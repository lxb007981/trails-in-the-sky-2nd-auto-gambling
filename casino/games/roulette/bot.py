"""Screenshot-driven fixed-stake roulette with per-round accounting."""
import argparse
import json
import math
import time
from pathlib import Path
from casino.common.paths import ROOT
from casino.common.fast_mode import FastModeVision
from casino.common.window import GameWindow, RunLock, Stopped
from casino.common.vision import RecognitionError
from casino.games.roulette.vision import RouletteVision


class RouletteBot:
    def __init__(self, game, logdir=None):
        self.lock = RunLock()
        self.game, self.vision = game, RouletteVision()
        self.logdir = Path(logdir or ROOT/'logs'/('roulette_'+time.strftime('%Y%m%d_%H%M%S')))
        self.logdir.mkdir(parents=True, exist_ok=True)
        self.last = None
        self.fast_mode = False
        self.poll_interval = .25

    def event(self, event, **data):
        row = dict(time=time.time(), event=event, **data)
        text = json.dumps(row, ensure_ascii=False)
        with (self.logdir/'events.jsonl').open('a', encoding='utf-8') as f:
            f.write(text+'\n')
        print(text, flush=True)

    def wait(self, states, read=None, timeout=60):
        end = time.monotonic()+timeout
        previous, count, detail = None, 0, None
        while time.monotonic() < end:
            self.last = self.game.grab()
            state = self.vision.state(self.last)
            try:
                value = (state, read(self.last) if read else None) if state in states else None
            except RecognitionError as error:
                detail, value = str(error), None
            count = count+1 if value is not None and value == previous else 1
            previous = value
            if value is not None and count >= 4:
                return self.last, state, value[1]
            time.sleep(self.poll_interval)
        raise RecognitionError(f'Timed out waiting for {states}; state={state}; {detail}')

    def prepare_fast_mode(self):
        vision = FastModeVision(ROOT/'assets'/'roulette')
        self.last = self.game.grab()
        self.last.save(self.logdir/'startup.png')
        mode = vision.fast_mode(self.last)
        self.event('mode_detected', initial_fast_mode=mode)
        if mode == 'off':
            self.game.press('ctrl')

        def confirmed(image):
            if vision.fast_mode(image) != 'on':
                raise RecognitionError('Fast mode is not enabled')
            return 'on'

        self.wait({'menu','prompt','again','board'}, confirmed, timeout=5)
        self.last.save(self.logdir/'fast_mode_confirmed.png')
        self.fast_mode = True
        self.poll_interval = .12
        self.event('fast_mode', action='pressed_ctrl' if mode == 'off' else 'already_on',
                   confirmed=True, hold_seconds=.06, rest_seconds=.12, poll_seconds=.12)

    def press(self, key):
        if self.fast_mode:
            self.game.press(key, hold=.06, rest=.12)
        else:
            self.game.press(key)

    def board(self):
        for _ in range(4):
            im, state, account = self.wait({'menu','prompt','again','board'}, self.vision.account)
            if state == 'board':
                if account[1] != 0 or not self.vision.street_selected(im):
                    raise RecognitionError('Expected empty board with initial 1/2/3 street selected')
                return account[0]
            if state == 'menu':
                # Menu selection is verified separately before confirming Start.
                a = im.getpixel((630,320))
                if not (a[0]>180 and a[1]>140 and a[2]<190):
                    raise RecognitionError('Select Start before running')
            self.press('enter')
        raise RecognitionError('Cannot reach board')

    def finish(self):
        self.press('escape')
        self.wait({'cancel'})
        self.press('enter')
        self.wait({'menu'})
        self.last.save(self.logdir/'final_menu.png')

    def run(self, minutes):
        if not math.isfinite(minutes) or minutes <= 0:
            raise ValueError('minutes must be finite and positive')
        start = time.monotonic()
        self.prepare_fast_mode()
        initial = before = self.board()
        rounds = 0
        self.event('start', balance=initial, minutes=minutes, stake=10, selection=[1,2,3])
        reason = 'duration_reached'
        while time.monotonic()-start < minutes*60:
            if before < 10:
                reason = 'insufficient_balance'
                break
            # Recheck deadline immediately before committing funds.
            if time.monotonic()-start >= minutes*60:
                break
            self.press('enter')
            _,_,account = self.wait({'board'}, self.vision.account)
            if account != (before-10,10):
                raise RecognitionError(f'Bet debit mismatch: {account}, before={before}')
            self.press('tab')
            self.event('spin', round=rounds+1)
            im,_,result = self.wait({'settlement'}, self.vision.settlement)
            im.save(self.logdir/f'{rounds+1:04d}_settlement.png')
            self.press('enter')
            # Acknowledge next-round prompt only after it has finished rendering.
            self.wait({'again'})
            after = self.board()
            expected = before-10+result[2]
            if after != expected:
                raise RecognitionError(f'Balance mismatch: {after}, expected {expected}')
            rounds += 1
            self.event('round', round=rounds, before=before, after=after,
                       bet=result[0], rate=result[1], received=result[2], elapsed_seconds=time.monotonic()-start)
            before = after
        self.finish()
        self.event('complete', rounds=rounds, initial_balance=initial, final_balance=before,
                   net=before-initial, elapsed_seconds=time.monotonic()-start, stop_reason=reason)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--focus', action='store_true')
    parser.add_argument('--minutes', type=float, default=20)
    args = parser.parse_args()
    if not math.isfinite(args.minutes) or args.minutes <= 0:
        parser.error('--minutes must be finite and positive')
    bot = None
    try:
        bot = RouletteBot(GameWindow(args.focus))
        if args.run:
            bot.run(args.minutes)
        else:
            im = bot.game.grab()
            print(bot.vision.state(im), bot.vision.account(im))
        return 0
    except (Stopped, RecognitionError, KeyboardInterrupt) as error:
        if bot:
            if bot.last is not None:
                bot.last.save(bot.logdir/'stopped.png')
            bot.event('stopped', reason=str(error))
        else:
            print(str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
