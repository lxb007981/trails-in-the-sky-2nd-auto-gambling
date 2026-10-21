import unittest
from itertools import combinations
import numpy as np
from casino.games.poker.strategy import Strategy, categories, parse_card, PAYOUTS

class PokerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.strategy = Strategy()

    def test_all_hand_category_counts(self):
        counts = np.zeros(10,dtype=np.int64)
        for start in range(0,len(self.strategy.hands),100000):
            counts += np.bincount(categories(self.strategy.hands[start:start+100000]),minlength=10)
        np.testing.assert_array_equal(counts,[1302540,1098240,123552,54912,10200,5108,3744,624,36,4])

    def test_wheel_and_royal(self):
        hands = [[parse_card(c) for c in s.split()] for s in
                 ['AS 2D 3C 4H 5S','AS 2S 3S 4S 5S','TS JS QS KS AS','AH AD AC AS 2D']]
        self.assertEqual(categories(hands).tolist(),[4,8,9,7])
        self.assertEqual(categories(hands,wheel=False).tolist(),[0,5,9,7])

    def test_observed_pair_and_two_pairs(self):
        self.assertEqual(self.strategy.evaluate('2S 5H 3D 3H 6H'.split())['hold'],[2,3])
        self.assertEqual(self.strategy.evaluate('TS 4D 2H 4C 2C'.split())['hold'],[1,2,3,4])
        self.assertEqual(self.strategy.evaluate('TS JS QS KS AS'.split())['hold'],[0,1,2,3,4])

    def test_ev_against_direct_draw_enumeration(self):
        hand = [parse_card(c) for c in 'AS AD 7H 8H 9H'.split()]
        remaining = [c for c in range(52) if c not in hand]
        result = self.strategy.evaluate(hand)
        for mask in (7,15,23,30,31):
            held = [c for i,c in enumerate(hand) if mask & (1<<i)]
            outcomes = [held+list(draw) for draw in combinations(remaining,5-len(held))]
            direct = float(np.mean(PAYOUTS[categories(outcomes)]))
            self.assertAlmostEqual(result['all_ev'][mask],direct,places=12)

    def test_duplicate_input_rejected(self):
        with self.assertRaises(ValueError):
            self.strategy.evaluate('AS AS 3D 4D 5D'.split())

if __name__=='__main__':
    unittest.main()
