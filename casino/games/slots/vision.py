"""Slots fast-mode badge recognition."""
from casino.common.fast_mode import FastModeVision, MODE_BOX
from casino.common.paths import ASSETS


class SlotsVision(FastModeVision):
    def __init__(self):
        super().__init__(ASSETS/'slots')
