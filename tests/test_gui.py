import io
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

from casino.gui import CasinoApp, GAMES, build_command, parse_minutes
from casino.common import window


class GuiTests(unittest.TestCase):
    def test_invalid_durations(self):
        for value in ('', 'abc', '0', '-1', 'nan', 'inf', '1e308'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_minutes(value)
        self.assertEqual(parse_minutes('0.5'), 0.5)

    def test_all_game_entrypoints(self):
        for name, (module, _) in GAMES.items():
            command = build_command(name, '0.5')
            self.assertIn(f'casino.games.{module}.bot', command)
            self.assertEqual(command[-4:], ['--run', '--focus', '--minutes', '0.5'])

    def test_stop_request_prevents_key_input(self):
        game = window.GameWindow.__new__(window.GameWindow)
        game.hwnd = 123
        with tempfile.TemporaryDirectory() as directory:
            stop_file = Path(directory) / 'stop'
            stop_file.touch()
            with patch.dict(os.environ, {'CASINO_STOP_FILE': str(stop_file)}), patch.object(window, 'u') as user32:
                with self.assertRaisesRegex(window.Stopped, 'GUI'):
                    game.press('enter')
                user32.keybd_event.assert_not_called()

    def test_launch_stop_and_finish(self):
        root = tk.Tk()
        root.withdraw()
        app = CasinoApp(root)
        process = MagicMock()
        process.stdout = io.StringIO('{"event":"start"}\n')
        process.wait.return_value = 0
        try:
            with patch('casino.gui.subprocess.Popen', return_value=process) as launch, patch('casino.gui.threading.Thread'):
                app.start()
                app.start()
                launch.assert_called_once()
                stop_path = Path(launch.call_args.kwargs['env']['CASINO_STOP_FILE'])
                self.assertFalse(stop_path.exists())
                self.assertEqual(str(app.start_button['state']), 'disabled')
                app.stop()
                self.assertTrue(stop_path.exists())
                app.read_output(process)
                app.poll()
                self.assertIsNone(app.process)
                self.assertFalse(stop_path.parent.exists())
                self.assertEqual(app.status.get(), '已停止')
                self.assertEqual(str(app.start_button['state']), 'normal')
        finally:
            root.destroy()

    def test_launch_failure_restores_idle(self):
        root = tk.Tk()
        root.withdraw()
        app = CasinoApp(root)
        try:
            with patch('casino.gui.subprocess.Popen', side_effect=OSError('test')), patch('casino.gui.messagebox.showerror') as error:
                app.start()
                error.assert_called_once()
                self.assertIsNone(app.process)
                self.assertIsNone(app.stop_dir)
                self.assertEqual(str(app.start_button['state']), 'normal')
        finally:
            root.destroy()
