"""Build small runtime references from labelled blackjack captures."""
import json
from pathlib import Path
from PIL import Image
import numpy as np
from casino.games.blackjack.cards import rotated
from casino.common.vision import normalize, crop, segments

from casino.common.paths import ROOT
REFERENCES = {
    'menu': ('bj_033_menu', (574, 335, 709, 428)),
    'bet': ('bj_031_bet', (480, 245, 615, 470)),
    'bet_prompt': ('blackjack_001_menu', (250, 62, 565, 122)),
    'again': ('bj_030_prompt', (250, 62, 405, 88)),
    'cancel': ('bj_032_cancel', (250, 62, 426, 88)),
    'deposit': ('bj_003_enter', (250, 62, 495, 88)),
    'open': ('bj_005_hand', (250, 62, 405, 88)),
    'stand_dialog': ('bj_012_result', (250, 62, 505, 122)),
    'action_hit': ('bj_007_ready', (980, 187, 1275, 221)),
    'action_stand': ('bj_010_stand_selected', (980, 239, 1275, 273)),
    'settlement': ('bj_028_settle_stable', (435, 435, 906, 459)),
    'dialog_panel': ('bj_005_hand', (240, 48, 390, 60)),
}


def build():
    out = ROOT/'assets'/'blackjack'
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    for name, (source, box) in REFERENCES.items():
        with Image.open(ROOT/'captures'/f'{source}.png') as im:
            im.crop(box).save(out/f'{name}.png')
        entries.append(dict(name=name, file=f'{name}.png', box=box))
    with Image.open(ROOT/'captures'/'bj_005_hand.png') as im:
        im.crop((409,89,428,101)).save(out/'triangle.png')
    (out/'manifest.json').write_text(json.dumps(entries,indent=2),encoding='utf-8')
    # Verified AS corner after the fifth card shifts/rotates the layout.
    with Image.open(ROOT/'captures'/'bj_regression_five_two_aces.png') as im:
        a = rotated(im)[843:857,826:838]
        mask = ((a.max(2)<125) | ((a[:,:,0]>100)&(a[:,:,1]<90)&(a[:,:,2]<110)))
        np.save(out/'S_rotated.npy',normalize(mask))
    with Image.open(ROOT/'captures'/'bj_regression_250.png') as im:
        chunks = segments((crop(im,(600,472,700,500)).min(2)>180).astype(np.uint8))
        assert len(chunks) == 3
        for label,chunk in zip('250',chunks):
            np.save(out/f'{label}_white.npy',normalize(chunk))
    with Image.open(ROOT/'captures'/'bj_regression_red_five.png') as im:
        a = rotated(im)[913:932,816:830]
        mask = ((a.max(2)<125) | ((a[:,:,0]>100)&(a[:,:,1]<90)&(a[:,:,2]<110)))
        np.save(out/'5_rank.npy',normalize(mask))


if __name__ == '__main__':
    build()
