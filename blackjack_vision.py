"""Blackjack-only state and card recognition; uncertain frames never authorize input."""
import json
import cv2
import numpy as np
from PIL import Image
from vision import ROOT, crop, rgb, segments, match, ink, RecognitionError, Vision
from blackjack_cards import read_cards
from blackjack_rules import hand


class BlackjackVision:
    def __init__(self):
        self.base = Vision()
        self.templates = self.base.templates
        folder = ROOT/'assets'/'blackjack'
        for path in folder.glob('*_rotated.npy'):
            self.templates['suits'].setdefault(path.stem.split('_')[0],[]).append(np.load(path))
        for path in folder.glob('*_rank.npy'):
            self.templates['ranks'].setdefault(path.stem.split('_')[0],[]).append(np.load(path))
        self.white_digits = {k:list(v) for k,v in self.templates['digits'].items()}
        for path in folder.glob('*_white.npy'):
            self.white_digits.setdefault(path.stem.split('_')[0],[]).append(np.load(path))
        self.refs = {}
        for entry in json.loads((folder/'manifest.json').read_text(encoding='utf-8')):
            with Image.open(folder/entry['file']) as im:
                self.refs[entry['name']] = (entry['box'], rgb(im).astype(np.float32))
        with Image.open(folder/'triangle.png') as im:
            self.triangle = rgb(im)

    def score(self, im, name):
        box, ref = self.refs[name]
        return float(np.abs(crop(im,box).astype(float)-ref).mean()/255)

    def dialogue_ready(self, im):
        if self.score(im,'dialog_panel') > .035:
            return False
        scores = cv2.matchTemplate(crop(im,(245,83,950,143)), self.triangle, cv2.TM_SQDIFF_NORMED)
        return float(scores.min()) < .18

    def cursor(self, im):
        strengths = []
        for y in (198,250,301):
            a = crop(im,(1160,y,1260,y+12))
            strengths.append(float(((a[:,:,0]>110)&(a[:,:,1]<95)&(a[:,:,2]<80)).mean()))
        selected = [i for i,s in enumerate(strengths) if s > .25]
        if len(selected) != 1:
            raise RecognitionError(f'Uncertain action selection: {strengths}')
        return selected[0]

    def state(self, im):
        if self.score(im,'bet') < .035:
            return 'bet'
        if self.score(im,'menu') < .035:
            return 'menu'
        if self.score(im,'settlement') < .035:
            return 'settlement' if self.dialogue_ready(im) else 'animation'
        if self.dialogue_ready(im):
            for state in ('bet_prompt','again','cancel','deposit','open','stand_dialog'):
                if self.score(im,state) < .035:
                    return state
            return 'dialog'
        # Menu labels and actual selectable red fill must both be present.
        if min(self.score(im,'action_hit'),self.score(im,'action_stand')) < .035:
            return 'hand'
        # Double Down selected: Hit and Stand have moved to the same grey x.
        a = crop(im,(1160,301,1260,313))
        if float(((a[:,:,0]>110)&(a[:,:,1]<95)&(a[:,:,2]<80)).mean()) > .25:
            return 'hand'
        return 'unknown'

    def number(self, im, box, kind='white'):
        a = crop(im,box).astype(int)
        if kind == 'black':
            mask = ink(crop(im,box))
        elif kind == 'white':
            mask = a.min(2)>180
        elif kind == 'cyan':
            mask = (a[:,:,0]<200)&(a[:,:,1]>180)&(a[:,:,2]>180)&(a[:,:,2]-a[:,:,0]>25)
        else:
            mask = (a[:,:,0]>210)&(a[:,:,1]>100)&(a[:,:,1]<195)&(a[:,:,2]>120)&(a[:,:,0]-a[:,:,1]>35)
        if kind in ('cyan','pink') and int(mask.sum()) < 10:
            # Bust totals change from pink/cyan to neutral grey.
            mask = (a.min(2)>160)&(a.max(2)-a.min(2)<20)
            # With seven cards a white card edge can enter the total's crop.
            # Digits have padding on every side; discard boundary-connected
            # background instead of splitting it into spurious digits.
            _,labels,stats,_ = cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
            for index,(x,y,width,height,_) in enumerate(stats[1:],1):
                if x == 0 or y == 0 or x+width == mask.shape[1] or y+height == mask.shape[0]:
                    mask[labels == index] = False
        chunks = segments(mask.astype(np.uint8))
        if not chunks:
            raise RecognitionError(f'Missing {kind} digits at {box}')
        decoded = {}
        def decode(chunk):
            key = chunk.shape, chunk.tobytes()
            if key not in decoded:
                try:
                    decoded[key] = compute(chunk)
                except RecognitionError:
                    decoded[key] = None
            if decoded[key] is None:
                raise RecognitionError(f'Uncertain {kind} digit sequence at {box}')
            return decoded[key]
        def compute(chunk):
            try:
                label,score = match(chunk,self.white_digits if kind == 'white' else self.templates['digits'],.22,.025)
                return label,score
            except RecognitionError as original:
                # Serif digits such as 20 can touch in the column projection.
                # Split only rejected wide chunks, with confident component
                # matches and a unique best string; never relax glyph thresholds.
                if chunk.shape[1] < 15:
                    raise original
                options = {}
                for x in range(5,chunk.shape[1]-4):
                    try:
                        left,ls = decode(chunk[:,:x])
                        right,rs = decode(chunk[:,x:])
                        text = left+right
                        score = (ls*len(left)+rs*len(right))/len(text)
                        options[text] = min(options.get(text,1),score)
                    except RecognitionError:
                        continue
                ranked = sorted((score,text) for text,score in options.items())
                if not ranked or (len(ranked)>1 and ranked[1][0]-ranked[0][0]<.025):
                    raise original
                return ranked[0][1],ranked[0][0]
        return int(''.join(decode(c)[0] for c in chunks))

    def totals(self, im):
        return (self.number(im,(555,648,588,683),'cyan'),
                self.number(im,(684,648,737,683),'cyan'),
                self.number(im,(684,38,737,74),'pink'))

    def observation(self, im):
        player, dealer = read_cards(im,self.templates)
        cards = tuple(c['card'] for c in player)
        n, total, up = self.totals(im)
        if len(cards) != n or not 2 <= n <= 7 or hand(cards)[0] != total:
            raise RecognitionError(f'Player cards/count/total disagree: {cards}, {n}, {total}')
        if len(dealer) != 1 or hand((dealer[0]['card'],))[0] != up:
            raise RecognitionError(f'Dealer upcard/total disagree: {dealer}, {up}')
        if len(set(cards+(dealer[0]['card'],))) != len(cards)+1:
            raise RecognitionError('Duplicate card in a single 52-card deck')
        return cards, dealer[0]['card']

    def final_hand(self, im, known=()):
        player, _ = read_cards(im,self.templates)
        cards = tuple(c['card'] for c in player)
        n, total, dealer_total = self.totals(im)
        if len(cards) != n and known:
            # WIN/BURST graphics can hide an older card corner. Retain only
            # previously verified cards; newly exposed cards still need reading.
            new = tuple(c for c in cards if c not in known)
            candidate = tuple(known)+new
            if cards and len(candidate) == n and set(cards).issubset(candidate):
                cards = candidate
        if len(cards) != n or not 2 <= n <= 7 or hand(cards)[0] != total or len(set(cards)) != n:
            raise RecognitionError(f'Uncertain final hand: {cards}, {n}, {total}')
        return cards, dealer_total

    def bet(self, im):
        balance = self.number(im,(620,255,775,280),'black')
        remaining = self.number(im,(620,436,775,461),'black')
        amount = balance-remaining
        if not 1 <= amount <= 100 or remaining < 0:
            raise RecognitionError(f'Invalid bet: balance={balance}, remaining={remaining}')
        return balance, amount

    def settlement(self, im):
        result = tuple(self.number(im,box) for box in (
            (435,472,520,500),(600,472,700,500),(770,472,914,500)))
        bet, rate, received = result
        if bet*rate != received:
            raise RecognitionError(f'Settlement is not stable: {result}')
        return result

    def start_selected(self, im):
        return self.base.start_selected(im)
