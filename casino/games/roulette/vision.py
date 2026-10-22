"""Roulette-local reference images and numeric recognition."""
import json
import cv2
import numpy as np
from PIL import Image
from casino.common.paths import ASSETS
from casino.common.templates import load_templates
from casino.common.vision import crop, segments, match, RecognitionError


def counter_mask(im, box):
    mask = (crop(im, box).min(2)>180).astype(np.uint8)
    # Italic 8 can spill one isolated edge pixel into the preceding cell.
    # Remove only tiny disconnected components, preserving split 0/3 strokes.
    _, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    for index, stat in enumerate(stats[1:], 1):
        if stat[cv2.CC_STAT_AREA] <= 2:
            mask[labels == index] = 0
    return mask


class RouletteVision:
    def __init__(self):
        folder = ASSETS/'roulette'
        self.refs = {}
        for entry in json.loads((folder/'manifest.json').read_text()):
            self.refs[entry['name']] = (entry['box'], np.asarray(Image.open(folder/entry['file'])).astype(float))
        self.digits = load_templates(ASSETS)['digits']
        for path in (folder/'digits').glob('*.npy'):
            self.digits.setdefault(path.stem.split('_')[0], []).append(np.load(path))
        self.account_digits = {}
        for path in (folder/'account_digits').glob('*.npy'):
            self.account_digits.setdefault(path.stem.split('_')[0], []).append(np.load(path))

    def score(self, im, name):
        box, ref = self.refs[name]
        return float(np.abs(crop(im, box).astype(float)-ref).mean()/255)

    def state(self, im):
        if self.score(im, 'win') < .025:
            return 'settlement'
        for name in ('settlement', 'menu', 'again', 'prompt', 'cancel', 'board'):
            if self.score(im, name) < .025:
                return name
        return 'animation'

    def number(self, im, box):
        chunks = segments((crop(im, box).min(2)>180).astype(np.uint8))
        if not chunks:
            raise RecognitionError(f'Missing number at {box}')
        return int(''.join(match(c, self.digits, .20, .025)[0] for c in chunks))

    def street_selected(self, im):
        # Selection brightness pulses. Require cyan coverage in all three
        # cells plus the observed Rate 12 panel, rather than a fixed RGB image.
        if self.state(im) != 'board':
            return False
        for y in (230,305,380):
            a = crop(im,(176,y,188,y+35)).astype(float)
            cyan = (a[:,:,2]>90)&(a[:,:,1]>120)&(a[:,:,1]>1.2*a[:,:,0])
            if cyan.mean() < .40:
                return False
        return True

    def account(self, im):
        def read(y):
            # The italic counter uses fixed 11.5 px advances. Projection splits
            # disconnected strokes inside 0/3, so read complete character cells.
            text = ''
            for i in range(7, -1, -1):
                mask = counter_mask(im, (int(1213-(i+1)*11.5), y, int(1213-i*11.5), y+24))
                if mask.sum() > 4:
                    try:
                        text += match(mask, self.account_digits, .16, .025)[0]
                    except RecognitionError as error:
                        field = 'balance' if y == 55 else 'bet'
                        raise RecognitionError(f'{field} digit {i} from right: {error}') from error
                elif text:
                    raise RecognitionError('Gap in account digits')
            if not text:
                raise RecognitionError('Missing account digits')
            return int(text)
        return read(55), read(89)

    def settlement(self, im):
        win = self.score(im, 'win') < .025
        boxes = ((700,363,755,387),(520,363,575,387),(850,363,917,387)) if win else (
            (448,431,505,455),(625,431,682,455),(793,431,873,455))
        values = tuple(self.number(im, box) for box in boxes)
        bet, rate, received = values
        if bet != 10 or rate != (12 if win else 0) or received != bet*rate:
            raise RecognitionError(f'Unexpected street settlement: {values}')
        if win and self.number(im,(850,402,917,427)) != received:
            raise RecognitionError('Winning total does not equal the street return')
        return values
