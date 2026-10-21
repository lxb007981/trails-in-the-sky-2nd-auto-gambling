"""Seeded single-deck simulation; an estimate under documented rule assumptions."""
import argparse
from collections import Counter
import json
import math
import random
from casino.games.blackjack.rules import RANKS, hand, payout
from casino.games.blackjack.strategy import Strategy


def simulate(rounds=100000, seed=20261022, dealer_stand=17, special_ties=True):
    if rounds < 2:
        raise ValueError('At least two rounds are required')
    rng = random.Random(seed)
    strategy = Strategy(dealer_stand,special_ties)
    full = [r+s for r in RANKS for s in 'CDHS']
    net = squared = invested = 0
    rates, actions = Counter(), Counter()
    for _ in range(rounds):
        deck = rng.sample(full,len(full))
        player, dealer = [deck.pop(),deck.pop()], [deck.pop(),deck.pop()]
        stake = 1
        while hand(player)[0] < 21 and len(player) < 7:
            action = strategy.evaluate(player,dealer[0])['action']
            actions[action] += 1
            if action == 'stand':
                break
            player.append(deck.pop())
            if action == 'double':
                stake = 2
                break
        if hand(player)[0] <= 21 and len(player) < 7:
            while hand(dealer)[0] < dealer_stand:
                dealer.append(deck.pop())
        rate = payout(player,hand(dealer)[0],special_ties)
        gain = stake*(rate-1)
        rates[rate] += 1
        net += gain
        squared += gain*gain
        invested += stake
    mean = net/rounds
    error = math.sqrt((squared-rounds*mean*mean)/(rounds-1)/rounds)
    return dict(rounds=rounds,seed=seed,model='fresh_52_card_deck_each_round',
                policy='independent_draw_expectimax',dealer_stand=dealer_stand,special_ties=special_ties,
                mean_net_per_initial_bet=mean,approx_95_percent_interval=[mean-1.96*error,mean+1.96*error],
                total_staked=invested,rates=dict(rates),actions=dict(actions),
                caveat='Simulation uses the displayed fresh-deck, dealer and tie assumptions; not measured game earnings.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rounds',type=int,default=100000)
    p.add_argument('--seed',type=int,default=20261022)
    p.add_argument('--dealer-stand',type=int,choices=(17,18),default=17)
    p.add_argument('--ordinary-special-ties',action='store_true')
    args = p.parse_args()
    print(json.dumps(simulate(args.rounds,args.seed,args.dealer_stand,not args.ordinary_special_ties),indent=2))
