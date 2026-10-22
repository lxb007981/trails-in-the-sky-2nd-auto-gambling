"""Frozen GUI and worker entry point (console streams support GUI log capture)."""
import runpy
import sys


def main():
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            stream.reconfigure(encoding='utf-8', write_through=True)
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
