"""Foreground-only Win32 control, client-area capture, and F8 emergency stop."""
import ctypes as c
from ctypes import wintypes as w
import time
from PIL import ImageGrab

u = c.windll.user32
try:
    u.SetProcessDpiAwarenessContext(c.c_void_p(-4))
except AttributeError:
    u.SetProcessDPIAware()
u.FindWindowW.argtypes = [w.LPCWSTR, w.LPCWSTR]
u.FindWindowW.restype = w.HWND
u.GetForegroundWindow.restype = w.HWND
for name in ('GetClientRect', 'ClientToScreen', 'IsIconic', 'SetForegroundWindow', 'ShowWindow'):
    # Explicit pointer widths are needed on 64-bit Windows.
    getattr(u,name).argtypes = {
        'GetClientRect':[w.HWND,c.POINTER(w.RECT)],
        'ClientToScreen':[w.HWND,c.POINTER(w.POINT)],
        'IsIconic':[w.HWND], 'SetForegroundWindow':[w.HWND],
        'ShowWindow':[w.HWND,c.c_int]}[name]

class Stopped(RuntimeError):
    pass

class RunLock:
    """Prevent two automation processes from sending competing inputs."""
    def __init__(self):
        self.kernel = c.WinDLL('kernel32',use_last_error=True)
        self.kernel.CreateMutexW.argtypes = [c.c_void_p,w.BOOL,w.LPCWSTR]
        self.kernel.CreateMutexW.restype = w.HANDLE
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        self.handle = self.kernel.CreateMutexW(None,False,'Local\\TrailsPokerAutomation')
        error = c.get_last_error()
        if not self.handle:
            raise Stopped(f'Cannot create run lock: {error}')
        if error == 183:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
            raise Stopped('Another poker automation process is already running')

    def __del__(self):
        if getattr(self,'handle',None):
            self.kernel.CloseHandle(self.handle)

class GameWindow:
    def __init__(self, focus=False):
        self.hwnd = u.FindWindowW(None, 'Trails in the Sky 2nd Chapter')
        if not self.hwnd:
            raise Stopped('Game window not found')
        # Clear F8's historical pressed bit before starting this run.
        u.GetAsyncKeyState(0x77)
        if focus:
            u.ShowWindow(self.hwnd,9)
            u.SetForegroundWindow(self.hwnd)
            time.sleep(.5)
        self.check()

    def check(self):
        if u.GetAsyncKeyState(0x77) & 0x8001:
            raise Stopped('F8 emergency stop')
        if u.IsIconic(self.hwnd) or u.GetForegroundWindow() != self.hwnd:
            raise Stopped('Game lost foreground focus; no further input sent')

    def grab(self):
        self.check()
        r, p = w.RECT(), w.POINT(0,0)
        if not u.GetClientRect(self.hwnd,c.byref(r)) or not u.ClientToScreen(self.hwnd,c.byref(p)):
            raise Stopped('Cannot get game client coordinates')
        if (r.right,r.bottom) != (1280,720):
            raise Stopped(f'Expected 1280x720 client, got {r.right}x{r.bottom}')
        im = ImageGrab.grab(bbox=(p.x,p.y,p.x+r.right,p.y+r.bottom),all_screens=True)
        self.check()
        return im

    def press(self, key):
        self.check()
        vk = {'enter':13,'escape':27,'tab':9,'w':87,'s':83,'a':65,'d':68}[key]
        scan = u.MapVirtualKeyW(vk,0)
        u.keybd_event(vk,scan,0,0)
        try:
            time.sleep(.08)
        finally:
            u.keybd_event(vk,scan,2,0)
        self.check()
        time.sleep(.20)
