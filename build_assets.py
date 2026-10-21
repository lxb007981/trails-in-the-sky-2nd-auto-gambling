"""Build recognition assets from human-labelled local screenshots."""
import json
from PIL import Image
import numpy as np
from vision import ROOT, ASSETS, rank_mask, suit_mask, normalize, ink, crop, segments

STATE_REFERENCES = [
    ('menu', '042_final_menu', (565,282,718,437)),
    ('bet', '005_bet', (480,200,810,235)),
    ('bet_prompt', '004_rules', (248,61,550,121)),
    ('bet_prompt', '011_continue', (248,61,550,121)),
    ('deposit', '006_deal', (248,61,480,88)),
    ('cancel', '013_cancel', (248,61,475,88)),
    ('win_dialog', '038_win', (248,61,378,120)),
    ('loss_dialog', '010_loss', (248,61,478,88)),
    ('hand', '007_hand', (1032,512,1200,542)),
    ('hand', '031_hold4', (1060,512,1200,542)),
    ('settlement', '038_win', (449,389,893,415)),
    ('dialog_panel', '054_debug', (224,48,245,90)),
]

def build_state_assets():
    folder = ASSETS / "states"
    folder.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, source, box in STATE_REFERENCES:
        filename = f"{name}_{source}.png"
        with Image.open(ROOT/"captures"/f"{source}.png") as im:
            im.convert("RGB").crop(box).save(folder/filename)
        manifest.append(dict(name=name, file=filename, box=box))
    (folder/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")

def save(kind, label, suffix, mask):
    d = ASSETS/kind
    d.mkdir(parents=True, exist_ok=True)
    np.save(d/f'{label}_{suffix}.npy', normalize(mask))

def build():
    build_state_assets()
    labels = json.loads((ROOT/'labels.json').read_text())
    # These are generated arrays only. Remove stale labels when correcting data.
    for kind in ('ranks','suits','digits'):
        folder = (ASSETS/kind).resolve()
        if folder.parent != ASSETS.resolve():
            raise ValueError('Asset folder escaped project')
        for file in folder.glob('*.npy'):
            if file.resolve().parent != folder:
                raise ValueError('Unexpected asset path')
            file.unlink()
    for file, cards in labels.items():
        im = Image.open(ROOT/'captures'/f'{file}.png')
        for i, card in enumerate(cards):
            save('ranks', card[0], f'{file}_{i}', rank_mask(im,i))
            save('suits', card[1], f'{file}_{i}', suit_mask(im,i))
    for bet in range(1,11):
        file = {1:'045_bet', 2:'046_bet_up'}.get(bet, f'cal_bet_{bet}')
        im = Image.open(ROOT/'captures'/f'{file}.png')
        for name, number, box in [('balance',403,(730,255,775,280)),
                                   ('remaining',403-bet,(730,436,775,461))]:
            glyphs = segments(ink(crop(im,box)))
            if len(glyphs) != len(str(number)):
                raise ValueError(f'Digit segmentation failed: {file} {number} {len(glyphs)}')
            for i,(digit,mask) in enumerate(zip(str(number),glyphs)):
                save('digits',digit,f'{file}_{name}_{i}',mask)
    # Four-digit balances render at different horizontal pixel offsets.
    for file, balance, remaining in [('live_progress',1556,1546), ('digits_four',1586,1576)]:
        im = Image.open(ROOT/'captures'/f'{file}.png')
        for name, number, box in [('balance',balance,(620,255,775,280)),
                                  ('remaining',remaining,(620,436,775,461))]:
            glyphs = segments(ink(crop(im,box)))
            if len(glyphs) != len(str(number)):
                raise ValueError(f'Digit segmentation failed: {file} {name}')
            for i,(digit,mask) in enumerate(zip(str(number),glyphs)):
                save('digits',digit,f'{file}_{name}_{i}',mask)
    known = {}
    for path in (ASSETS/'suits').glob('*.npy'):
        key = np.load(path).tobytes()
        label = path.stem.split('_')[0]
        if key in known and known[key][0] != label:
            raise ValueError(f'Conflicting suit labels: {path.name}, {known[key][1]}')
        known[key] = (label,path.name)
    print('Assets rebuilt; suit labels checked for conflicts.')

if __name__ == '__main__':
    build()
