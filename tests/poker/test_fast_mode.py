import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from casino.common.fast_mode import FastModeVision, MODE_BOX
from casino.common.paths import ASSETS, ROOT
from casino.common.vision import RecognitionError
from casino.games.poker.bot import Bot


class FastModeTests(unittest.TestCase):
    def frame(self, mode):
        image = Image.new('RGB', (1280, 720))
        with Image.open(ASSETS/'poker'/f'fast_mode_{mode}.png') as badge:
            image.paste(badge, MODE_BOX[:2])
        return image

    def test_startup_and_toggle_failure(self):
        for mode in ('off', 'on', 'unknown', 'failed_toggle'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                bot = Bot.__new__(Bot)
                bot.logdir = Path(directory)
                bot.game, bot.vision, bot.event = Mock(), Mock(), Mock()
                bot.vision.state.return_value = 'menu'
                bot.fast_mode, bot.poll_interval = False, .25
                initial = (Image.new('RGB', (1280, 720), 'magenta') if mode == 'unknown'
                           else self.frame('off' if mode == 'failed_toggle' else mode))
                bot.game.grab.side_effect = [initial]+[self.frame('off' if mode == 'failed_toggle' else 'on')]*3
                with patch('casino.games.poker.bot.time.sleep'):
                    if mode == 'failed_toggle':
                        with patch('casino.games.poker.bot.time.monotonic', side_effect=[0, 0, 6]):
                            with self.assertRaises(RecognitionError):
                                bot.prepare_fast_mode()
                        self.assertFalse(bot.fast_mode)
                        bot.game.press.assert_called_once_with('ctrl')
                    elif mode == 'unknown':
                        with self.assertRaises(RecognitionError):
                            bot.prepare_fast_mode()
                        bot.game.press.assert_not_called()
                    else:
                        bot.prepare_fast_mode()
                        self.assertTrue(bot.fast_mode)
                        self.assertEqual(bot.game.grab.call_count, 4)
                        if mode == 'off':
                            bot.game.press.assert_called_once_with('ctrl')
                        else:
                            bot.game.press.assert_not_called()
                        bot.press('enter')
                        bot.game.press.assert_called_with('enter', hold=.06, rest=.12)

    def test_captured_modes(self):
        vision = FastModeVision(ASSETS/'poker')
        for mode, name in [('off', 'initial'), ('on', 'on')]:
            with Image.open(ROOT/'captures'/f'poker_fast_mode_{name}.png') as image:
                self.assertEqual(vision.fast_mode(image), mode)
