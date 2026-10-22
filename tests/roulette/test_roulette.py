import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image
from casino.common.paths import ROOT
from casino.common.vision import RecognitionError
from casino.games.roulette.vision import RouletteVision
from casino.games.roulette.bot import RouletteBot


class VisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vision = RouletteVision()

    def test_states(self):
        for name, state in [('rt_001_menu','menu'),('rt_017_start','prompt'),
                            ('rt_018_board','board'),('rt_022_result','settlement'),
                            ('rt_024_again','again'),('rt_026_cancel','cancel')]:
            with self.subTest(name=name), Image.open(ROOT/'captures'/f'{name}.png') as im:
                self.assertEqual(self.vision.state(im),state)

    def test_all_counter_digits_and_disconnected_strokes(self):
        for i in range(10):
            with self.subTest(i=i), Image.open(ROOT/'captures'/f'rt_cal_{i}.png') as im:
                self.assertEqual(self.vision.account(im),(66951-i*10,(i+1)*10))

    def test_loss_settlement(self):
        with Image.open(ROOT/'captures/rt_022_result.png') as im:
            self.assertEqual(self.vision.settlement(im),(10,0,0))

    def test_menu_balances_after_blackjack(self):
        for balance in (96972, 25011):
            with self.subTest(balance=balance), Image.open(ROOT/'captures'/f'rt_account_{balance}.png') as im:
                self.assertEqual(self.vision.state(im), 'menu')
                self.assertEqual(self.vision.account(im), (balance, 0))

    def test_win_settlement_uses_different_table(self):
        with Image.open(ROOT/'captures/rt_win.png') as im:
            self.assertEqual(self.vision.state(im),'settlement')
            self.assertEqual(self.vision.settlement(im),(10,12,120))

    def test_zero_bet_after_settlement(self):
        with Image.open(ROOT/'captures/rt_zero_regression.png') as im:
            self.assertEqual(self.vision.account(im),(66981,0))

    def test_pulsing_street_selection(self):
        for name in ('rt_018_board', 'rt_selection_regression'):
            with Image.open(ROOT/'captures'/f'{name}.png') as im:
                self.assertTrue(self.vision.street_selected(im))
                for y in (230,305,380):
                    wrong = im.copy()
                    wrong.paste((0,100,30),(176,y,188,y+35))
                    self.assertFalse(self.vision.street_selected(wrong))

    def test_unknown_screen_does_not_authorize_input(self):
        im = Image.new('RGB',(1280,720))
        self.assertEqual(self.vision.state(im),'animation')
        with self.assertRaises(RecognitionError):
            self.vision.account(im)


class RunTests(unittest.TestCase):
    def bot(self):
        bot = RouletteBot.__new__(RouletteBot)
        bot.game = Mock()
        bot.vision = Mock()
        bot.event = Mock()
        bot.finish = Mock()
        bot.prepare_fast_mode = Mock()
        bot.fast_mode = False
        bot.poll_interval = .25
        return bot

    def test_invalid_duration_sends_nothing(self):
        for duration in (0,-1,math.inf,math.nan):
            bot = self.bot()
            with self.assertRaises(ValueError):
                bot.run(duration)
            bot.game.press.assert_not_called()

    def test_recognition_failure_is_reported_and_times_out_without_input(self):
        bot = self.bot()
        bot.vision.state.return_value = 'menu'
        bot.vision.account.side_effect = RecognitionError('balance digit uncertain')
        with patch('casino.games.roulette.bot.time.monotonic', side_effect=[0, 0, 1, 5, 61]), \
                patch('casino.games.roulette.bot.time.sleep'):
            with self.assertRaisesRegex(RecognitionError, 'balance digit uncertain'):
                bot.wait({'menu'}, bot.vision.account)
        self.assertEqual(bot.event.call_count, 2)
        bot.event.assert_called_with('recognition_wait', state='menu', reason='balance digit uncertain')
        bot.game.press.assert_not_called()

    def test_recognition_recovers_only_after_four_stable_reads(self):
        bot = self.bot()
        bot.vision.state.return_value = 'menu'
        bot.vision.account.side_effect = [RecognitionError('uncertain'), (25011, 0),
                                        (25011, 0), (25011, 0), (25011, 0)]
        with patch('casino.games.roulette.bot.time.sleep'):
            _, state, account = bot.wait({'menu'}, bot.vision.account)
        self.assertEqual((state, account), ('menu', (25011, 0)))
        self.assertEqual(bot.game.grab.call_count, 5)
        bot.game.press.assert_not_called()

    def test_deadline_before_bet(self):
        bot = self.bot()
        bot.board = Mock(return_value=100)
        with patch('casino.games.roulette.bot.time.monotonic',side_effect=[0,61,62]):
            bot.run(1)
        bot.game.press.assert_not_called()
        bot.finish.assert_called_once()

    def test_wrong_debit_never_starts_wheel(self):
        bot = self.bot()
        bot.board = Mock(return_value=100)
        bot.wait = Mock(return_value=(None,'board',(80,20)))
        with self.assertRaises(RecognitionError):
            bot.run(1)
        self.assertEqual(bot.game.press.call_args_list, [unittest.mock.call('enter')])

    def test_current_round_finishes_after_deadline(self):
        bot = self.bot()
        bot.board = Mock(side_effect=[100,90])
        bot.wait = Mock(side_effect=[(None,'board',(90,10)),(Mock(),'settlement',(10,0,0)),(None,'again',None)])
        with tempfile.TemporaryDirectory() as folder:
            bot.logdir = Path(folder)
            with patch('casino.games.roulette.bot.time.monotonic',side_effect=[0,1,2,65,66,67]):
                bot.run(1)
        self.assertEqual([c.args[0] for c in bot.game.press.call_args_list], ['enter','tab','enter'])
        self.assertEqual(bot.event.call_args.kwargs['rounds'],1)
        self.assertEqual(bot.event.call_args.kwargs['net'],-10)
        bot.finish.assert_called_once()


if __name__ == '__main__':
    unittest.main()
