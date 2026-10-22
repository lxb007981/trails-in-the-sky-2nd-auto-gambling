"""Recognize the top-right HIGH-SPEED MODE badge at 1280 x 720."""
import numpy as np
from PIL import Image

from casino.common.vision import RecognitionError

MODE_BOX = (1110, 20, 1240, 40)


class FastModeVision:
    def __init__(self, folder):
        self.templates = {}
        for state in ('on', 'off'):
            with Image.open(folder/f'fast_mode_{state}.png') as image:
                self.templates[state] = np.asarray(image.convert('RGB'), dtype=np.float32)

    def fast_mode(self, image):
        if image.size != (1280, 720):
            raise RecognitionError(f'Expected 1280x720, got {image.size}')
        region = np.asarray(image.convert('RGB').crop(MODE_BOX), dtype=np.float32)
        scores = sorted((float(np.mean(np.abs(region-template))), state)
                        for state, template in self.templates.items())
        if scores[0][0] > 18 or scores[1][0]-scores[0][0] < 20:
            raise RecognitionError(f'Cannot confirm fast mode: {scores}')
        return scores[0][1]
