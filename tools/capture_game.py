"""Capture and inspect the game window; optional foreground keyboard input."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import json
from casino.common.paths import ROOT
import time
from PIL import ImageGrab

u = c.windll.user32
u.SetProcessDPIAware()
u.FindWindowW.argtypes = [w.LPCWSTR, w.LPCWSTR]
u.FindWindowW.restype = w.HWND
u.GetForegroundWindow.restype = w.HWND
TITLE = 'Trails in the Sky 2nd Chapter'

def window():
    h = u.FindWindowW(None, TITLE)
    if not h:
        raise RuntimeError('Game window not found')
    return h

def capture(label, key=None, click=None):
    h = window()
    u.ShowWindow(h, 9)
    u.SetForegroundWindow(h)
    time.sleep(.4)
    if u.GetForegroundWindow() != h:
        raise RuntimeError('Game is not foreground; refusing input/capture')
    if click:
        origin = w.POINT(0, 0)
        u.ClientToScreen(h, c.byref(origin))
        u.SetCursorPos(origin.x + click[0], origin.y + click[1])
        time.sleep(.2)
        u.mouse_event(2, 0, 0, 0, 0)
        time.sleep(.1)
        u.mouse_event(4, 0, 0, 0, 0)
        time.sleep(1.5)
    if key:
        keys = {'enter': 0x0D, 'escape': 0x1B, 'left': 0x25, 'up': 0x26,
                'right': 0x27, 'down': 0x28, 'space': 0x20, 'z': 0x5A, 'x': 0x58,
                'w': 0x57, 'a': 0x41, 's': 0x53, 'd': 0x44, 'r': 0x52}
        vk = keys[key]
        scan = u.MapVirtualKeyW(vk, 0)
        flags = 1 if key in ('left', 'right', 'up', 'down') else 0
        u.keybd_event(vk, scan, flags, 0)
        time.sleep(.12)
        u.keybd_event(vk, scan, flags | 2, 0)
        time.sleep(1.5)
    r = w.RECT()
    u.GetClientRect(h, c.byref(r))
    p = w.POINT(0, 0)
    u.ClientToScreen(h, c.byref(p))
    box = (p.x, p.y, p.x+r.right, p.y+r.bottom)
    out = ROOT / 'captures'
    out.mkdir(exist_ok=True)
    path = out / (label+'.png')
    ImageGrab.grab(bbox=box, all_screens=True).save(path)
    meta = {'label': label, 'key': key, 'click': click, 'client_box': box, 'time': time.time()}
    path.with_suffix('.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(path.resolve())

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('label')
    parser.add_argument('--key')
    parser.add_argument('--click', nargs=2, type=int)
    args = parser.parse_args()
    capture(args.label, args.key, args.click)
