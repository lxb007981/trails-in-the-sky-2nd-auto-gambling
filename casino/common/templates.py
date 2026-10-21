"""Load shared glyph templates without loading game state references."""
import numpy as np

def load_templates(folder):
    templates = {}
    for kind in ("ranks", "suits", "digits"):
        labels = {}
        for path in (folder / kind).glob("*.npy"):
            label = path.stem.split("_")[0]
            labels.setdefault(label, []).append(np.load(path))
        templates[kind] = labels
    return templates
