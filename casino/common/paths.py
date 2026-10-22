"""Repository paths independent of the current working directory."""
from pathlib import Path
import os
import sys

RESOURCE_ROOT = Path(__file__).resolve().parents[2]
ASSETS = RESOURCE_ROOT / "assets"
# One-file resources are temporary; keep logs and caches in a writable location.
ROOT = (Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Sora2AutoGambling'
        if getattr(sys, 'frozen', False) else RESOURCE_ROOT)
