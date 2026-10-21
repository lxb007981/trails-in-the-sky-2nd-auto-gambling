import unittest
from unittest.mock import patch, MagicMock
import game_window
from game_window import GameWindow, Stopped

class InputSafetyTests(unittest.TestCase):
    def game(self):
        game = GameWindow.__new__(GameWindow)
        game.hwnd = 123
        return game

    def user32(self):
        mock = MagicMock()
        mock.GetAsyncKeyState.return_value = 0
        mock.IsIconic.return_value = 0
        mock.GetForegroundWindow.return_value = 123
        mock.MapVirtualKeyW.return_value = 28
        return mock

    def test_lost_focus_sends_nothing(self):
        mock = self.user32()
        mock.GetForegroundWindow.return_value = 456
        with patch.object(game_window,'u',mock), self.assertRaises(Stopped):
            self.game().press('enter')
        mock.keybd_event.assert_not_called()

    def test_f8_sends_nothing(self):
        mock = self.user32()
        mock.GetAsyncKeyState.return_value = 0x8000
        with patch.object(game_window,'u',mock), self.assertRaises(Stopped):
            self.game().press('enter')
        mock.keybd_event.assert_not_called()

    def test_key_release_even_if_interrupted(self):
        mock = self.user32()
        with patch.object(game_window,'u',mock), patch.object(game_window.time,'sleep',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.game().press('enter')
        self.assertEqual(mock.keybd_event.call_count,2)
        self.assertEqual(mock.keybd_event.call_args.args,(13,28,2,0))

if __name__=='__main__':
    unittest.main()
