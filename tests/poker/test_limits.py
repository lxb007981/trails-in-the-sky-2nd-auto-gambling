import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from casino.games.poker.bot import Bot

class LimitTests(unittest.TestCase):
    def make_bot(self, balances, payouts):
        bot = Bot.__new__(Bot)
        bot.wheel = True
        bot.to_bet = MagicMock(side_effect=[(None,(b,b-1)) for b in balances])
        bot.set_bet = MagicMock(side_effect=[balances[0]]+balances[:-1])
        bot.play_hand = MagicMock(side_effect=[{'payout':p} for p in payouts])
        bot.event, bot.press, bot.wait = MagicMock(), MagicMock(), MagicMock()
        bot.wait.return_value = (MagicMock(),'menu')
        bot.logdir = Path('unused_test_directory')
        return bot

    def test_losses_do_not_stop_run(self):
        bot = self.make_bot([100,90,80],[0,0])
        with patch('casino.games.poker.bot.time.monotonic',side_effect=[0,0,0,30,30,60,61]):
            bot.run(minutes=1,bet=10)
        self.assertEqual(bot.play_hand.call_count,2)
        self.assertEqual(bot.event.call_args.kwargs['stop_reason'],'duration_reached')
        self.assertEqual(bot.event.call_args.kwargs['net'],-20)

    def test_gains_do_not_stop_run(self):
        bot = self.make_bot([100,190,280],[10,10])
        with patch('casino.games.poker.bot.time.monotonic',side_effect=[0,0,0,30,30,60,61]):
            bot.run(minutes=1,bet=10)
        self.assertEqual(bot.play_hand.call_count,2)
        self.assertEqual(bot.event.call_args.kwargs['net'],180)

    def test_insufficient_balance(self):
        bot = self.make_bot([15,5],[0])
        with patch('casino.games.poker.bot.time.monotonic',return_value=0):
            bot.run(minutes=1,bet=10)
        self.assertEqual(bot.play_hand.call_count,1)
        self.assertEqual(bot.event.call_args.kwargs['stop_reason'],'insufficient_balance')

    def test_deadline_during_bet_setup(self):
        bot = self.make_bot([100],[])
        bot.set_bet.side_effect = [100,100]
        with patch('casino.games.poker.bot.time.monotonic',side_effect=[0,59,60,61]):
            bot.run(minutes=1)
        bot.play_hand.assert_not_called()
        self.assertEqual(bot.press.call_args_list,[unittest.mock.call('escape'),unittest.mock.call('enter')])

    def test_current_hand_finishes_after_deadline(self):
        bot = self.make_bot([100,110],[2])
        with patch('casino.games.poker.bot.time.monotonic',side_effect=[0,59,59,75,76]):
            bot.run(minutes=1)
        self.assertEqual(bot.play_hand.call_count,1)
        self.assertEqual(bot.event.call_args.kwargs['final_balance'],110)

    def test_no_default_round_limit(self):
        bot = self.make_bot(list(range(100,107)),[2]*6)
        with patch('casino.games.poker.bot.time.monotonic',side_effect=[0]+[0]*12+[60,61]):
            bot.run(minutes=1,bet=1)
        self.assertEqual(bot.play_hand.call_count,6)

    def test_invalid_duration_sends_no_input(self):
        for minutes in [0,-1,float('inf'),float('nan')]:
            with self.subTest(minutes=minutes):
                bot = self.make_bot([100],[])
                with self.assertRaises(ValueError):
                    bot.run(minutes=minutes)
                bot.to_bet.assert_not_called()

if __name__=='__main__':
    unittest.main()
