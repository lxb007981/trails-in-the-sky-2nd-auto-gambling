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
import webbrowser
from tkinter import messagebox, ttk
from PIL import Image, ImageTk

from casino.common.paths import ROOT, ASSETS
from casino.gui_theme import JADE, SAGE, configure_theme


PROJECT_URL = 'https://github.com/lxb007981/trails-in-the-sky-2nd-auto-gambling'


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
    if getattr(sys, 'frozen', False):
        return [str(executable), '--bot', module,
                '--run', '--focus', '--minutes', str(parse_minutes(minutes))]
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
        root.iconbitmap(default=str(ASSETS / 'sora_2.ico'))
        # Match the window's pixel dimensions to Tk's DPI-scaled fonts.
        scale = max(1.0, float(root.tk.call('tk', 'scaling')) / (96 / 72))
        root.geometry(f'{round(980 * scale)}x{round(850 * scale)}')
        root.minsize(round(940 * scale), round(830 * scale))
        self.scale = scale
        fonts = configure_theme(root, scale)
        unit = lambda value: round(value * scale)
        body = ttk.Frame(root, padding=unit(24))
        body.pack(fill='both', expand=True)
        project_link = ttk.Label(body, text=f'项目地址：{PROJECT_URL}', cursor='hand2',
                                 foreground=JADE[11], font=fonts['link'],
                                 takefocus=True)
        project_link.pack(side='bottom', pady=(unit(12), 0))
        for event in ('<Button-1>', '<Return>', '<space>'):
            project_link.bind(event, lambda _event: webbrowser.open(PROJECT_URL))
        project_link.bind('<FocusIn>', lambda _event: project_link.configure(background=JADE[4]))
        project_link.bind('<FocusOut>', lambda _event: project_link.configure(background=SAGE[1]))
        heading = ttk.Frame(body)
        heading.pack(fill='x', pady=(0, unit(24)))
        ttk.Label(heading, text='自动刷筹码', style='Title.TLabel').pack(anchor='w')
        ttk.Label(heading, text='选择游戏与时长，然后开始。', style='Muted.TLabel').pack(anchor='w', pady=(unit(4), 0))
        top = ttk.Frame(body)
        top.pack(fill='x')
        top.columnconfigure(0, weight=1)
        top.rowconfigure(0, weight=1)
        reference = ttk.Frame(top, style='Card.TFrame', padding=unit(20))
        reference.grid(row=0, column=1, sticky='nsew', padx=(unit(16), 0))
        ttk.Label(reference, text='起始画面', style='Section.TLabel').pack(anchor='w')
        self.reference_label = ttk.Label(reference, cursor='hand2', style='Card.TLabel')
        self.reference_label.pack(pady=(unit(12), unit(12)))
        self.reference_label.bind('<Button-1>', self.show_reference)
        ttk.Label(reference, text='点击图片放大查看', style='Caption.TLabel').pack(anchor='w')
        settings = ttk.Frame(top, style='Card.TFrame', padding=unit(20))
        settings.grid(row=0, column=0, sticky='nsew')
        ttk.Label(settings, text='运行设置', style='Section.TLabel').pack(anchor='w')
        ttk.Label(settings, text='先在游戏中进入对应的小游戏界面', style='Caption.TLabel').pack(anchor='w', pady=(unit(8), unit(20)))
        controls = ttk.Frame(settings, style='Card.TFrame')
        controls.pack(fill='x')
        controls.columnconfigure((0, 1), weight=1, uniform='input')
        ttk.Label(controls, text='本次游戏', style='Card.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Label(controls, text='持续时间（分钟）', style='Card.TLabel').grid(row=0, column=1, padx=(unit(16), 0), sticky='w')
        self.game = tk.StringVar(value='梭哈')
        self.minutes = tk.StringVar(value='10')
        self.game_input = ttk.Combobox(controls, textvariable=self.game, values=list(GAMES), state='readonly', width=12,
                                       font=fonts['body'])
        self.game_input.grid(row=1, column=0, pady=(unit(8), 0), sticky='ew')
        self.time_input = ttk.Entry(controls, textvariable=self.minutes, width=12, font=fonts['body'])
        self.time_input.grid(row=1, column=1, padx=(unit(16), 0), pady=(unit(8), 0), sticky='ew')
        ttk.Label(settings, text='支持小数时长，例如 0.5 分钟', style='Caption.TLabel').pack(anchor='w', pady=(unit(16), 0))
        self.hint = tk.StringVar()
        guidance = ttk.Frame(body, style='Hint.TFrame', padding=unit(20))
        guidance.pack(fill='x', pady=(unit(16), unit(12)))
        ttk.Label(guidance, text='开始前', style='Hint.TLabel', font=fonts['strong']).pack(anchor='w')
        hint_label = ttk.Label(guidance, textvariable=self.hint, style='Hint.TLabel', wraplength=unit(780))
        hint_label.pack(fill='x', pady=(unit(8), 0))
        guidance.bind('<Configure>', lambda event: hint_label.configure(wraplength=max(1, event.width - unit(40))))
        self.game_input.bind('<<ComboboxSelected>>', self.update_hint)
        self.update_hint()
        ttk.Label(body, text='游戏分辨率须为窗口化 1280×720。开始后自动切到游戏，请保持游戏在前台。',
                  style='Muted.TLabel').pack(anchor='w', padx=unit(20))
        ttk.Label(body, text='按 F8、切换窗口或点击停止均会中断；牌类和轮盘到时结算当前局后退出。',
                  style='Muted.TLabel').pack(anchor='w', padx=unit(20), pady=(unit(4), 0))
        buttons = ttk.Frame(body)
        buttons.pack(fill='x', pady=unit(16))
        self.start_button = ttk.Button(buttons, text='开始游玩', style='Primary.TButton', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(buttons, text='停止', command=self.stop, state='disabled')
        self.stop_button.pack(side='left', padx=unit(12))
        self.status = tk.StringVar(value='就绪')
        ttk.Label(buttons, textvariable=self.status, style='Muted.TLabel').pack(side='left', padx=(unit(4), 0))
        log_card = ttk.Frame(body, style='Card.TFrame', padding=unit(20))
        log_card.pack(fill='both', expand=True)
        log_heading = ttk.Frame(log_card, style='Card.TFrame')
        log_heading.pack(fill='x', pady=(0, unit(12)))
        ttk.Label(log_heading, text='运行日志', style='Section.TLabel').pack(side='left')
        ttk.Button(log_heading, text='打开日志目录', command=self.open_logs).pack(side='right')
        log_body = ttk.Frame(log_card, style='Card.TFrame')
        log_body.pack(fill='both', expand=True)
        self.output = tk.Text(log_body, height=5, state='disabled', wrap='word', font=fonts['mono'],
                              background=SAGE[3], foreground=SAGE[12], relief='flat', borderwidth=0,
                              padx=unit(12), pady=unit(12), selectbackground=JADE[5], selectforeground=JADE[12],
                              insertbackground=SAGE[12], highlightthickness=0)
        scrollbar = ttk.Scrollbar(log_body, orient='vertical', command=self.output.yview)
        scrollbar.pack(side='right', fill='y')
        self.output.configure(yscrollcommand=scrollbar.set)
        self.output.pack(side='left', fill='both', expand=True)
        self.output.bind('<FocusIn>', lambda _event: self.output.configure(background=JADE[3]))
        self.output.bind('<FocusOut>', lambda _event: self.output.configure(background=SAGE[3]))
        # Include five complete log lines and all surrounding controls at this DPI.
        root.update_idletasks()
        default_height = max(unit(850), root.winfo_reqheight())
        root.geometry(f'{unit(980)}x{default_height}')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def update_hint(self, _event=None):
        # Drop the combobox's text selection highlight after choosing a game.
        self.game_input.selection_clear()
        self.hint.set(GAMES[self.game.get()][1])
        path = ASSETS / 'start_screens' / f'{GAMES[self.game.get()][0]}.png'
        try:
            with Image.open(path) as source:
                self.reference_image = source.copy()
            preview = self.reference_image.copy()
            preview.thumbnail((round(288 * self.scale), round(162 * self.scale)), Image.Resampling.LANCZOS)
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
        popup.configure(background=SAGE[1])
        picture = self.reference_image.copy()
        picture.thumbnail((min(1280, self.root.winfo_screenwidth() - 100),
                           min(720, self.root.winfo_screenheight() - 160)),
                          Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(picture, master=popup)
        label = ttk.Label(popup, image=photo)
        label.image = photo
        label.pack(padx=14, pady=14)
        ttk.Label(popup, text='请将游戏调整到图示界面，再点击程序中的“开始游玩”。').pack(pady=(0, 14))
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
            ROOT.mkdir(parents=True, exist_ok=True)
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
