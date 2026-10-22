"""Windowed GUI and worker entry point with redirected worker logs."""
import os
import runpy
import sys


def configure_output():
    # Windowed Python sets stdout/stderr to None, even when the parent supplies
    # pipes. Reopen those Windows handles without allocating a console.
    for name, handle_id in (('stdout', -11), ('stderr', -12)):
        stream = getattr(sys, name)
        if stream is None:
            if os.name == 'nt':
                import ctypes
                import msvcrt
                from ctypes import wintypes

                get_handle = ctypes.WinDLL('kernel32', use_last_error=True).GetStdHandle
                get_handle.argtypes = [wintypes.DWORD]
                get_handle.restype = wintypes.HANDLE
                handle = get_handle(handle_id)
                if handle not in (None, 0, ctypes.c_void_p(-1).value):
                    fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
                    stream = open(fd, 'w', encoding='utf-8', buffering=1)
            if stream is None:
                stream = open(os.devnull, 'w', encoding='utf-8')
            setattr(sys, name, stream)
        stream.reconfigure(encoding='utf-8', write_through=True)


def main():
    configure_output()
    if len(sys.argv) > 1 and sys.argv[1] == '--bot':
        if len(sys.argv) < 3 or sys.argv[2] not in ('poker', 'blackjack', 'roulette', 'slots'):
            raise SystemExit('Unknown game')
        module = f'casino.games.{sys.argv[2]}.bot'
        sys.argv = [module, *sys.argv[3:]]
        runpy.run_module(module, run_name='__main__')
    elif sys.argv[1:] == ['--smoke-test']:
        from casino.packaging_check import smoke_test
        smoke_test()
    else:
        from casino.gui import main as gui_main
        gui_main()


if __name__ == '__main__':
    main()
