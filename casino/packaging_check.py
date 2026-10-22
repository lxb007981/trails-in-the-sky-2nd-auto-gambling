"""Offline checks for the bundled runtime; never interacts with the game."""
import subprocess
import tkinter as tk

from casino.common.fast_mode import FastModeVision
from casino.common.paths import ASSETS
from casino.games.blackjack.vision import BlackjackVision
from casino.games.poker.vision import Vision
from casino.games.roulette.vision import RouletteVision
from casino.gui import CasinoApp, GAMES, build_command


def smoke_test():
    Vision()
    BlackjackVision()
    RouletteVision()
    for game, _ in GAMES.values():
        FastModeVision(ASSETS / game)
    root = tk.Tk()
    root.withdraw()
    try:
        app = CasinoApp(root)
        for name in GAMES:
            app.game.set(name)
            app.update_hint()
            if app.reference_image is None:
                raise RuntimeError(f'Missing start screen: {name}')
            # --help loads the actual worker entry point without sending input.
            command = build_command(name, 1)[:-4] + ['--help']
            result = subprocess.run(command, capture_output=True, text=True,
                                    encoding='utf-8', timeout=60,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode or '--minutes' not in result.stdout:
                raise RuntimeError(f'{name}: {result.stdout}\n{result.stderr}')
        root.update_idletasks()
    finally:
        root.destroy()
    print('Packaged GUI, assets and all four workers passed.', flush=True)
