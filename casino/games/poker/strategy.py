"""Exact single-draw strategy for the observed Trails payout table."""
from itertools import combinations, chain
from math import comb
from pathlib import Path
import numpy as np
from casino.common.paths import ROOT

RANKS = '23456789TJQKA'
SUITS = 'CDHS'
PAYOUTS = np.array([0, 2, 3, 4, 8, 10, 15, 50, 100, 1000], dtype=np.uint16)
NAMES = ['no_pair', 'one_pair', 'two_pair', 'three_kind', 'straight',
         'flush', 'full_house', 'four_kind', 'straight_flush', 'royal_flush']

def parse_card(s):
    s = s.upper().replace('10', 'T')
    if len(s) != 2 or s[0] not in RANKS or s[1] not in SUITS:
        raise ValueError(f'Invalid card: {s}')
    return RANKS.index(s[0]) * 4 + SUITS.index(s[1])

def card_name(n):
    return RANKS[n // 4] + SUITS[n % 4]

def categories(hands, wheel=True):
    """Vectorized five-card classification, cards encoded rank*4+suit."""
    hands = np.asarray(hands, dtype=np.uint8).reshape(-1, 5)
    ranks = np.sort(hands // 4, axis=1)
    suits = hands % 4
    pairs = np.zeros(len(hands), np.uint8)
    for i, j in combinations(range(5), 2):
        pairs += ranks[:, i] == ranks[:, j]
    out = np.zeros(len(hands), np.uint8)
    for n, category in [(1, 1), (2, 2), (3, 3), (4, 6), (6, 7)]:
        out[pairs == n] = category
    straight = (pairs == 0) & (ranks[:, 4] - ranks[:, 0] == 4)
    if wheel:
        straight |= np.all(ranks == [0, 1, 2, 3, 12], axis=1)
    flush = np.all(suits == suits[:, :1], axis=1)
    out[straight] = 4
    out[flush] = 5
    out[straight & flush] = 8
    out[straight & flush & (ranks[:, 0] == 8)] = 9
    return out

class Strategy:
    """Group every possible final hand by its intersection with the initial hand.

    Each of the 32 groups is exactly the replacement outcomes for one hold mask,
    assuming the five initially dealt cards cannot be drawn again.
    """
    def __init__(self, cache_dir=None, wheel=True):
        cache_dir = Path(cache_dir or ROOT / 'cache')
        cache_dir.mkdir(exist_ok=True)
        path = cache_dir / 'all_hands_v1.npy'
        if not path.exists():
            hands = np.fromiter(chain.from_iterable(combinations(range(52), 5)),
                                dtype=np.uint8, count=comb(52, 5)*5).reshape(-1, 5)
            np.save(path, hands)
        self.hands = np.load(path, mmap_mode='r')
        values_path = cache_dir / f'payouts_v1_wheel_{int(wheel)}.npy'
        if not values_path.exists():
            values = np.empty(len(self.hands), np.uint16)
            for start in range(0, len(values), 100000):
                stop = start + 100000
                values[start:stop] = PAYOUTS[categories(self.hands[start:stop], wheel)]
            np.save(values_path, values)
        self.values = np.load(values_path, mmap_mode='r')

    def evaluate(self, cards):
        hand = [parse_card(x) if isinstance(x, str) else int(x) for x in cards]
        if len(hand) != 5 or len(set(hand)) != 5 or not all(0 <= c < 52 for c in hand):
            raise ValueError('Expected five distinct cards')
        bits = np.zeros(52, np.uint8)
        for i, card in enumerate(hand):
            bits[card] = 1 << i
        masks = np.zeros(len(self.hands), np.uint8)
        for col in range(5):
            masks |= bits[self.hands[:, col]]
        counts = np.bincount(masks, minlength=32)
        expected_counts = np.array([comb(47, 5-m.bit_count()) for m in range(32)])
        if not np.array_equal(counts, expected_counts):
            raise RuntimeError('Strategy cache/count mismatch')
        sums = np.bincount(masks, weights=self.values, minlength=32)
        ev = sums / counts
        # Prefer retaining more cards when expected payouts are tied.
        best = max(range(32), key=lambda m: (ev[m], m.bit_count()))
        return {'mask': best, 'hold': [i for i in range(5) if best & (1 << i)],
                'expected_return': float(ev[best]), 'all_ev': ev.tolist()}

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('cards', nargs=5)
    p.add_argument('--no-wheel', action='store_true')
    args = p.parse_args()
    import json
    print(json.dumps(Strategy(wheel=not args.no_wheel).evaluate(args.cards), indent=2))
