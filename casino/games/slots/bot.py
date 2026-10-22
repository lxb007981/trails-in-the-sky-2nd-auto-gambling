"""Check fast mode once, then play slots by alternating S and Enter."""
import argparse
import json
import math
import time
from pathlib import Path

from casino.common.paths import ROOT
from casino.common.window import GameWindow, RunLock, Stopped
from casino.common.vision import RecognitionError
from casino.games.slots.vision import SlotsVision


class SlotsBot:
    def __init__(self, game, logdir=None):
        self.game = game
        self.vision = SlotsVision()
        self.logdir = Path(logdir or ROOT/'logs'/('slots_'+time.strftime('%Y%m%d_%H%M%S')))
        self.logdir.mkdir(parents=True, exist_ok=True)

    def event(self, event, **data):
        row = dict(time=time.time(), event=event, **data)
        text = json.dumps(row, ensure_ascii=False)
        with (self.logdir/'events.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(text+'\n')
        print(text, flush=True)

    def run(self, minutes):
        if not math.isfinite(minutes) or minutes <= 0:
            raise ValueError('minutes must be finite and positive')
        start = time.monotonic()
        deadline = start + minutes*60
        counts = dict(s=0, enter=0)
        next_heartbeat = start + 30
        self.event('start', minutes=minutes, screenshots='startup_only', strategy=['s', 'enter'])
        try:
            image = self.game.grab()
            image.save(self.logdir/'startup.png')
            fast_mode = self.vision.fast_mode(image)
            self.event('mode_detected', initial_fast_mode=fast_mode, screenshot='startup.png')
            if fast_mode == 'off':
                self.game.press('ctrl')
            self.event('fast_mode', action='pressed_ctrl' if fast_mode == 'off' else 'already_on',
                       basis='startup_screenshot')
            index = 0
            while time.monotonic() < deadline:
                self.game.check()
                # The shared press holds for 80 ms and rests for 200 ms.
                # Reserve that time so a new press is not started at the deadline.
                remaining = deadline-time.monotonic()
                if remaining < .28:
                    time.sleep(max(0, min(.02, remaining)))
                    continue
                key = ('s', 'enter')[index % 2]
                self.game.press(key)
                counts[key] += 1
                index += 1
                now = time.monotonic()
                if now >= next_heartbeat:
                    self.event('heartbeat', elapsed_seconds=now-start, presses=dict(counts))
                    next_heartbeat = now+30
        except (Stopped, RecognitionError, KeyboardInterrupt) as error:
            self.event('stopped', reason=str(error) or type(error).__name__,
                       elapsed_seconds=time.monotonic()-start, presses=counts)
            raise
        self.event('complete', elapsed_seconds=time.monotonic()-start, presses=counts,
                   stop_reason='duration_reached')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Actually send keys')
    parser.add_argument('--focus', action='store_true', help='Bring game to foreground')
    parser.add_argument('--minutes', type=float, default=10)
    args = parser.parse_args()
    if not math.isfinite(args.minutes) or args.minutes <= 0:
        parser.error('--minutes must be finite and positive')
    if not args.run:
        print('No keys sent. Use --run --focus --minutes 10; fast mode is detected automatically.')
        return 0
    try:
        lock = RunLock()  # Keep the shared mutex alive until all input stops.
        bot = SlotsBot(GameWindow(args.focus))
        bot.run(args.minutes)
        return 0
    except (Stopped, RecognitionError, KeyboardInterrupt) as error:
        print(str(error) or type(error).__name__, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
