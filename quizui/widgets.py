"""Reusable native widgets and a restrained teal/cream visual theme."""
import tkinter as tk
from tkinter import ttk

BG = '#f4f7f5'
PANEL = '#ffffff'
INK = '#183c35'
MUTED = '#61786f'
TEAL = '#147568'
DEEP = '#143f37'
PALE = '#e5efe7'
LINE = '#d6e2db'
RED = '#a53335'


def apply_theme(root):
    root.configure(bg=BG)
    root.option_add('*Font', ('Segoe UI', 10))
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', background=BG, foreground=INK, font=('Segoe UI', 10))
    style.configure('TFrame', background=BG)
    style.configure('Card.TFrame', background=PANEL)
    style.configure('TLabel', background=BG, foreground=INK)
    style.configure('Title.TLabel', font=('Segoe UI', 24, 'bold'))
    style.configure('Heading.TLabel', font=('Segoe UI', 13, 'bold'))
    style.configure('Muted.TLabel', foreground=MUTED)
    style.configure('Error.TLabel', foreground=RED)
    style.configure('TButton', padding=(13, 9), background=PANEL, borderwidth=1)
    style.map('TButton', background=[('active', PALE)], foreground=[('disabled', MUTED)])
    style.configure('Primary.TButton', background=TEAL, foreground='white', borderwidth=0)
    style.map('Primary.TButton', background=[('active', DEEP), ('disabled', '#88a69a')], foreground=[('disabled', 'white')])
    style.configure('Danger.TButton', foreground=RED)
    style.configure('TEntry', fieldbackground=PANEL, padding=7)
    style.configure('TCombobox', fieldbackground=PANEL, padding=7)
    style.configure('Treeview', background=PANEL, fieldbackground=PANEL, rowheight=34, borderwidth=0)
    style.configure('Treeview.Heading', background=PALE, foreground=INK, font=('Segoe UI', 10, 'bold'), padding=9)
    style.map('Treeview', background=[('selected', TEAL)], foreground=[('selected', 'white')])
    style.configure('TNotebook', background=BG, borderwidth=0)
    style.configure('TNotebook.Tab', padding=(16, 10))
    style.configure('TRadiobutton', padding=10)
    style.configure('TCheckbutton', padding=5)
    style.configure('TProgressbar', background=TEAL, troughcolor=PALE)


def label(parent, text, size=10, color=INK, bg=None, bold=False, **kwargs):
    return tk.Label(parent, text=text, font=('Segoe UI', size, 'bold' if bold else 'normal'),
                    fg=color, bg=bg or BG, anchor='w', justify='left', **kwargs)


class ScrollFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        bar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.body = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window(0, 0, window=self.body, anchor='nw')
        self.body.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        # Toplevel-scoped bindings also cover children without global bind_all.
        top = self.winfo_toplevel()
        def wheel(event):
            if not self.winfo_exists():
                return
            widget = self.winfo_containing(event.x_root, event.y_root)
            while widget is not None and widget is not self:
                widget = getattr(widget, 'master', None)
            if widget is self:
                direction = -1 if getattr(event, 'num', 0) == 4 or event.delta > 0 else 1
                self.canvas.yview_scroll(direction * 3, 'units')
        bindings = [(event, top.bind(event, wheel, add='+')) for event in ('<MouseWheel>', '<Button-4>', '<Button-5>')]
        def cleanup(event):
            if event.widget is self:
                for name, bid in bindings:
                    if bid:
                        top.unbind(name, bid)
        self.bind('<Destroy>', cleanup)


class DataTable(ttk.Frame):
    def __init__(self, parent, columns, rows, on_open=None):
        super().__init__(parent)
        self.records = {}
        self.tree = ttk.Treeview(self, columns=[c[0] for c in columns], show='headings', selectmode='browse')
        y = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        x = ttk.Scrollbar(self, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.tree.grid(row=0, column=0, sticky='nsew'); y.grid(row=0, column=1, sticky='ns'); x.grid(row=1, column=0, sticky='ew')
        self.rowconfigure(0, weight=1); self.columnconfigure(0, weight=1)
        for key, title, width in columns:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=65, anchor='w')
        self.tree.tag_configure('alternate', background='#f2f6f2')
        for i, row in enumerate(rows):
            iid = str(i)
            self.records[iid] = row
            self.tree.insert('', 'end', iid=iid, values=[str(row.get(c[0], '')) for c in columns], tags=('alternate',) if i % 2 else ())
        if on_open:
            self.tree.bind('<Double-1>', lambda e: on_open())
            self.tree.bind('<Return>', lambda e: on_open())

    def selected(self):
        from quizcore.validation import AppError
        selected = self.tree.selection()
        if not selected:
            raise AppError('Select a row first.')
        return self.records[selected[0]]


class FormDialog(tk.Toplevel):
    def __init__(self, app, title, fields, initial, save, extra=None):
        super().__init__(app.root)
        self.app = app
        self.title(title); self.geometry('700x680'); self.minsize(540, 440); self.configure(bg=BG)
        self.transient(app.root); self.grab_set()
        self.inputs = {}; self.readers = {}
        outer = ttk.Frame(self, padding=22); outer.pack(fill='both', expand=True)
        label(outer, title, 21, bold=True).pack(anchor='w', pady=(0, 15))
        scroller = ScrollFrame(outer); scroller.pack(fill='both', expand=True)
        for key, caption, kind in fields:
            label(scroller.body, caption, bold=True).pack(anchor='w', pady=(10, 5))
            value = initial.get(key, '')
            if kind == 'text':
                widget = tk.Text(scroller.body, height=4, wrap='word', bg=PANEL, fg=INK,
                                 relief='solid', borderwidth=1, font=('Segoe UI', 10), padx=9, pady=8)
                widget.insert('1.0', str(value)); widget.pack(fill='x', padx=(0, 8))
                self.readers[key] = lambda w=widget: w.get('1.0', 'end-1c')
            elif isinstance(kind, (list, tuple)):
                widget = ttk.Combobox(scroller.body, values=kind, state='readonly')
                widget.set(str(value if value != '' else kind[0])); widget.pack(fill='x', padx=(0, 8))
                self.readers[key] = widget.get
            else:
                widget = ttk.Entry(scroller.body, show='*' if kind == 'password' else '')
                widget.insert(0, str(value)); widget.pack(fill='x', padx=(0, 8))
                self.readers[key] = widget.get
            self.inputs[key] = widget
        self.extra_reader = extra(scroller.body) if extra else None
        self.error = tk.StringVar()
        ttk.Label(outer, textvariable=self.error, style='Error.TLabel', wraplength=630).pack(fill='x', pady=9)
        buttons = ttk.Frame(outer); buttons.pack(fill='x')
        ttk.Button(buttons, text='Cancel', command=self.destroy).pack(side='left')
        def submit():
            try:
                values = {k: reader() for k, reader in self.readers.items()}
                if self.extra_reader:
                    values.update(self.extra_reader())
                save(values)
                if self.winfo_exists(): self.destroy()
            except Exception as error:
                self.error.set(app.error_text(error))
        ttk.Button(buttons, text='Save changes', style='Primary.TButton', command=submit).pack(side='right')
        self.bind('<Escape>', lambda e: self.destroy())
        if self.inputs: next(iter(self.inputs.values())).focus_set()
