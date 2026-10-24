"""Radix light palette and borderless Tk styles.

Scale roles: 1–2 surfaces, 3–5 interaction, 9–10 solid actions,
11 secondary text, 12 primary text. No fractional borders: Tk rounds them.
Source: https://github.com/radix-ui/colors/blob/main/src/light.ts
Usage: https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale
"""
from tkinter import ttk


SAGE = {
    1: '#fbfdfc', 2: '#f7f9f8', 3: '#eef1f0', 4: '#e6e9e8',
    5: '#dfe2e0', 11: '#5f6563', 12: '#1a211e',
}
JADE = {
    2: '#f4fbf7', 3: '#e6f7ed', 4: '#d6f1e3', 5: '#c3e9d7',
    9: '#29a383', 10: '#26997b', 11: '#208368', 12: '#1d3b31',
}


def configure_theme(root, scale):
    # Negative Tk font sizes are pixels; scale explicitly with the window.
    fonts = {
        'body': ('Microsoft YaHei UI', -round(18 * scale)),
        'strong': ('Microsoft YaHei UI', -round(18 * scale), 'bold'),
        'caption': ('Microsoft YaHei UI', -round(16 * scale)),
        'link': ('Microsoft YaHei UI', -round(16 * scale), 'underline'),
        'title': ('Microsoft YaHei UI', -round(32 * scale), 'bold'),
        'mono': ('Consolas', -round(18 * scale)),
    }
    root.configure(background=SAGE[1])
    for option, value in {
        'font': fonts['body'], 'background': SAGE[3], 'foreground': SAGE[12],
        'selectBackground': JADE[5], 'selectForeground': JADE[12],
        'borderWidth': 0, 'highlightThickness': 0,
    }.items():
        root.option_add(f'*TCombobox*Listbox.{option}', value)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=fonts['body'], background=SAGE[1], foreground=SAGE[12],
                    borderwidth=0, relief='flat')
    style.configure('TFrame', background=SAGE[1])
    style.configure('TLabel', background=SAGE[1])
    style.configure('Muted.TLabel', foreground=SAGE[11])
    style.configure('Title.TLabel', font=fonts['title'])
    style.configure('Card.TFrame', background=SAGE[2])
    style.configure('Card.TLabel', background=SAGE[2])
    style.configure('Section.TLabel', background=SAGE[2], font=fonts['strong'])
    style.configure('Caption.TLabel', background=SAGE[2], foreground=SAGE[11], font=fonts['caption'])
    style.configure('Hint.TFrame', background=JADE[2])
    style.configure('Hint.TLabel', background=JADE[2], foreground=JADE[12])
    # Remove theme border/focus elements, including clam's beveled arrow.
    style.layout('TButton', [('Button.padding', {'sticky': 'nswe', 'children': [
        ('Button.label', {'sticky': 'nswe'})]})])
    style.configure('TButton', padding=(round(16 * scale), round(10 * scale)),
                    background=SAGE[3], foreground=SAGE[12], anchor='center')
    style.map('TButton', background=[('disabled', SAGE[3]), ('pressed', SAGE[5]),
                                    ('active', SAGE[4]), ('focus', JADE[4])],
              foreground=[('disabled', SAGE[11])])
    style.configure('Primary.TButton', background=JADE[9], foreground=SAGE[1], font=fonts['strong'])
    style.map('Primary.TButton', background=[('disabled', SAGE[3]), ('pressed', JADE[11]),
                                            ('active', JADE[10]), ('focus', JADE[11])],
              foreground=[('disabled', SAGE[11]), ('!disabled', SAGE[1])])
    style.layout('TEntry', [('Entry.padding', {'sticky': 'nswe', 'children': [
        ('Entry.textarea', {'sticky': 'nswe'})]})])
    style.layout('TCombobox', [('Combobox.padding', {'sticky': 'nswe', 'children': [
        ('Combobox.downarrow', {'side': 'right', 'sticky': 'ns'}),
        ('Combobox.textarea', {'sticky': 'nswe'})]})])
    for name in ('TEntry', 'TCombobox'):
        style.configure(name, padding=round(10 * scale), fieldbackground=SAGE[3],
                        background=SAGE[3], foreground=SAGE[12], arrowcolor=SAGE[11],
                        arrowsize=round(14 * scale), insertcolor=SAGE[12],
                        selectbackground=JADE[5], selectforeground=JADE[12],
                        bordercolor=SAGE[3], lightcolor=SAGE[3], darkcolor=SAGE[3])
        states = [('disabled', SAGE[3]), ('focus', JADE[3]), ('active', SAGE[4]),
                  ('readonly', SAGE[3])]
        style.map(name, fieldbackground=states, background=states,
                  foreground=[('disabled', SAGE[11]), ('!disabled', SAGE[12])],
                  arrowcolor=[('disabled', SAGE[11]), ('!disabled', SAGE[11])])
    style.layout('Vertical.TScrollbar', [('Vertical.Scrollbar.trough', {
        'sticky': 'ns', 'children': [('Vertical.Scrollbar.thumb', {'sticky': 'nswe'})]})])
    style.configure('Vertical.TScrollbar', background=SAGE[5], troughcolor=SAGE[2],
                    lightcolor=SAGE[5], darkcolor=SAGE[5], bordercolor=SAGE[5],
                    borderwidth=0, arrowsize=round(10 * scale))
    style.map('Vertical.TScrollbar', background=[('pressed', SAGE[11]), ('active', SAGE[11])],
              lightcolor=[('pressed', SAGE[11]), ('active', SAGE[11])],
              darkcolor=[('pressed', SAGE[11]), ('active', SAGE[11])])
    return fonts
