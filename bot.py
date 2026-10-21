"""Screen-driven Trails poker automation; defaults to read-only inspection."""
import argparse
import json
import math
from pathlib import Path
import time
from game_window import GameWindow, Stopped, RunLock
from vision import Vision, RecognitionError, ROOT
from poker import Strategy, parse_card, categories, PAYOUTS

class Bot:
    def __init__(self, game, logdir=None, wheel=True):
        self.lock = RunLock()
        self.game, self.vision = game, Vision()
        for kind, expected in [('ranks',set('23456789TJQKA')),('suits',set('CDHS')),('digits',set('0123456789'))]:
            if set(self.vision.templates[kind]) != expected:
                raise RecognitionError(f'Missing {kind} templates; run build_assets.py')
        self.strategy = Strategy(wheel=wheel)
        self.wheel = wheel
        self.logdir = Path(logdir or ROOT/'logs'/time.strftime('%Y%m%d_%H%M%S'))
        self.logdir.mkdir(parents=True, exist_ok=True)
        self.last = None

    def event(self, kind, **data):
        row = dict(time=time.time(),event=kind,**data)
        with (self.logdir/'events.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(json.dumps({k:v for k,v in row.items() if k!='all_ev'},ensure_ascii=False),flush=True)

    def wait(self, states, timeout=20, predicate=None):
        end = time.monotonic()+timeout
        previous = None
        count = 0
        last_error = None
        while time.monotonic()<end:
            im = self.game.grab()
            self.last = im
            state = self.vision.state(im)
            if state in {'bet_prompt','deposit','cancel','result','win_dialog','loss_dialog','settlement'}:
                if not self.vision.dialogue_ready(im):
                    previous,count = None,0
                    time.sleep(.25)
                    continue
            if state in states:
                try:
                    value = predicate(im) if predicate else state
                except RecognitionError as e:
                    last_error = str(e)
                    value = None
                if value is not None:
                    if value == previous:
                        count += 1
                    else:
                        previous, count = value, 1
                    if count >= 3:
                        return im, value
                else:
                    previous,count = None,0
            else:
                previous,count = None,0
            time.sleep(.25)
        raise RecognitionError(f'Timed out waiting for {states}; last state={state}; detail={last_error}')

    def press(self,key):
        self.game.press(key)

    def to_bet(self):
        im,state = self.wait({'menu','bet_prompt','bet'})
        if state == 'menu':
            # Require the observed Start-selected menu, not an arbitrary highlight.
            if not self.vision.start_selected(im):
                raise RecognitionError('Select Start in the game menu before running')
            self.press('enter')
            self.wait({'bet_prompt'})
            self.press('enter')
        elif state == 'bet_prompt':
            self.press('enter')
        return self.wait({'bet'},predicate=lambda im:(self.vision.balance(im),self.vision.remaining(im)))

    def set_bet(self, target):
        for _ in range(12):
            im,(balance,remaining) = self.wait({'bet'},predicate=lambda im:(self.vision.balance(im),self.vision.remaining(im)))
            current = balance-remaining
            if not 1<=current<=10:
                raise RecognitionError(f'Invalid bet from balances: {balance}, {remaining}')
            if current == target:
                return balance
            if target == 10:
                self.press('a')
                self.press('a')
            else:
                self.press('w' if current<target else 's')
        raise RecognitionError('Could not set bet')

    def play_hand(self, tag):
        im,cards = self.wait({'hand'},predicate=lambda im:self.vision.hand(im)[0])
        if any(self.vision.holds(im)):
            raise RecognitionError('Hand already has HOLD markers; refusing to assume state')
        im.save(self.logdir/f'{tag}_initial.png')
        choice = self.strategy.evaluate(cards)
        self.event('decision',cards=cards,**choice)
        expected = [False]*5
        for target in choice['hold']:
            for _ in range(7):
                im,cursor = self.wait({'hand'},predicate=self.vision.cursor)
                if cursor == target:
                    break
                self.press('a' if cursor>target else 'd')
            else:
                raise RecognitionError('Cursor navigation failed')
            self.press('enter')
            expected[target] = True
            self.wait({'hand'},predicate=lambda im: True if self.vision.holds(im)==expected else None)
        for _ in range(7):
            im,cursor = self.wait({'hand'},predicate=self.vision.cursor)
            if cursor == 5:
                break
            self.press('d')
        else:
            raise RecognitionError('Could not select Change')
        if self.vision.holds(im) != expected:
            raise RecognitionError('HOLD verification failed')
        im.save(self.logdir/f'{tag}_hold.png')
        self.press('enter')
        # Wait for the completed result dialogue; never skip dealing animations.
        im,_ = self.wait({'result','win_dialog','loss_dialog'},timeout=30,
                         predicate=lambda im:self.vision.hand(im)[0])
        final = self.vision.hand(im)[0]
        for i in choice['hold']:
            if final[i] != cards[i]:
                raise RecognitionError('Retained card changed unexpectedly')
        category = int(categories([[parse_card(c) for c in final]],self.wheel)[0])
        payout = int(PAYOUTS[category])
        im.save(self.logdir/f'{tag}_result.png')
        self.press('enter')
        self.wait({'settlement'},predicate=lambda im: True if min(
            self.vision.score(im,'win_dialog'),self.vision.score(im,'loss_dialog')) < .025 else None)
        self.press('enter')
        return dict(initial=cards, final=final, hold=choice['hold'], payout=payout,
                    expected_return=choice['expected_return'])

    def run(self, minutes=15, bet=10):
        if not math.isfinite(minutes) or minutes <= 0:
            raise ValueError('Minutes must be finite and positive')
        if bet not in range(1, 11):
            raise ValueError('Bet must be an integer from 1 to 10')
        started = time.monotonic()
        deadline = started + minutes*60
        self.to_bet()
        initial_balance = self.set_bet(bet)
        self.event('start',initial_balance=initial_balance,bet=bet,minutes=minutes,
                   wheel=self.wheel,draw_model='47_remaining_without_replacement')
        balance = initial_balance
        completed = 0
        while True:
            if time.monotonic() >= deadline:
                reason = 'duration_reached'
                break
            if balance < bet:
                reason = 'insufficient_balance'
                break
            before = self.set_bet(bet)
            if before != balance:
                raise RecognitionError('Balance changed outside this run')
            # Setting/recognizing the bet can take time. Recheck before committing.
            if time.monotonic() >= deadline:
                reason = 'duration_reached'
                break
            n = completed + 1
            self.press('enter')
            self.wait({'deposit'})
            self.press('enter')
            result = self.play_hand(f'round_{n:03d}')
            _,(balance,_) = self.to_bet()
            expected = before-bet+bet*result['payout']
            if balance != expected:
                raise RecognitionError(f'Balance mismatch: expected {expected}, observed {balance}')
            completed += 1
            self.event('round',round=n,bet=bet,before=before,after=balance,**result)
        # Leave a clean Start menu, without making another bet.
        self.press('escape')
        self.wait({'cancel'})
        self.press('enter')
        final_image,_ = self.wait({'menu'})
        final_image.save(self.logdir/'final_menu.png')
        self.event('complete',rounds=completed,initial_balance=initial_balance,
                   final_balance=balance,net=balance-initial_balance,
                   stop_reason=reason,elapsed_seconds=time.monotonic()-started)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',action='store_true',help='Enable keyboard actions')
    p.add_argument('--focus',action='store_true',help='Bring game forward once at startup')
    p.add_argument('--bet',type=int,choices=range(1,11),default=10)
    p.add_argument('--minutes',type=float,default=15,
                   help='Run for this many minutes, then finish the current hand (default: 15)')
    p.add_argument('--no-wheel',action='store_true',help='Do not count A2345 as a straight')
    args = p.parse_args()
    if not math.isfinite(args.minutes) or args.minutes <= 0:
        p.error('Minutes must be finite and positive')
    bot = None
    try:
        game = GameWindow(focus=args.focus)
        if not args.run:
            im = game.grab()
            v = Vision()
            state = v.state(im)
            info = {'state':state}
            if state=='hand':
                cards,_ = v.hand(im)
                info.update(cards=cards, strategy=Strategy(wheel=not args.no_wheel).evaluate(cards))
            elif state=='bet':
                info.update(balance=v.balance(im),bet=v.balance(im)-v.remaining(im))
            print(json.dumps(info,ensure_ascii=False,indent=2))
            return 0
        bot = Bot(game,wheel=not args.no_wheel)
        bot.run(minutes=args.minutes,bet=args.bet)
        return 0
    except (Stopped,RecognitionError,KeyboardInterrupt) as e:
        if bot:
            if bot.last:
                bot.last.save(bot.logdir/'stopped.png')
            bot.event('stopped',reason=str(e))
        else:
            print(f'Stopped: {e}',flush=True)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
