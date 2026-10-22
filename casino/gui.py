"""Desktop launcher for the existing game automation entry points."""
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from PIL import Image, ImageTk

from casino.common.paths import ROOT


GAMES = {
    '梭哈': ('poker', '请停在“开始”菜单或下注提示 / 下注窗口。每局默认下注 10 枚。'),
    '21 点': ('blackjack', '请停在“开始”菜单、下注提示或下注窗口。每局默认下注 100 枚。'),
    '轮盘': ('roulette', '请停在“开始”菜单或未下注、初始选区为 1/2/3 的界面。每局下注 10 枚。\n\n基本上无法有效刷筹码，仅能用于完成成就。'),
    '角子机': ('slots', '请先进入角子机界面。到时停止按键并保留当前画面。'),
}


def parse_minutes(value):
    try:
        minutes = float(value)
    except (TypeError, ValueError):
        raise ValueError('请输入大于 0 的分钟数，例如 10 或 0.5。') from None
    if not math.isfinite(minutes) or minutes <= 0 or not math.isfinite(minutes * 60):
        raise ValueError('运行时长必须是有限的正数。')
    return minutes


def build_command(game, minutes):
    module = GAMES[game][0]
    executable = Path(sys.executable)
    if executable.name.lower() == 'pythonw.exe':
        executable = executable.with_name('python.exe')
    return [str(executable), '-u', '-m', f'casino.games.{module}.bot',
            '--run', '--focus', '--minutes', str(parse_minutes(minutes))]


class CasinoApp:
    def __init__(self, root):
        self.root = root
        self.process = None
        self.stop_dir = None
        self.messages = queue.Queue()
        self.closing = False
        self.started = None
        self.duration = 0
        self.stopping = False
        root.title('空之轨迹 2nd · 全自动赌圣')
        root.iconbitmap(default=str(ROOT / 'assets' / 'sora_2.ico'))
        root.geometry('820x600')
        root.minsize(820, 560)
        style = ttk.Style(root)
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        style.configure('TLabel', font=('Microsoft YaHei UI', 10))
        style.configure('TButton', font=('Microsoft YaHei UI', 10), padding=7)
        body = ttk.Frame(root, padding=22)
        body.pack(fill='both', expand=True)
        top = ttk.Frame(body)
        top.pack(fill='x')
        reference = ttk.Frame(top)
        reference.pack(side='right', anchor='n', padx=(12, 0))
        ttk.Label(reference, text='起始界面示例 · 点击图片放大').pack(anchor='w')
        self.reference_label = ttk.Label(reference, cursor='hand2')
        self.reference_label.pack(pady=(4, 0))
        self.reference_label.bind('<Button-1>', self.show_reference)
        settings = ttk.Frame(top)
        settings.pack(side='left', fill='both', expand=True)
        ttk.Label(settings, text='自动刷筹码', font=('Microsoft YaHei UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(settings, text='选择游戏与时长，然后开始。').pack(anchor='w', pady=(4, 18))
        controls = ttk.Frame(settings)
        controls.pack(fill='x')
        ttk.Label(controls, text='本次游戏').grid(row=0, column=0, sticky='w')
        ttk.Label(controls, text='持续时间（分钟）').grid(row=0, column=1, padx=20, sticky='w')
        self.game = tk.StringVar(value='梭哈')
        self.minutes = tk.StringVar(value='10')
        self.game_input = ttk.Combobox(controls, textvariable=self.game, values=list(GAMES), state='readonly', width=20)
        self.game_input.grid(row=1, column=0, pady=7, sticky='w')
        self.time_input = ttk.Entry(controls, textvariable=self.minutes, width=20)
        self.time_input.grid(row=1, column=1, padx=20, pady=7, sticky='w')
        self.hint = tk.StringVar()
        ttk.Label(body, textvariable=self.hint, wraplength=650).pack(anchor='w', pady=(8, 8))
        self.game_input.bind('<<ComboboxSelected>>', self.update_hint)
        self.update_hint()
        ttk.Label(body, text='游戏分辨率须为窗口化 1280×720。开始后自动切到游戏，请保持游戏在前台。\n按 F8、切换窗口或点击停止均会中断；牌类和轮盘到时结算当前局后退出。',
                  wraplength=650).pack(anchor='w')
        buttons = ttk.Frame(body)
        buttons.pack(fill='x', pady=16)
        self.start_button = ttk.Button(buttons, text='开始游玩', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(buttons, text='停止', command=self.stop, state='disabled')
        self.stop_button.pack(side='left', padx=10)
        ttk.Button(buttons, text='打开日志目录', command=self.open_logs).pack(side='right')
        self.status = tk.StringVar(value='就绪')
        ttk.Label(body, textvariable=self.status).pack(anchor='w', pady=(0, 8))
        self.output = scrolledtext.ScrolledText(body, height=12, state='disabled', wrap='word', font=('Consolas', 10))
        self.output.pack(fill='both', expand=True)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def update_hint(self, _event=None):
        self.hint.set(GAMES[self.game.get()][1])
        path = ROOT / 'assets' / 'start_screens' / f'{GAMES[self.game.get()][0]}.png'
        try:
            with Image.open(path) as source:
                self.reference_image = source.copy()
            preview = self.reference_image.copy()
            preview.thumbnail((288, 162), Image.Resampling.LANCZOS)
            self.reference_photo = ImageTk.PhotoImage(preview, master=self.root)
            self.reference_label.configure(image=self.reference_photo, text='')
        except OSError:
            self.reference_image = None
            self.reference_label.configure(image='', text='起始界面示例暂不可用')

    def show_reference(self, _event=None):
        if self.reference_image is None:
            return
        popup = tk.Toplevel(self.root)
        popup.title(f'{self.game.get()} · 起始界面示例')
        popup.transient(self.root)
        picture = self.reference_image.copy()
        picture.thumbnail((min(1280, self.root.winfo_screenwidth() - 100),
                           min(720, self.root.winfo_screenheight() - 160)),
                          Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(picture, master=popup)
        label = ttk.Label(popup, image=photo)
        label.image = photo
        label.pack(padx=12, pady=12)
        ttk.Label(popup, text='请将游戏调整到图示界面，再点击程序中的“开始游玩”。').pack(pady=(0, 12))
        popup.bind('<Escape>', lambda _event: popup.destroy())

    def append(self, text):
        self.output.configure(state='normal')
        self.output.insert('end', text + '\n')
        if int(self.output.index('end-1c').split('.')[0]) > 1500:
            self.output.delete('1.0', '300.0')
        self.output.see('end')
        self.output.configure(state='disabled')

    def start(self):
        if self.process is not None:
            return
        try:
            minutes = parse_minutes(self.minutes.get())
            command = build_command(self.game.get(), minutes)
        except ValueError as error:
            messagebox.showerror('时长有误', str(error), parent=self.root)
            return
        self.stop_dir = tempfile.TemporaryDirectory(prefix='casino_gui_')
        env = os.environ.copy()
        env['CASINO_STOP_FILE'] = str(Path(self.stop_dir.name) / 'stop')
        env['PYTHONIOENCODING'] = 'utf-8'
        try:
            self.process = subprocess.Popen(command, cwd=ROOT, env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except OSError as error:
            self.stop_dir.cleanup()
            self.stop_dir = None
            messagebox.showerror('无法启动', str(error), parent=self.root)
            return
        self.duration = minutes * 60
        self.started = None
        self.stopping = False
        self.status.set('正在启动并切换到游戏…')
        self.start_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.game_input.configure(state='disabled')
        self.time_input.configure(state='disabled')
        self.append(f'\n开始：{self.game.get()}，{minutes:g} 分钟')
        threading.Thread(target=self.read_output, args=(self.process,), daemon=True).start()

    def read_output(self, process):
        try:
            with process.stdout:
                for line in process.stdout:
                    self.messages.put(('line', line.rstrip()))
        finally:
            self.messages.put(('exit', process.wait()))

    def stop(self):
        if self.process is not None:
            (Path(self.stop_dir.name) / 'stop').touch()
            self.stopping = True
            self.status.set('正在停止，等待当前操作释放按键…')
            self.stop_button.configure(state='disabled')

    def poll(self):
        for _ in range(200):
            try:
                kind, value = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == 'line':
                self.append(value)
                try:
                    event = json.loads(value)
                    if isinstance(event, dict) and event.get('event') == 'start':
                        self.started = time.monotonic()
                except (ValueError, TypeError):
                    pass
            else:
                self.process = None
                self.stop_dir.cleanup()
                self.stop_dir = None
                self.status.set('已停止' if self.stopping else ('运行完成' if value == 0 else '运行已中断，请查看日志'))
                self.append(f'进程已结束，退出码：{value}')
                self.start_button.configure(state='normal')
                self.stop_button.configure(state='disabled')
                self.game_input.configure(state='readonly')
                self.time_input.configure(state='normal')
                if self.closing:
                    self.root.destroy()
                    return
        if self.process is not None and self.started is not None and not self.stopping:
            remaining = max(0, math.ceil(self.duration - (time.monotonic() - self.started)))
            self.status.set(f'运行中 · 预计剩余 {remaining // 60:02d}:{remaining % 60:02d}'
                            if remaining else '设定时长已到，等待当前局结算 / 程序退出…')
        self.root.after(100, self.poll)

    def open_logs(self):
        path = ROOT / 'logs'
        path.mkdir(exist_ok=True)
        try:
            os.startfile(path)
        except OSError as error:
            messagebox.showerror('无法打开日志', str(error), parent=self.root)

    def close(self):
        if self.process is None:
            self.root.destroy()
        else:
            self.closing = True
            self.stop()


def main():
    root = tk.Tk()
    CasinoApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
