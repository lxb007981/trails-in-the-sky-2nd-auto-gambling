"""Conservative screenshot recognition using locally collected glyphs."""
from pathlib import Path
import json
from functools import lru_cache
import cv2
import numpy as np
from PIL import Image

from casino.common.paths import ROOT, ASSETS
from casino.common.vision import RecognitionError, rgb, crop, ink, normalize, segments, match
from casino.common.templates import load_templates
XS = [280, 418, 555, 693, 830]

def rank_mask(im, i):
    mask = ink(crop(im, (XS[i], 354, XS[i]+38, 381)))
    # The rounded card corner contributes dark pixels at the crop boundary.
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask,8)
    for label in range(1,n):
        x,y,w,h,area = stats[label]
        if x==0 or y==0 or x+w==mask.shape[1] or area<3:
            mask[labels==label] = 0
    return mask

def suit_mask(im, i):
    mask = ink(crop(im, (XS[i], 381, XS[i]+25, 401)))
    # Q's descending stroke may enter this crop above the suit. Keep the suit's
    # main connected component instead of normalizing both disconnected marks.
    n,labels,stats,_ = cv2.connectedComponentsWithStats(mask,8)
    if n>1:
        largest = 1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))
        mask = (labels==largest).astype(np.uint8)
    return mask

class Vision:
    def __init__(self):
        self.templates = load_templates(ASSETS)
        self.refs = {}
        try:
            folder = ASSETS / 'states'
            manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
            for entry in manifest:
                name, filename, box = entry['name'], entry['file'], entry['box']
                if Path(filename).name != filename:
                    raise ValueError('Invalid state asset filename')
                x1,y1,x2,y2 = box
                if not (0 <= x1 < x2 <= 1280 and 0 <= y1 < y2 <= 720):
                    raise ValueError('Invalid state asset coordinates')
                with Image.open(folder/filename) as im:
                    if im.size != (x2-x1,y2-y1):
                        raise ValueError(f'State asset size mismatch: {filename}')
                    ref = rgb(im).astype(float)
                self.refs.setdefault(name, []).append((box, ref))
            expected = {'menu','bet','bet_prompt','deposit','cancel','win_dialog',
                        'loss_dialog','hand','settlement','dialog_panel'}
            if set(self.refs) != expected:
                raise ValueError('Missing or unexpected state references')
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise RecognitionError(f'Invalid state assets; run python -m tools.build_poker_assets: {e}') from e

    def score(self, im, name):
        return min(float(np.mean(np.abs(crop(im, box).astype(float)-ref)))/255
                   for box, ref in self.refs[name])

    def state(self, im):
        if self.score(im, 'bet') < .04:
            return 'bet'
        if self.score(im, 'settlement') < .04:
            return 'settlement'
        if self.score(im, 'menu') < .05:
            return 'menu'
        if self.score(im, 'hand') < .04:
            # Check the white top of every card, away from rank/suit glyphs.
            # Face-card artwork darkens when enlarged by cursor selection;
            # its brightness cannot distinguish a dealt hand from animation.
            # HOLD lifts cards, so allow artwork to enter part of each patch.
            if all(np.mean(np.all(crop(im, (x+70,350,x+100,370)) > 200,
                                  axis=2)) > .35 for x in XS):
                return 'hand'
        for name in ('bet_prompt', 'deposit', 'cancel', 'win_dialog', 'loss_dialog'):
            if self.score(im, name) < .035:
                return name
        if (self.score(im, 'dialog_panel') < .03 and np.mean(crop(im,(320,345,400,360)))>220
                and int(ink(crop(im,(250,64,385,86))).sum())>150):
            return 'result'
        return 'unknown'

    def hand(self, im):
        result, scores = [], []
        for i in range(5):
            r, rs = match(rank_mask(im, i), self.templates['ranks'])
            suit_patch = crop(im,(XS[i],381,XS[i]+25,401)).astype(int)
            is_red = int(np.sum((suit_patch[:,:,0]-suit_patch[:,:,1]>50)&(suit_patch[:,:,1]<170)))>8
            allowed = 'DH' if is_red else 'CS'
            suit_templates = {k:v for k,v in self.templates['suits'].items() if k in allowed}
            s, ss = match(suit_mask(im, i), suit_templates, threshold=.14, margin=.01)
            result.append(r+s)
            scores.append([rs, ss])
        if len(set(result)) != 5:
            raise RecognitionError(f'Duplicate cards: {result}')
        return result, scores

    def number(self, im, box):
        chunks = segments(ink(crop(im, box)))
        if not chunks:
            raise RecognitionError('No digits')
        @lru_cache(None)
        def decode(shape, data):
            chunk = np.frombuffer(data, dtype=np.uint8).reshape(shape)
            try:
                return match(chunk, self.templates['digits'], .20, .035)
            except RecognitionError as original:
                # Serif digits may overlap in the column projection. Only
                # split rejected wide chunks; keep the original confidence gates.
                if chunk.shape[1] < 15:
                    raise original
                options = {}
                for x in range(5, chunk.shape[1]-4):
                    left, right = chunk[:,:x], chunk[:,x:]
                    try:
                        a, sa = decode(left.shape, left.tobytes())
                        b, sb = decode(right.shape, right.tobytes())
                    except RecognitionError:
                        continue
                    text = a+b
                    score = (sa*len(a)+sb*len(b))/len(text)
                    options[text] = min(options.get(text, 1), score)
                ranked = sorted((score, text) for text, score in options.items())
                if not ranked or (len(ranked)>1 and ranked[1][0]-ranked[0][0]<.035):
                    raise original
                return ranked[0][1], ranked[0][0]
        return int(''.join(decode(c.shape, c.tobytes())[0] for c in chunks))

    def dialogue_ready(self, im):
        # The gold continuation triangle appears only after text finishes typing.
        region = crop(im,(280,84,850,144))
        gold = (region[:,:,0]>160)&(region[:,:,1]>110)&(region[:,:,2]<130)
        return int(gold.sum())>=15

    def start_selected(self, im):
        region = crop(im,(595,308,685,331))
        yellow = (region[:,:,0]>190)&(region[:,:,1]>160)&(region[:,:,2]<130)
        return float(yellow.mean())>.4

    def balance(self, im):
        return self.number(im, (620,255,775,280))

    def remaining(self, im):
        return self.number(im, (620,436,775,461))

    def holds(self, im):
        # HOLD letters are bright gold/white above each held card.
        a = rgb(im)
        return [int(np.sum((a[281:311,x+15:x+120,0]>180) &
                           (a[281:311,x+15:x+120,1]>160) &
                           (a[281:311,x+15:x+120,2]<160))) > 100 for x in XS]

    def cursor(self, im):
        a = rgb(im)
        # Gold frame is horizontal across the top of the focused card.
        strengths = []
        for x in XS:
            region = a[339:363,x:x+125]
            gold = (region[:,:,0]>155)&(region[:,:,1]>105)&(region[:,:,2]<100)
            strengths.append(int(gold.sum(axis=1).max()))
        selected = [i for i, strength in enumerate(strengths) if strength > 65]
        if len(selected) == 1:
            return selected[0]
        if self.score(im, 'hand') < .04:
            # Red fill confirms that Change is selected.
            region = a[513:538,1150:1220]
            if np.mean((region[:,:,0]>100)&(region[:,:,1]<70)) > .4:
                return 5
        raise RecognitionError(f'Unknown cursor: {strengths}')

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('image')
    args = p.parse_args()
    im = Image.open(args.image)
    v = Vision()
    state = v.state(im)
    out = {'state': state}
    if state == 'hand':
        out.update(hand=v.hand(im), holds=v.holds(im), cursor=v.cursor(im))
    elif state == 'bet':
        out.update(balance=v.balance(im), remaining=v.remaining(im))
    print(json.dumps(out))
