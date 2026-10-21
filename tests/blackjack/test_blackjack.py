import math
from pathlib import Path
import tempfile
import shutil
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
from PIL import Image
from casino.games.blackjack.rules import hand, bonus, payout
from casino.games.blackjack.strategy import Strategy, DRAWS
from casino.games.blackjack.vision import BlackjackVision
from casino.games.blackjack.bot import BlackjackBot
from casino.common.paths import ROOT
from casino.common.vision import RecognitionError


class RulesTests(unittest.TestCase):
    def test_aces(self):
        self.assertEqual(hand(['AC','AH']), (2,False))
        self.assertEqual(hand(['AC','AH','9D']), (11,False))
        self.assertEqual(hand(['AC','AH','9D','KC']), (21,False))
        self.assertEqual(hand(['TC','9D','5S']), (24,False))
        self.assertEqual(hand(['2S','AD','3D','AS']), (7,False))
        self.assertEqual(hand(['2S','AD','3D']), (16,True))
        self.assertEqual(payout(['2S','AD','3D','AS'],17),0)

    def test_bonuses(self):
        for cards, rate in [(['AS','JS'],50),(['AD','QD'],10),(['AC','TH'],3),
                            (['7C','7D','7S'],100),(['AC','2D','3S','4H','2S','3C'],120),
                            (['AC','2D','3S','4H','2S','3C','2C'],250)]:
            self.assertEqual(bonus(cards),rate)
        self.assertEqual(bonus(['AC','5D','5S']),2)

    def test_settlement(self):
        self.assertEqual(payout(['TC','9D','5S'],25),0)
        self.assertEqual(payout(['TC','9D'],19),1)
        self.assertEqual(payout(['TC','9D'],22),2)
        self.assertEqual(payout(['AS','JS'],21),50)
        self.assertEqual(payout(['AS','JS'],21,False),1)
        self.assertEqual(payout(['AC','2D','3S','4H','2S','3C'],21),0)
        self.assertEqual(payout(['AC','2D','3S','4H','2S','3C','2C'],21),250)


class StrategyTests(unittest.TestCase):
    def test_multiple_aces_use_low_total_in_all_search_branches(self):
        s = Strategy()
        self.assertEqual(s.evaluate(['2S','AD','3D','AS'],'7D')['total'],7)
        self.assertNotEqual(s.dealer(7,2),((17,1.),))
        # Six-card 7 with two aces: every seventh draw avoids bust and wins.
        self.assertAlmostEqual(s.continuation(7,2,6,False,7),249)
        with patch.object(s,'stand_ev',side_effect=lambda total,*args:float(total)):
            expected = 2*sum(p*t for (_,p),t in zip(DRAWS,(7,18,19,20,21,12,13,14,15,16)))
            self.assertAlmostEqual(s.evaluate(['AD','5S'],'7D')['ev']['double'],expected)

    def test_dealer_probability(self):
        for threshold in (17,18):
            s = Strategy(threshold)
            for up in range(1,11):
                dist = s.dealer(up,up==1)
                self.assertAlmostEqual(sum(p for _,p in dist),1)
                self.assertTrue(all(threshold <= t <= 22 for t,_ in dist))

    def test_double_legality_and_terminal(self):
        s = Strategy()
        self.assertNotIn('double',s.evaluate(['5C','6D'],'6S',False)['ev'])
        self.assertNotIn('double',s.evaluate(['2C','3D','6S'],'6H')['ev'])
        self.assertEqual(s.evaluate(['AS','JS'],'6D')['action'],'stand')
        self.assertAlmostEqual(s.evaluate(['AS','JS'],'6D')['ev']['stand'],49)

    def test_six_cards_independent_oracle(self):
        s = Strategy()
        cards = ['2C','2D','2S','3C','3D','3S']  # Hard 15, no ace remains soft.
        # A seventh card wins unconditionally iff it doesn't bust.
        hit = sum(p*(249 if 15+v <= 21 else -1) for v,p in DRAWS)
        self.assertAlmostEqual(s.evaluate(cards,'9H')['ev']['hit'],hit)
        self.assertEqual(s.evaluate(cards,'9H')['action'],'hit')


class VisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = BlackjackVision()

    def sample(self,name):
        path = ROOT/'captures'/f'{name}.png'
        if not path.exists():
            self.skipTest('Development captures are not installed')
        with Image.open(path) as im:
            return im.copy()

    def test_hands(self):
        for name,cards,up in [('bj_007_ready',('AC','9C'),'2C'),
                               ('bj_021_ready',('4D','TH'),'QC'),
                               ('bj_022_hit',('4D','TH','6D'),'QC')]:
            im = self.sample(name)
            self.assertEqual(self.v.state(im),'hand')
            self.assertEqual(self.v.observation(im),(cards,up))

    def test_final_and_bet(self):
        self.assertEqual(self.v.final_hand(self.sample('bj_014_ready')),(('AC','9C'),22))
        self.assertEqual(self.v.bet(self.sample('bj_031_bet')),(1866,1))
        self.assertEqual(self.v.settlement(self.sample('bj_028_settle_stable')),(1,0,0))

    def test_animation_and_dialogues(self):
        self.assertEqual(self.v.state(self.sample('bj_006_hand')),'unknown')
        self.assertEqual(self.v.state(self.sample('bj_030_prompt')),'again')
        self.assertEqual(self.v.state(self.sample('bj_012_result')),'stand_dialog')
        with self.assertRaises(RecognitionError):
            self.v.observation(self.sample('bj_006_hand'))

    def test_unknown_frame(self):
        self.assertEqual(self.v.state(Image.new('RGB',(1280,720))),'unknown')

    def test_action_cursor(self):
        self.assertEqual(self.v.cursor(self.sample('bj_007_ready')),0)
        self.assertEqual(self.v.cursor(self.sample('bj_010_stand_selected')),1)

    def test_occluded_bust_retains_verified_cards(self):
        im = self.sample('bj_042_burst')
        cards = ('AD','2S','4S','9H','7S')
        self.assertEqual(self.v.final_hand(im,cards)[0],cards)
        with self.assertRaises(RecognitionError):
            self.v.final_hand(im)

    def test_live_recognition_regressions(self):
        self.assertEqual(self.v.observation(self.sample('bj_regression_club')),(('8S','6C'),'6S'))
        self.assertEqual(self.v.observation(self.sample('bj_regression_ace')),
                         (('8D','5C','2H','2D','AS'),'6S'))
        self.assertEqual(self.v.final_hand(self.sample('bj_regression_gray')),
                         (('AD','2S','4S','9H','7S'),2))
        self.assertEqual(self.v.bet(self.sample('bj_regression_2061')),(2061,1))

    def test_runtime_without_captures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT/'casino', root/'casino',
                            ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT/'assets',root/'assets')
            shutil.rmtree(root/'assets'/'states')
            self.sample('bj_022_hit').save(root/'sample.png')
            result = subprocess.run([sys.executable,'-c',
                'from casino.games.blackjack.vision import *; v=BlackjackVision(); '
                'assert v.observation(Image.open("sample.png")) == (("4D","TH","6D"),"QC")'],
                cwd=root,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_fifth_card_club_with_disconnected_stem(self):
        im = self.sample('bj_regression_fifth_club')
        known = ('4D','5S','2H','3C')
        self.assertEqual(self.v.state(im),'dialog')
        self.assertEqual(self.v.final_hand(im,known),(known+('8C',),10))
        self.assertEqual(self.v.final_hand(im),(known+('8C',),10))
        # A missing new card must still fail, even with the total and old cards.
        from PIL import ImageDraw
        ImageDraw.Draw(im).rectangle((910,340,965,400),fill='white')
        with self.assertRaises(RecognitionError):
            self.v.final_hand(im,known)

    def test_live_two_aces_count_as_seven(self):
        im = self.sample('bj_regression_two_aces')
        self.assertEqual(self.v.observation(im),(('2S','AD','3D','AS'),'7D'))
        im = self.sample('bj_regression_five_two_aces')
        self.assertEqual(self.v.observation(im),(('2S','AD','3D','AS','3C'),'7D'))

    def test_seven_card_bonus_settlement(self):
        self.assertEqual(self.v.settlement(self.sample('bj_regression_250')),(100,250,25000))
        self.assertEqual(payout(('2S','AD','3D','AS','3C','4S','6H'),18),250)

    def test_rotated_red_five_is_not_three(self):
        self.assertEqual(self.v.observation(self.sample('bj_regression_red_five')),
                         (('8H','7S','5H'),'QD'))

    def test_dealer_ace_displays_eleven(self):
        im = self.sample('bj_regression_dealer_ace')
        self.assertEqual(self.v.totals(im),(2,11,11))
        self.assertEqual(self.v.observation(im),(('6H','5H'),'AC'))

    def test_seven_card_edge_does_not_pollute_gray_total(self):
        im = self.sample('bj_regression_seven_bust')
        self.assertEqual(self.v.totals(im),(7,25,2))
        self.assertEqual(self.v.final_hand(im),
                         (('3C','2D','AH','8D','2S','AD','8C'),2))


class ControlTests(unittest.TestCase):
    def bot(self):
        b = BlackjackBot.__new__(BlackjackBot)
        b.strategy = Strategy()
        b.to_bet = Mock(return_value=(1000,1))
        b.set_bet = Mock(return_value=1000)
        b.press = Mock()
        b.finish = Mock()
        b.event = Mock()
        b.play_hand = Mock(return_value=dict(bet=1,received=0))
        return b

    def test_duration_rechecked_after_bet_adjustment(self):
        b = self.bot()
        with patch('casino.games.blackjack.bot.time.monotonic',side_effect=[0,0,61,62]):
            b.run(1,1)
        b.press.assert_not_called()
        b.finish.assert_called_once()

    def test_finishes_current_round(self):
        b = self.bot()
        b.to_bet.side_effect = [(1000,1),(999,1)]
        with patch('casino.games.blackjack.bot.time.monotonic',side_effect=[0,0,0,61,62]):
            b.run(1,1)
        b.play_hand.assert_called_once()
        b.finish.assert_called_once()

    def test_balance_mismatch_stops(self):
        b = self.bot()
        with patch('casino.games.blackjack.bot.time.monotonic',return_value=0):
            with self.assertRaisesRegex(RecognitionError,'Balance mismatch'):
                b.run(1,1)
        b.finish.assert_not_called()

    def test_insufficient_balance_and_invalid_duration(self):
        b = self.bot()
        b.to_bet.return_value = (1,1)
        b.run(1,100)
        b.press.assert_not_called()
        for duration in (0,-1,math.inf,math.nan):
            with self.assertRaises(ValueError):
                b.run(duration,1)

    def test_three_a_shortcut_checked_before_commit(self):
        b = self.bot()
        b.wait = Mock(side_effect=[(None,'bet',(1000,1)),(None,'bet',(1000,100))])
        self.assertEqual(BlackjackBot.set_bet(b,100),1000)
        self.assertEqual([c.args[0] for c in b.press.call_args_list],['a','a','a'])
        b.press.reset_mock()
        b.wait.side_effect = [(None,'bet',(1000,1)),(None,'bet',(1000,10))]
        with self.assertRaises(RecognitionError):
            BlackjackBot.set_bet(b,100)
        self.assertNotIn('enter',[c.args[0] for c in b.press.call_args_list])

    def test_decimal_cursor_returns_to_units(self):
        b = self.bot()
        b.wait = Mock(side_effect=[(None,'bet',x) for x in [(1000,1),(1000,100),(1000,100),(1000,99)]])
        self.assertEqual(BlackjackBot.set_bet(b,99),1000)
        self.assertEqual([c.args[0] for c in b.press.call_args_list],['a','a','a','d','d','s'])
        b.press.reset_mock()
        b.wait.side_effect = [(None,'bet',(1000,99)),(None,'bet',(1000,1))]
        BlackjackBot.set_bet(b,1)
        self.assertEqual([c.args[0] for c in b.press.call_args_list],['d','d','d'])

    def test_double_sevens_real_settlement(self):
        v = BlackjackVision()
        path = ROOT/'captures'/'bj_double_777.png'
        if not path.exists():
            self.skipTest('Development capture not installed')
        with Image.open(path) as im:
            self.assertEqual(v.settlement(im),(2,100,200))
        self.assertEqual(payout(['7S','7H','7D'],19)*2,200)

    def test_wait_requires_stable_frames(self):
        b = self.bot()
        b.game = Mock()
        b.game.grab.return_value = Image.new('RGB',(1280,720))
        b.vision = Mock()
        b.vision.state.return_value = 'hand'
        values = iter([('old',),None,('new',),('new',),('new',)])
        with patch('casino.games.blackjack.bot.time.sleep'):
            _,_,result = BlackjackBot.wait(b,{'hand'},lambda im,s:next(values))
        self.assertEqual(result,('new',))
        self.assertEqual(b.game.grab.call_count,5)

    def test_wait_logs_recognition_error_before_focus_loss(self):
        from casino.common.window import Stopped
        b = self.bot()
        b.game = Mock()
        im = Image.new('RGB',(1280,720))
        b.game.grab.side_effect = [im,im,Stopped('Game lost foreground focus')]
        b.vision = Mock()
        b.vision.state.return_value = 'dialog'
        predicate = Mock(side_effect=RecognitionError('Uncertain final hand'))
        with patch('casino.games.blackjack.bot.time.sleep'):
            with self.assertRaises(Stopped):
                BlackjackBot.wait(b,{'dialog'},predicate)
        b.event.assert_called_once_with('recognition_wait',state='dialog',
                                       reason='Uncertain final hand')


if __name__ == '__main__':
    unittest.main()
