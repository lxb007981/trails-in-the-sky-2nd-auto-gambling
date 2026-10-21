"""Cached expectimax, explicitly using an independent-draw approximation.

The game has 52 cards. This model uses rank probabilities 1/13 (A..9),
4/13 (ten-valued), not card counting or a claim of exact single-deck optimality.
Special initial suits are evaluated by the rules module; future bonuses depend
on count and sevens. Dealer threshold and special ties are configurable.
"""
from functools import lru_cache
from blackjack_rules import hand, bonus, value, total_from_low

DRAWS = tuple((n, (4 if n == 10 else 1)/13) for n in range(1,11))


class Strategy:
    def __init__(self, dealer_stand=17, special_ties=True):
        if dealer_stand not in (17,18):
            raise ValueError('Dealer stand threshold must be 17 or 18')
        self.dealer_stand = dealer_stand
        self.special_ties = special_ties

    @lru_cache(maxsize=None)
    def dealer(self, low, ace):
        total = total_from_low(low, ace)[0]
        if total > 21:
            return ((22, 1.),)
        if total >= self.dealer_stand:
            return ((total, 1.),)
        out = {}
        for v, probability in DRAWS:
            for end, p in self.dealer(low+v, min(2, ace + (v == 1))):
                out[end] = out.get(end,0) + probability*p
        return tuple(sorted(out.items()))

    def stand_ev(self, total, rate, n, up):
        if total > 21:
            return -1.
        if n >= 7:
            return rate-1.
        result = -1.
        for end, p in self.dealer(up, up == 1):
            if end > 21 or total > end:
                result += p*rate
            elif total == end:
                result += p*(rate if rate > 2 and self.special_ties else 1)
        return result

    @lru_cache(maxsize=None)
    def continuation(self, low, ace, n, sevens, up):
        total = total_from_low(low, ace)[0]
        rate = 250 if n >= 7 else 120 if n == 6 else 100 if n == 3 and sevens else 2
        stand = self.stand_ev(total, rate, n, up)
        if total >= 21 or n >= 7:
            return stand
        hit = sum(p*self.continuation(low+v, min(2, ace + (v == 1)), n+1, sevens and v == 7, up)
                  for v,p in DRAWS)
        return max(stand, hit)

    def evaluate(self, cards, dealer_card, can_double=True):
        total, _ = hand(cards)
        low, ace = sum(value(c) for c in cards), sum(c[0]=='A' for c in cards)
        up = value(dealer_card)
        n, sevens = len(cards), all(c[0]=='7' for c in cards)
        ev = {'stand': self.stand_ev(total, bonus(cards), n, up)}
        if total < 21 and n < 7:
            ev['hit'] = sum(p*self.continuation(low+v, min(2, ace + (v == 1)), n+1, sevens and v == 7, up)
                            for v,p in DRAWS)
            if n == 2 and can_double:
                def double(v):
                    t = total_from_low(low+v, min(2, ace + (v == 1)))[0]
                    rate = 100 if sevens and v == 7 else 2
                    return 2*self.stand_ev(t,rate,3,up)
                ev['double'] = sum(p*double(v) for v,p in DRAWS)
        return {'action':max(ev, key=ev.get), 'ev':ev, 'total':total,
                'model':'independent_draws', 'dealer_stand':self.dealer_stand,
                'special_ties':self.special_ties}
