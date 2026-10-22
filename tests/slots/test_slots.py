import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

from casino.common.window import Stopped
from casino.common.paths import ASSETS
from casino.common.vision import RecognitionError
from casino.games.slots.bot import SlotsBot
from casino.games.slots.vision import SlotsVision, MODE_BOX


def mode_image(mode):
    image = Image.new('RGB', (1280, 720))
    with Image.open(ASSETS/'slots'/f'fast_mode_{mode}.png') as badge:
        image.paste(badge, MODE_BOX[:2])
    return image


class SlotsTests(unittest.TestCase):
    def run_bot(self, mode, stop=False):
        clock = [0.0]
        keys = []
        captures = []

        class Game:
            def grab(self):
                captures.append(True)
                return mode_image(mode)

            def check(self):
                if stop and len(keys) >= 4:
                    raise Stopped('focus lost')

            def press(self, key):
                self.check()
                keys.append(key)
                clock[0] += .28

        def sleep(seconds):
            clock[0] += seconds

        with tempfile.TemporaryDirectory() as logdir:
            bot = SlotsBot(Game(), logdir)
            with patch('casino.games.slots.bot.time.monotonic', side_effect=lambda: clock[0]), \
                 patch('casino.games.slots.bot.time.sleep', side_effect=sleep), \
                 patch.object(bot, 'event') as events:
                if stop:
                    with self.assertRaises(Stopped):
                        bot.run(10)
                    self.assertEqual(events.call_args.args[0], 'stopped')
                else:
                    bot.run(10)
                    self.assertEqual(events.call_args.args[0], 'complete')
                    self.assertAlmostEqual(clock[0], 600)
            self.assertEqual(len(captures), 1)
            self.assertTrue((bot.logdir/'startup.png').is_file())
        return keys

    def test_off_enables_once_and_alternates_until_deadline(self):
        keys = self.run_bot('off')
        self.assertEqual(keys.pop(0), 'ctrl')
        self.assertGreater(len(keys), 2000)
        self.assertTrue(all(key == ('s', 'enter')[i % 2] for i, key in enumerate(keys)))

    def test_on_does_not_toggle(self):
        keys = self.run_bot('on')
        self.assertEqual(set(keys), {'s', 'enter'})

    def test_focus_loss_stops_immediately(self):
        self.assertEqual(len(self.run_bot('on', stop=True)), 4)

    def test_unknown_mode_sends_no_keys(self):
        from unittest.mock import MagicMock
        game = MagicMock()
        game.grab.return_value = Image.new('RGB', (1280, 720), 'black')
        with tempfile.TemporaryDirectory() as logdir:
            bot = SlotsBot(game, logdir)
            with self.assertRaises(RecognitionError), patch.object(bot, 'event'):
                bot.run(10)
        game.press.assert_not_called()

    def test_wrong_resolution_rejected(self):
        with self.assertRaises(RecognitionError):
            SlotsVision().fast_mode(Image.new('RGB', (640, 360)))


if __name__ == '__main__':
    unittest.main()
