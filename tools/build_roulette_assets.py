"""Rebuild roulette-local references from labeled development captures."""
import json
import numpy as np
from PIL import Image
from casino.common.paths import ROOT, ASSETS
from casino.common.fast_mode import MODE_BOX
from casino.common.vision import crop, normalize, segments
from casino.games.roulette.vision import counter_mask


REFERENCES = {
    'menu': ('rt_001_menu', (570,370,710,428)),
    'prompt': ('rt_017_start', (250,64,463,86)),
    'again': ('rt_024_again', (250,64,550,119)),
    'cancel': ('rt_026_cancel', (250,64,444,86)),
    'board': ('rt_018_board', (539,40,740,124)),
    'selection': ('rt_018_board', (175,280,248,430)),
    'settlement': ('rt_022_result', (434,391,910,415)),
    'win': ('rt_win', (333,326,944,351)),
}


def build():
    folder = ASSETS/'roulette'
    folder.mkdir(exist_ok=True)
    for mode, source in [('off', 'initial'), ('on', 'on')]:
        with Image.open(ROOT/'captures'/f'roulette_fast_mode_{source}.png') as im:
            im.crop(MODE_BOX).save(folder/f'fast_mode_{mode}.png')
    manifest = []
    for name, (source, box) in REFERENCES.items():
        with Image.open(ROOT/'captures'/f'{source}.png') as im:
            im.crop(box).save(folder/f'{name}.png')
        manifest.append(dict(name=name, box=box, file=f'{name}.png'))
    (folder/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    digits = folder/'account_digits'
    digits.mkdir(exist_ok=True)
    for n in range(10):
        with Image.open(ROOT/'captures'/f'rt_cal_{n}.png') as im:
            for y, value in [(55,str(66951-n*10)),(89,str((n+1)*10))]:
                for i,d in enumerate(reversed(value)):
                    box = (int(1213-(i+1)*11.5),y,int(1213-i*11.5),y+24)
                    mask = counter_mask(im,box)
                    np.save(digits/f'{d}_{n}_{y}_{i}.npy', normalize(mask))
    for name in ('rt_zero_regression', 'rt_027_menu'):
        with Image.open(ROOT/'captures'/f'{name}.png') as im:
            mask = counter_mask(im,(1201,89,1213,113))
            np.save(digits/f'0_{name}.npy', normalize(mask))
    # The original calibration mostly exercises digits in the tens column.
    # Half-pixel advances rasterize the same digit differently in other cells.
    # Keep real samples from balances that previously stalled menu recovery.
    for name, value in [('rt_account_96972', '96972'), ('rt_account_25011', '25011'),
                        ('rt_account_23811', '23811')]:
        with Image.open(ROOT/'captures'/f'{name}.png') as im:
            for i, d in enumerate(reversed(value)):
                box = (int(1213-(i+1)*11.5),55,int(1213-i*11.5),79)
                np.save(digits/f'{d}_{name}_{i}.npy', normalize(counter_mask(im,box)))
    digits = folder/'digits'
    digits.mkdir(exist_ok=True)
    samples = [
        ('rt_027_menu',(1130,55,1218,79),'66961'),
        ('rt_027_menu',(1130,89,1218,112),'0'),
        ('rt_019_red',(1130,89,1218,112),'10'),
        ('rt_018_board',(667,68,712,100),'12'),
        ('rt_020_down',(667,68,712,100),'36'),
    ]
    for source,box,value in samples:
        with Image.open(ROOT/'captures'/f'{source}.png') as im:
            chunks = segments((crop(im,box).min(2)>180).astype(np.uint8))
            if len(chunks) != len(value):
                raise ValueError(f'Bad label: {source}')
            for i,(chunk,d) in enumerate(zip(chunks,value)):
                np.save(digits/f'{d}_{source}_{i}.npy', normalize(chunk))
    with Image.open(ROOT/'captures/rt_022_result.png') as im:
        for box, value in [((448,431,505,455),'10'),((625,431,682,455),'0'),((793,431,873,455),'0')]:
            chunks = segments((crop(im,box).min(2)>180).astype(np.uint8))
            if len(chunks) != len(value):
                raise ValueError(f'Bad label at {box}')
            for i,(chunk,d) in enumerate(zip(chunks,value)):
                np.save(digits/f'{d}_settle_{box[0]}_{i}.npy', normalize(chunk))
    with Image.open(ROOT/'captures/rt_win.png') as im:
        for box,value in [((520,363,575,387),'12'),((700,363,755,387),'10'),
                          ((850,363,917,387),'120'),((850,402,917,427),'120')]:
            chunks = segments((crop(im,box).min(2)>180).astype(np.uint8))
            if len(chunks) != len(value):
                raise ValueError(f'Bad winning label at {box}')
            for i,(chunk,d) in enumerate(zip(chunks,value)):
                np.save(digits/f'{d}_win_{box[0]}_{box[1]}_{i}.npy', normalize(chunk))


if __name__ == '__main__':
    build()
