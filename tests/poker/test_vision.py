import unittest
from PIL import Image
from casino.games.poker.vision import Vision, ROOT, RecognitionError
from unittest.mock import patch
import tempfile
import shutil
from pathlib import Path
import numpy as np

class VisionTests(unittest.TestCase):
    def setUp(self):
        self.v = Vision()

    def im(self,name):
        return Image.open(ROOT/'captures'/f'{name}.png')

    def test_states(self):
        for file,state in [('042_final_menu','menu'),('005_bet','bet'),('006_deal','deposit'),
                           ('007_hand','hand'),('010_loss','settlement'),('038_win','settlement'),
                           ('039_paid','bet_prompt'),('013_cancel','cancel'),('052_hand','unknown')]:
            with self.subTest(file=file):
                self.assertEqual(self.v.state(self.im(file)),state)

    def test_state_assets_match_original_pixels(self):
        from tools.build_poker_assets import STATE_REFERENCES
        from casino.games.poker.vision import crop
        offsets = {}
        for name,source,box in STATE_REFERENCES:
            index = offsets.get(name,0)
            actual_box, actual = self.v.refs[name][index]
            self.assertEqual(tuple(actual_box),box)
            np.testing.assert_array_equal(actual,crop(self.im(source),box))
            offsets[name] = index+1

    def test_runtime_without_capture_directory(self):
        menu = self.im('042_final_menu')
        hand = self.im('063_result')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT/'assets',root/'assets')
            with patch('casino.games.poker.vision.ROOT',root), patch('casino.games.poker.vision.ASSETS',root/'assets'):
                v = Vision()
                self.assertFalse((root/'captures').exists())
                self.assertEqual(v.state(menu),'menu')
                self.assertEqual(v.hand(hand)[0],['TS','7D','5D','TD','5C'])
                (root/'assets'/'states'/'manifest.json').unlink()
                with self.assertRaises(RecognitionError):
                    Vision()

    def test_hold_and_focus(self):
        for file,expected,cursor in [('028_hand',[0,0,0,0,0],5),('029_left',[0,0,0,0,0],4),
                                    ('031_hold4',[0,0,0,1,0],3),('034_right',[0,0,1,1,0],3)]:
            with self.subTest(file=file):
                im = self.im(file)
                self.assertEqual(self.v.holds(im),[bool(x) for x in expected])
                self.assertEqual(self.v.cursor(im),cursor)

    def test_bet_balance(self):
        im = self.im('050_bet')
        self.assertEqual(self.v.balance(im),403)
        self.assertEqual(self.v.remaining(im),393)

    def test_unreadable_card_rejected(self):
        with self.assertRaises(RecognitionError):
            self.v.hand(self.im('052_hand'))

    def test_four_digit_balances(self):
        for file,balance,remaining in [('live_progress',1556,1546), ('digits_four',1586,1576)]:
            with self.subTest(file=file):
                im = self.im(file)
                self.assertEqual(self.v.balance(im),balance)
                self.assertEqual(self.v.remaining(im),remaining)

    def test_untrained_result_frame(self):
        # This frame is deliberately absent from labels.json/template training.
        self.assertEqual(self.v.hand(self.im('063_result'))[0],['TS','7D','5D','TD','5C'])

    def test_queen_tail_does_not_change_spade_to_club(self):
        self.assertEqual(self.v.hand(self.im('066_queen_regression'))[0],['2H','7D','KH','QS','QH'])
        self.assertEqual(self.v.hand(self.im('067_three_kind'))[0],['JS','5D','QD','QS','QH'])

    def test_waits_for_dialogue_triangle(self):
        for name in ['010_loss','038_win','054_debug','056_paid','006_deal','004_rules']:
            self.assertTrue(self.v.dialogue_ready(self.im(name)),name)
        self.assertFalse(self.v.dialogue_ready(self.im('064_live')))

    def test_start_selection(self):
        self.assertTrue(self.v.start_selected(self.im('042_final_menu')))
        self.assertFalse(self.v.start_selected(self.im('015_s')))

    def test_result_gate_skips_unfinished_flash(self):
        from casino.games.poker.bot import Bot
        from unittest.mock import MagicMock, patch
        bot = Bot.__new__(Bot)
        bot.vision = self.v
        bot.game = MagicMock()
        bot.game.grab.side_effect = [self.im('064_live')]*3+[self.im('063_result')]*3
        with patch('casino.games.poker.bot.time.sleep'):
            _,cards = bot.wait({'result'},predicate=lambda im:self.v.hand(im)[0])
        self.assertEqual(cards,['TS','7D','5D','TD','5C'])
        self.assertEqual(bot.game.grab.call_count,6)

if __name__=='__main__':
    unittest.main()
