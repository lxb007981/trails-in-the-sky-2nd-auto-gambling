"""Foreground, screenshot-driven blackjack automation for Trails 2nd."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time
from casino.common.window import GameWindow, RunLock, Stopped
from casino.common.paths import ROOT
from casino.common.vision import RecognitionError, crop
from casino.games.blackjack.vision import BlackjackVision
from casino.games.blackjack.strategy import Strategy
from casino.games.blackjack.rules import payout, RATES, hand


class BlackjackBot:
    def __init__(self, game, logdir=None, dealer_stand=17, special_ties=True):
        self.lock = RunLock()
        self.game = game
        self.vision = BlackjackVision()
        self.strategy = Strategy(dealer_stand, special_ties)
        self.logdir = Path(logdir or ROOT/'logs'/('blackjack_'+time.strftime('%Y%m%d_%H%M%S')))
        self.logdir.mkdir(parents=True, exist_ok=True)
        self.last = None

    def event(self, event, **data):
        row = dict(time=time.time(),event=event,**data)
        with (self.logdir/'events.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(json.dumps(row,ensure_ascii=False),flush=True)

    def signature(self, im, state):
        # The first text line changes after an acknowledged dialogue. Excludes
        # the blinking continuation arrow and the moving card table.
        patch = crop(im,(250,64,400,85))
        return state, hashlib.sha256((patch.min(2)<130).tobytes()).hexdigest()

    def wait(self, states, predicate=None, timeout=30, exclude=None):
        end = time.monotonic()+timeout
        previous, count, detail, state = None, 0, None, 'unknown'
        while time.monotonic() < end:
            im = self.game.grab()
            self.last = im
            state = self.vision.state(im)
            if state in states and (exclude is None or self.signature(im,state) != exclude):
                try:
                    value = predicate(im,state) if predicate else self.signature(im,state)
                except RecognitionError as error:
                    if str(error) != detail:
                        self.event('recognition_wait', state=state, reason=str(error))
                    value, detail = None, str(error)
                if value is not None:
                    count = count+1 if value == previous else 1
                    previous = value
                    if count >= 3:
                        return im, state, value
                else:
                    previous, count = None, 0
            else:
                previous, count = None, 0
            time.sleep(.20)
        raise RecognitionError(f'Timed out: wanted {states}, saw {state}; {detail}')

    def press(self, key):
        self.game.press(key)

    def to_bet(self):
        for _ in range(5):
            im, state, _ = self.wait({'menu','bet_prompt','again','bet'})
            if state == 'bet':
                return self.wait({'bet'},lambda im,s:self.vision.bet(im))[2]
            if state == 'menu' and not self.vision.start_selected(im):
                raise RecognitionError('Select Start before running')
            before = self.signature(im,state)
            self.press('enter')
            self.wait({'bet_prompt','again','bet'},exclude=before)
        raise RecognitionError('Could not reach bet window')

    def set_bet(self, target):
        # A/D move the decimal cursor; pressing beyond its boundary jumps to
        # maximum/minimum. Three A/D presses reliably select 100/1 respectively.
        _,_,(balance,current) = self.wait({'bet'},lambda im,s:self.vision.bet(im))
        if balance < target:
            return balance
        if current != target:
            endpoint = 100 if target > 50 and balance >= 100 else 1
            for _ in range(3):
                self.press('a' if endpoint == 100 else 'd')
            _,_,(balance,current) = self.wait({'bet'},lambda im,s:self.vision.bet(im))
            if current != endpoint:
                raise RecognitionError(f'Bet shortcut produced {current}, expected {endpoint}')
            if current != target:
                if endpoint == 100:
                    # From hundreds to units; a third D would reset to 1.
                    self.press('d')
                    self.press('d')
                    _,_,(balance,current) = self.wait({'bet'},lambda im,s:self.vision.bet(im))
                    if current != 100:
                        raise RecognitionError('Moving the bet cursor changed the amount')
                for _ in range(100):
                    if current == target:
                        break
                    self.press('w' if current < target else 's')
                    _,_,(balance,new) = self.wait({'bet'},lambda im,s:self.vision.bet(im))
                    if abs(new-current) != 1:
                        raise RecognitionError(f'Unexpected bet step: {current} -> {new}')
                    current = new
                if current != target:
                    raise RecognitionError('Could not select requested bet')
        return balance

    def choose(self, action):
        target = {'hit':0,'stand':1,'double':2}[action]
        for _ in range(4):
            _,_,cursor = self.wait({'hand'},lambda im,s:self.vision.cursor(im))
            if cursor == target:
                self.press('enter')
                return
            self.press('s' if cursor < target else 'w')
        raise RecognitionError(f'Cannot select {action}')

    def play_hand(self, tag, bet, before, *, dealt=False, known=()):
        if not dealt:
            self.wait({'deposit'})
            self.press('enter')
            self.wait({'open'})
            self.press('enter')
        old_cards, upcard, final, dealer_total = tuple(known), None, None, None
        doubled, pending_hit, exclude = False, False, None
        for step in range(32):
            def ready(im, state):
                if state == 'hand':
                    cards, up = self.vision.observation(im)
                    if pending_hit and len(cards) == len(old_cards):
                        return None
                    return state, cards, up
                if state == 'settlement':
                    return state, self.vision.settlement(im)
                return state, self.vision.final_hand(im,final or old_cards), self.signature(im,state)
            im, state, observation = self.wait({'hand','stand_dialog','dialog','settlement'},ready,exclude=exclude)
            im.save(self.logdir/f'{tag}_{step:02d}_{state}.png')
            if state == 'settlement':
                actual_bet, rate, received = observation[1]
                expected_bet = bet*(2 if doubled else 1)
                if actual_bet != expected_bet or rate not in RATES or final is None:
                    raise RecognitionError(f'Unexpected settlement: {observation}, bet={expected_bet}')
                expected_rate = payout(final,dealer_total,self.strategy.special_ties)
                if rate != expected_rate:
                    raise RecognitionError(f'Rule mismatch: expected rate {expected_rate}, observed {rate}; '
                                           f'cards={final}, dealer={dealer_total}')
                self.event('settlement',cards=final,dealer_total=dealer_total,bet=actual_bet,rate=rate,received=received)
                self.press('enter')
                return dict(cards=final,dealer_total=dealer_total,bet=actual_bet,rate=rate,received=received)
            if state == 'hand':
                cards, up = observation[1:]
                if old_cards and cards[:len(old_cards)] != old_cards:
                    raise RecognitionError(f'Previous cards changed: {old_cards} -> {cards}')
                if pending_hit and len(cards) != len(old_cards)+1:
                    raise RecognitionError('Hit did not add exactly one card')
                if upcard is not None and up != upcard:
                    raise RecognitionError('Dealer upcard changed')
                upcard, old_cards, pending_hit = up, cards, False
                choice = self.strategy.evaluate(cards,up,can_double=(before >= 2*bet))
                self.event('decision',cards=cards,dealer=up,**choice)
                action = choice['action']
                doubled = action == 'double'
                pending_hit = action == 'hit'
                self.choose(action)
                # After stand/double, an unchanged menu must not be acted on.
                exclude = self.signature(im,state) if action != 'hit' else None
            else:
                final, dealer_total = observation[1]
                if old_cards and final[:len(old_cards)] != old_cards:
                    raise RecognitionError('Final cards do not preserve the observed hand')
                if pending_hit and len(final) != len(old_cards)+1:
                    raise RecognitionError('Terminal hit did not add one card')
                pending_hit = False
                exclude = self.signature(im,state)
                self.press('enter')
        raise RecognitionError('Too many transitions in one hand')

    def finish(self):
        self.wait({'bet'})
        self.press('escape')
        self.wait({'cancel'})
        self.press('enter')
        im,_,_ = self.wait({'menu'})
        im.save(self.logdir/'final_menu.png')

    def run(self, minutes=15, bet=1):
        if not math.isfinite(minutes) or minutes <= 0 or not 1 <= bet <= 100:
            raise ValueError('Require finite positive minutes and bet 1..100')
        start = time.monotonic()
        deadline = start+minutes*60
        initial,_ = self.to_bet()
        balance, completed = initial, 0
        self.event('start',balance=initial,bet=bet,minutes=minutes,dealer_stand=self.strategy.dealer_stand,
                   special_ties=self.strategy.special_ties,model='independent_draws')
        while True:
            if time.monotonic() >= deadline:
                reason = 'duration_reached'
                break
            if balance < bet:
                reason = 'insufficient_balance'
                break
            observed = self.set_bet(bet)
            if observed != balance:
                raise RecognitionError('Balance changed outside this run')
            if time.monotonic() >= deadline:
                reason = 'duration_reached'
                break
            self.press('enter')
            result = self.play_hand(f'round_{completed+1:03d}',bet,balance)
            after,_ = self.to_bet()
            expected = balance-result['bet']+result['received']
            if after != expected:
                raise RecognitionError(f'Balance mismatch: expected {expected}, observed {after}')
            completed += 1
            self.event('round',round=completed,before=balance,after=after,**result)
            balance = after
        self.finish()
        self.event('complete',rounds=completed,initial_balance=initial,final_balance=balance,
                   net=balance-initial,stop_reason=reason,elapsed_seconds=time.monotonic()-start)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--focus',action='store_true')
    parser.add_argument('--minutes',type=float,default=15)
    parser.add_argument('--bet',type=int,choices=range(1,101),default=1)
    parser.add_argument('--dealer-stand',type=int,choices=(17,18),default=17)
    parser.add_argument('--ordinary-special-ties',action='store_true',help='Treat equal totals as draws, even with a bonus hand')
    args = parser.parse_args()
    if not math.isfinite(args.minutes) or args.minutes <= 0:
        parser.error('--minutes must be finite and positive')
    bot = None
    try:
        game = GameWindow(focus=args.focus)
        if not args.run:
            v = BlackjackVision()
            im = game.grab()
            state = v.state(im)
            info = dict(state=state)
            if state == 'hand':
                cards,up = v.observation(im)
                info.update(cards=cards,dealer=up,decision=Strategy(args.dealer_stand,not args.ordinary_special_ties).evaluate(cards,up,False))
            elif state == 'bet':
                info.update(zip(('balance','bet'),v.bet(im)))
            print(json.dumps(info,ensure_ascii=False,indent=2))
            return 0
        bot = BlackjackBot(game,dealer_stand=args.dealer_stand,special_ties=not args.ordinary_special_ties)
        bot.run(args.minutes,args.bet)
        return 0
    except (Stopped,RecognitionError,KeyboardInterrupt) as error:
        if bot:
            if bot.last:
                bot.last.save(bot.logdir/'stopped.png')
            bot.event('stopped',reason=str(error))
        else:
            print(f'Stopped: {error}',flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
