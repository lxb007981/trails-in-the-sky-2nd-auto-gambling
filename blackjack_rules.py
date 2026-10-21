"""Rules transcribed from the game's five help pages and payout table."""
RANKS = 'A23456789TJQK'
RATES = {0, 1, 2, 3, 10, 50, 100, 120, 250}


def value(card):
    if card[0] not in RANKS:
        raise ValueError(f'Invalid card: {card}')
    return 1 if card[0] == 'A' else min(10, RANKS.index(card[0])+1)


def total_from_low(low, aces):
    # Live 2S, AD, 3D, AS is 7, not standard-blackjack soft 17.
    # The game uses the high ace value only with a single ace.
    soft = aces == 1 and low+10 <= 21
    return low + 10*soft, soft


def hand(cards):
    return total_from_low(sum(value(c) for c in cards),
                          sum(c[0] == 'A' for c in cards))


def bonus(cards):
    total, _ = hand(cards)
    if total > 21:
        return 0
    if len(cards) >= 7:
        return 250
    if len(cards) == 6:
        return 120
    if len(cards) == 3 and all(c[0] == '7' for c in cards):
        return 100
    if len(cards) == 2 and total == 21:
        if set(cards) == {'AS', 'JS'}:
            return 50
        if set(cards) == {'AD', 'QD'}:
            return 10
        return 3
    return 2


def payout(cards, dealer_total, special_ties=True):
    total, _ = hand(cards)
    rate = bonus(cards)
    if total > 21:
        return 0
    if len(cards) >= 7:
        return rate
    if dealer_total > 21 or total > dealer_total:
        return rate
    if total == dealer_total:
        return rate if special_ties and rate > 2 else 1
    return 0
