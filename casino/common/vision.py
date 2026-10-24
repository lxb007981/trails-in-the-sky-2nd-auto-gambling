"""Shared image and glyph operations; no game-specific state references."""
import cv2
import numpy as np
from PIL import Image

class RecognitionError(RuntimeError):
    pass

def rgb(im):
    return np.asarray(im.convert('RGB')) if isinstance(im, Image.Image) else im

def crop(im, box):
    x1, y1, x2, y2 = box
    return rgb(im)[y1:y2, x1:x2]

def ink(im):
    return (cv2.cvtColor(rgb(im), cv2.COLOR_RGB2GRAY) < 165).astype(np.uint8)

def normalize(mask):
    ys, xs = np.where(mask)
    if not len(xs):
        raise RecognitionError('Empty glyph')
    trimmed = mask[ys.min():ys.max()+1, xs.min():xs.max()+1]
    height,width = trimmed.shape
    scale = min(22/width,30/height)
    resized = cv2.resize(trimmed.astype(np.float32),
                         (max(1,round(width*scale)),max(1,round(height*scale))),
                         interpolation=cv2.INTER_AREA)
    out = np.zeros((32,24),np.float32)
    h,w = resized.shape
    y,x = (32-h)//2,(24-w)//2
    out[y:y+h,x:x+w] = resized
    return out

def segments(mask):
    active = np.any(mask, axis=0)
    edges = np.diff(np.r_[False, active, False].astype(int))
    return [mask[:, a:b] for a, b in zip(np.where(edges == 1)[0], np.where(edges == -1)[0])]

def match(mask, templates, threshold=.20, margin=.045):
    glyph = normalize(mask)
    scores = sorted((min(float(np.mean(np.abs(glyph-t))) for t in ts), label)
                    for label, ts in templates.items())
    if not scores or scores[0][0] > threshold or (len(scores)>1 and scores[1][0]-scores[0][0]<margin):
        raise RecognitionError(f'Uncertain glyph: {scores[:3]}')
    return scores[0][1], scores[0][0]


def read_bet_amount(im, templates):
    # Ignore grey leading zeroes and the cursor frame around the input field.
    mask = (crop(im, (688,349,771,364)).min(2) < 100).astype(np.uint8)
    chunks = segments(mask)
    if not chunks:
        raise RecognitionError('Missing bet digits')
    return int(''.join(match(c, templates, .20, .025)[0] for c in chunks))
