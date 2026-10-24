import unittest
from unittest.mock import Mock, patch
from PIL import Image, ImageDraw

from casino.common.paths import ROOT
from casino.games.blackjack.bot import BlackjackBot
from casino.games.blackjack.vision import BlackjackVision
from casino.games.poker.bot import Bot
from casino.games.poker.vision import Vision
from casino.games.roulette.bot import RouletteBot
from casino.games.roulette.vision import RouletteVision


class OptionalBalanceTests(unittest.TestCase):
    def test_bet_reading_with_unreadable_balances(self):
        cases = [(BlackjackBot, BlackjackVision, 'bj_031_bet', 1, 'read_bet'),
                 (Bot, Vision, '050_bet', 10, 'read_bet'),
                 (RouletteBot, RouletteVision, 'rt_cal_0', 10, 'read_account')]
        for cls, vision, capture, amount, reader in cases:
            with self.subTest(game=cls.__name__):
                with Image.open(ROOT/'captures'/f'{capture}.png') as source:
                    im = source.copy()
                draw = ImageDraw.Draw(im)
                for box in [(620,255,775,280), (620,436,775,461), (1100,55,1213,79)]:
                    draw.rectangle(box, fill='white')
                bot = cls.__new__(cls)
                bot.dev, bot.vision = False, vision()
                self.assertEqual(getattr(bot, reader)(im), (None, amount))
                bot.dev = True
                with self.assertRaises(RuntimeError):
                    getattr(bot, reader)(im)

    def test_blackjack_round_without_balance(self):
        from tests.blackjack.test_blackjack import ControlTests
        bot = ControlTests().bot()
        bot.dev = False
        bot.to_bet.return_value = (None, 1)
        bot.set_bet.return_value = None
        with patch('casino.games.blackjack.bot.time.monotonic', side_effect=[0,0,0,61,62]):
            bot.run(1,1)
        bot.play_hand.assert_called_once_with('round_001',1,None)
        bot.finish.assert_called_once()

    def test_poker_round_without_balance(self):
        from tests.poker.test_limits import LimitTests
        bot = LimitTests().make_bot([100,90],[0])
        bot.dev = False
        bot.to_bet.side_effect = None
        bot.to_bet.return_value = (None,(None,10))
        bot.set_bet.side_effect = None
        bot.set_bet.return_value = None
        with patch('casino.games.poker.bot.time.monotonic', side_effect=[0,0,0,61,62]):
            bot.run(1,10)
        bot.play_hand.assert_called_once()
        self.assertEqual(bot.event.call_args.kwargs['rounds'],1)

    def test_roulette_round_without_balance(self):
        bot = RouletteBot.__new__(RouletteBot)
        bot.dev = False
        bot.vision = Mock()
        bot.prepare_fast_mode = Mock()
        bot.board = Mock(return_value=None)
        bot.press, bot.finish, bot.event = Mock(), Mock(), Mock()
        bot.logdir = ROOT/'logs'
        bot.wait = Mock(side_effect=[(None,'board',(None,10)),
                                    (Mock(),'settlement',(10,0,0)),(None,'again',None)])
        with patch('casino.games.roulette.bot.time.monotonic', side_effect=[0,1,2,65,66,67]):
            bot.run(1)
        self.assertEqual(bot.event.call_args.kwargs['rounds'],1)
        bot.finish.assert_called_once()
