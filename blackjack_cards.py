"""Locate upright card corners after undoing the table's 45 degree rotation."""
import cv2
import numpy as np
from PIL import Image
from vision import match, RecognitionError


def rotated(im):
    return np.array(im.convert('RGB').rotate(-45, resample=Image.Resampling.BICUBIC, expand=True))


def read_cards(im, templates):
    a = rotated(im)
    mask = ((a.max(2) < 125) | ((a[:,:,0] > 100) & (a[:,:,1] < 90) & (a[:,:,2] < 110))).astype(np.uint8)
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    cards = []
    for sx, sy, sw, sh, area in stats[1:]:
        sx, sy, sw, sh = map(int, (sx, sy, sw, sh))
        if not (450 < sx < 1100 and 300 < sy < 1200 and 7 <= sw <= 20 and 9 <= sh <= 20):
            continue
        parts = [s for s in stats[1:] if sy-30 <= s[1] < sy-10 and
                 s[1]+s[3] <= sy+2 and sx-12 <= s[0] <= sx+15 and
                 15 <= s[3] <= 29 and 4 <= s[2] <= 28]
        if not parts:
            continue
        rx = min(int(s[0]) for s in parts)
        ry = min(int(s[1]) for s in parts)
        ex = max(int(s[0]+s[2]) for s in parts)
        ey = max(int(s[1]+s[3]) for s in parts)
        if ex-rx > 30:
            continue
        background = a[ry-3:sy+sh+3, rx-3:max(ex,sx+sw)+4]
        if float((background.min(2) > 210).mean()) < .55:
            continue
        # Rotation/thresholding can disconnect the tiny stem of a club or
        # spade. Include only a small, centered component directly below the
        # symbol; matching an incomplete club can make it resemble a spade.
        bottom = sy+sh
        stems = [s for s in stats[1:] if bottom <= s[1] <= bottom+1 and
                 1 <= s[2] <= 4 and 1 <= s[3] <= 4 and s[4] <= 12 and
                 sx <= s[0] and s[0]+s[2] <= sx+sw and
                 abs((s[0]+s[2]/2)-(sx+sw/2)) <= sw/4]
        if len(stems) == 1:
            bottom = int(stems[0][1]+stems[0][3])
        try:
            rank, rs = match(mask[ry:ey, rx:ex], templates['ranks'], .18, .018)
            patch = a[sy:bottom,sx:sx+sw].astype(int)
            red = int(((patch[:,:,0]-patch[:,:,1]>50)&(patch[:,:,1]<120)).sum()) > 8
            allowed = 'DH' if red else 'CS'
            suit, ss = match(mask[sy:bottom, sx:sx+sw],
                             {k:v for k,v in templates['suits'].items() if k in allowed}, .14, .008)
        except RecognitionError:
            continue
        cards.append(dict(card=rank+suit, x=rx, y=ry, score=[rs, ss]))
    player = sorted([c for c in cards if c['y'] > 730], key=lambda c:c['x'])
    dealer = sorted([c for c in cards if c['y'] < 700], key=lambda c:c['x'])
    return player, dealer
