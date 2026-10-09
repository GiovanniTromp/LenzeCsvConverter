"""Desktop CSV review and LASAL export with light and dark themes."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinterdnd2 import DND_FILES, TkinterDnD
from app_settings import default_settings_path, load_theme, save_theme
from lenze_parser import get_group_name, get_group_number, get_display_parameter_from_fields
from utils import ReviewRow, build_output_file, read_review_csv, edit_parameter_fields

COLUMNS = (
    "Index", "Subindex", "Value", "Raw Value", "Raw Hex Value", "Parameter Type",
    "Text", "Unit", "Min.", "Max.", "Factory Setting", "Controller Inhibit",
    "Access", "Display Value", "Display Value Factory Setting", "Display parameter",
    "Display factor",
)
PALETTES = {
    "light": dict(bg="#f5f6fa", surface="#ffffff", text="#202638", muted="#737b90",
                  border="#e3e6ef", accent="#6554d9", hover="#5545c2", soft="#eeebfc",
                  stripe="#f9faff", group="#eeeff8", redbg="#fff0f0", red="#b93548",
                  green="#168064", header="#191d30", headtext="#ffffff", disabled="#e4e5ed"),
    "dark": dict(bg="#111420", surface="#1b2030", text="#edf0fa", muted="#a0aac0",
                 border="#30384e", accent="#a395ff", hover="#b6aaff", soft="#302b4c",
                 stripe="#202638", group="#2a2f45", redbg="#422631", red="#ff9caa",
                 green="#65d5ae", header="#0c0f19", headtext="#ffffff", disabled="#30364a"),
}


class Tooltip:
    """Small hover hint, also available when its button is disabled."""
    def __init__(self, widget, text):
        self.widget, self.text = widget, text
        self.timer = self.window = None
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<FocusIn>", self.schedule, add="+")
        for event in ("<Leave>", "<FocusOut>", "<ButtonPress>", "<Destroy>"):
            widget.bind(event, self.hide, add="+")

    def schedule(self, event=None):
        self.hide()
        self.timer = self.widget.after(450, self.show)

    def show(self):
        self.timer = None
        if not self.widget.winfo_exists():
            return
        self.window = tk.Toplevel(self.widget)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.geometry(f"+{self.widget.winfo_rootx()}+{self.widget.winfo_rooty() + self.widget.winfo_height() + 8}")
        tk.Label(self.window, text=self.text, bg="#101525", fg="#ffffff",
                 font=("Segoe UI", 10), padx=12, pady=9, justify="left").pack()

    def hide(self, event=None):
        if self.timer is not None:
            self.widget.after_cancel(self.timer)
            self.timer = None
        if self.window is not None:
            self.window.destroy()
            self.window = None


class ConverterApp(TkinterDnD.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Lenze CSV to LASAL")
        self.geometry("1320x900")
        self.minsize(1040, 740)
        self.rows: dict[str, ReviewRow] = {}
        self.input_path: Path | None = None
        self.output_path = tk.StringVar()
        self.status = tk.StringVar()
        self.detail = tk.StringVar()
        self.total_count, self.ready_count, self.error_count = (tk.StringVar(value="0") for _ in range(3))
        self.settings_path = default_settings_path()
        self.theme = load_theme(self.settings_path)
        self.editor = None
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.apply_theme()
        self.header = ttk.Frame(self, style="Header.TFrame", padding=(28, 18))
        self.header.pack(fill="x")
        ttk.Label(self.header, text="L /", style="Brand.TLabel").pack(side="left", padx=(0, 14))
        identity = ttk.Frame(self.header, style="Header.TFrame")
        identity.pack(side="left")
        ttk.Label(identity, text="LENZE  /  LASAL", style="HeaderTitle.TLabel").pack(anchor="w")
        ttk.Label(identity, text="Parameter table converter", style="HeaderMuted.TLabel").pack(anchor="w", pady=(3, 0))
        self.theme_button = self.button(self.header, "Light mode" if self.theme == "dark" else "Dark mode", self.toggle_theme,
                                       "Switch between light and dark appearance.", "Header.TButton")
        self.theme_button.pack(side="right")
        ttk.Label(self.header, text="IMPORT   /   REVIEW   /   EXPORT", style="HeaderMuted.TLabel").pack(side="right", padx=30)
        self.container = ttk.Frame(self, padding=(28, 24))
        self.container.pack(fill="both", expand=True)
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self.on_drop)
        self.bind_shortcuts()
        self.show_picker()

    def apply_theme(self):
        p = self.palette = PALETTES[self.theme]
        self.configure(bg=p["bg"])
        s = self.style
        s.configure("TFrame", background=p["bg"])
        s.configure("Card.TFrame", background=p["surface"])
        s.configure("Header.TFrame", background=p["header"])
        s.configure("TLabel", background=p["bg"], foreground=p["text"], font=("Segoe UI", 10))
        for name, bg, fg, font in (
            ("Title", p["bg"], p["text"], ("Segoe UI", 26, "bold")),
            ("Muted", p["bg"], p["muted"], ("Segoe UI", 10)),
            ("Eyebrow", p["bg"], p["accent"], ("Segoe UI", 9, "bold")),
            ("Card", p["surface"], p["text"], ("Segoe UI", 10)),
            ("CardMuted", p["surface"], p["muted"], ("Segoe UI", 10)),
            ("CardTitle", p["surface"], p["text"], ("Segoe UI", 12, "bold")),
            ("Stat", p["surface"], p["text"], ("Segoe UI", 26, "bold")),
            ("ReadyStat", p["surface"], p["green"], ("Segoe UI", 26, "bold")),
            ("ErrorStat", p["surface"], p["red"], ("Segoe UI", 26, "bold")),
            ("Brand", p["header"], "#b3a5ff", ("Segoe UI", 24, "bold")),
            ("HeaderTitle", p["header"], p["headtext"], ("Segoe UI", 11, "bold")),
            ("HeaderMuted", p["header"], "#9da6c1", ("Segoe UI", 9)),
        ):
            s.configure(name + ".TLabel", background=bg, foreground=fg, font=font)
        s.configure("TButton", font=("Segoe UI", 10), padding=(14, 9), borderwidth=1,
                    relief="flat", background=p["surface"], foreground=p["text"],
                    bordercolor=p["border"], focusthickness=2, focuscolor=p["accent"])
        s.map("TButton", background=[("disabled", p["disabled"]), ("active", p["soft"])],
              foreground=[("disabled", p["muted"])], bordercolor=[("active", p["accent"])])
        s.configure("Primary.TButton", background=p["accent"], foreground="#ffffff" if self.theme == "light" else "#171227", borderwidth=0)
        s.map("Primary.TButton", background=[("disabled", p["disabled"]), ("active", p["hover"])],
              foreground=[("disabled", p["muted"])])
        s.configure("Header.TButton", background="#2c3149", foreground="#ffffff", borderwidth=0)
        s.map("Header.TButton", background=[("active", "#414764")], foreground=[("active", "#ffffff")])
        s.configure("TEntry", fieldbackground=p["bg"], foreground=p["text"],
                    insertcolor=p["text"], bordercolor=p["border"], padding=10,
                    lightcolor=p["border"], darkcolor=p["border"])
        s.map("TEntry", bordercolor=[("focus", p["accent"])])
        s.configure("Treeview", background=p["surface"], fieldbackground=p["surface"],
                    foreground=p["text"], rowheight=36, font=("Segoe UI", 10),
                    borderwidth=0, relief="flat", bordercolor=p["border"],
                    lightcolor=p["surface"], darkcolor=p["surface"])
        s.map("Treeview", background=[("selected", p["accent"])],
              foreground=[("selected", "#ffffff" if self.theme == "light" else "#171227")])
        s.configure("Treeview.Heading", background=p["surface"], foreground=p["muted"],
                    font=("Segoe UI", 9, "bold"), padding=(10, 12), relief="flat", borderwidth=0)
        s.map("Treeview.Heading", background=[("active", p["soft"])])
        for direction in ("Vertical", "Horizontal"):
            s.configure(direction + ".TScrollbar", background=p["border"], troughcolor=p["surface"],
                        borderwidth=0, arrowcolor=p["muted"], relief="flat", width=12,
                        bordercolor=p["surface"], lightcolor=p["surface"], darkcolor=p["surface"])
            s.map(direction + ".TScrollbar", background=[("active", p["muted"])])

    def button(self, parent, text, command, hint, style="TButton"):
        button = ttk.Button(parent, text=text, command=command, style=style, cursor="hand2")
        Tooltip(button, hint)
        return button

    def table_state(self):
        if not self.input_path or not hasattr(self, "table") or not self.table.winfo_exists():
            return None
        return dict(opened={self.table.item(k, "text"): self.table.item(k, "open") for k in self.table.get_children()},
                    selected=self.table.selection(), focus=self.table.focus(),
                    x=self.table.xview()[0], y=self.table.yview()[0], detail=self.detail.get())

    def restore_table_state(self, state):
        if not state:
            return
        for parent in self.table.get_children():
            name = self.table.item(parent, "text")
            if name in state["opened"]:
                self.table.item(parent, open=state["opened"][name])
        selection = [k for k in state["selected"] if self.table.exists(k)]
        self.table.selection_set(selection)
        if self.table.exists(state["focus"]):
            self.table.focus(state["focus"])
        self.table.xview_moveto(state["x"])
        self.table.yview_moveto(state["y"])
        self.detail.set(state["detail"])

    def toggle_theme(self):
        self.finish_edit()
        state = self.table_state()
        self.theme = "dark" if self.theme == "light" else "light"
        save_theme(self.settings_path, self.theme)
        self.apply_theme()
        self.theme_button.configure(text="Light mode" if self.theme == "dark" else "Dark mode")
        if self.input_path:
            self.show_review()
            self.restore_table_state(state)
        else:
            self.show_picker()

    def bind_shortcuts(self):
        self.bind("<Control-o>", lambda e: self.shortcut(self.choose_file))
        self.bind("<Control-s>", lambda e: self.shortcut(self.export, review=True))
        self.bind("<Control-e>", lambda e: self.shortcut(self.select_invalid, review=True, table_only=True))
        self.bind("<Delete>", lambda e: self.shortcut(self.remove_selected, review=True, table_only=True))
        self.bind("<F4>", lambda e: self.shortcut(lambda: self.next_error(bool(e.state & 0x0005)), review=True))
        self.bind("<Shift-F4>", lambda e: self.shortcut(lambda: self.next_error(True), review=True))
        self.bind("<Control-F4>", lambda e: self.shortcut(lambda: self.next_error(True), review=True))

    def shortcut(self, action, review=False, table_only=False):
        if review and self.input_path is None:
            return "break"
        # Text controls retain native Delete and text editing shortcuts.
        if table_only and isinstance(self.focus_get(), (tk.Entry, ttk.Entry, tk.Text)):
            return None
        action()
        return "break"

    def clear_page(self):
        self.finish_edit()
        for child in self.container.winfo_children():
            child.destroy()

    def enable_file_drop(self, widget):
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", self.on_drop)
        for child in widget.winfo_children():
            self.enable_file_drop(child)

    def show_picker(self):
        self.clear_page()
        p = self.palette
        ttk.Label(self.container, text="01 / IMPORT", style="Eyebrow.TLabel").pack(anchor="w")
        ttk.Label(self.container, text="Your parameters. Ready for LASAL.", style="Title.TLabel").pack(anchor="w", pady=(7, 6))
        ttk.Label(self.container, text="Bring in a Lenze CSV, review the values, and export a table in a few clicks.", style="Muted.TLabel").pack(anchor="w")
        drop = tk.Canvas(self.container, bg=p["surface"], highlightthickness=0)
        drop.pack(fill="both", expand=True, pady=(28, 20))
        center = tk.Frame(drop, bg=p["surface"])
        icon = tk.Canvas(center, width=86, height=86, bg=p["surface"], highlightthickness=0)
        icon.pack(pady=(0, 20))
        icon.create_oval(2, 2, 84, 84, fill=p["soft"], outline="")
        icon.create_line(32, 22, 51, 22, 60, 32, 60, 62, 27, 62, 27, 22, 32, 22, fill=p["accent"], width=2)
        icon.create_line(50, 22, 50, 33, 60, 33, fill=p["accent"], width=2)
        icon.create_line(43, 53, 43, 37, fill=p["accent"], width=2)
        icon.create_line(36, 44, 43, 37, 50, 44, fill=p["accent"], width=2)
        tk.Label(center, text="Drop your CSV here", bg=p["surface"], fg=p["text"], font=("Segoe UI", 22, "bold")).pack()
        tk.Label(center, text="or browse for a parameter export on your computer", bg=p["surface"], fg=p["muted"], font=("Segoe UI", 11)).pack(pady=(10, 24))
        self.button(center, "Choose CSV file  →", self.choose_file, "Open a Lenze CSV export.\nCtrl+O", "Primary.TButton").pack()
        tk.Label(center, text="CSV files  ·  Your source file stays unchanged", bg=p["surface"], fg=p["muted"], font=("Segoe UI", 9)).pack(pady=(20, 0))
        window = drop.create_window(0, 0, window=center, anchor="center")
        def resize(event):
            drop.delete("outline")
            drop.create_rectangle(20, 20, event.width - 20, event.height - 20, outline=p["border"], width=2, dash=(6, 5), tags="outline")
            drop.coords(window, event.width / 2, event.height / 2)
        drop.bind("<Configure>", resize)
        ttk.Label(self.container, text="01  Import your CSV              02  Review by category              03  Export your LASAL table", style="Muted.TLabel").pack(pady=(0, 6))
        self.enable_file_drop(self.container)

    def choose_file(self):
        chosen = filedialog.askopenfilename(parent=self, title="Open Lenze CSV", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if chosen:
            self.load_file(Path(chosen))

    def on_drop(self, event):
        paths = self.tk.splitlist(event.data)
        if len(paths) != 1:
            messagebox.showinfo("Choose one file", "Please drop one CSV file at a time.", parent=self)
            return
        self.load_file(Path(paths[0]))

    def load_file(self, path):
        try:
            rows = read_review_csv(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Unable to open CSV", str(exc), parent=self)
            return
        self.cancel_edit()
        self.input_path = path
        self.rows = {str(i): row for i, row in enumerate(rows)}
        self.output_path.set(str(path.with_name(f"lasal_{path.stem}.txt")))
        self.show_review()
        self.table.focus_set()

    def show_review(self):
        self.clear_page()
        heading = ttk.Frame(self.container)
        heading.pack(fill="x")
        title = ttk.Frame(heading)
        title.pack(side="left", fill="x", expand=True)
        ttk.Label(title, text="02 / REVIEW", style="Eyebrow.TLabel").pack(anchor="w")
        ttk.Label(title, text="Review parameters", style="Title.TLabel").pack(anchor="w", pady=(4, 4))
        ttk.Label(title, text=self.input_path.name, style="Muted.TLabel").pack(anchor="w")
        self.button(heading, "Open another CSV", self.choose_file, "Replace the loaded file, or drop a CSV anywhere.\nCtrl+O").pack(side="right")
        stats = ttk.Frame(self.container)
        stats.pack(fill="x", pady=(20, 18))
        for i, (label, variable, style) in enumerate((
            ("TOTAL PARAMETERS", self.total_count, "Stat.TLabel"),
            ("READY TO EXPORT", self.ready_count, "ReadyStat.TLabel"),
            ("NEEDS ATTENTION", self.error_count, "ErrorStat.TLabel"),
        )):
            stats.columnconfigure(i, weight=1, uniform="stats")
            card = ttk.Frame(stats, style="Card.TFrame", padding=(20, 12))
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 7, 0 if i == 2 else 7))
            ttk.Label(card, text=label, style="CardMuted.TLabel").pack(anchor="w")
            ttk.Label(card, textvariable=variable, style=style).pack(anchor="w", pady=(2, 0))
        panel = ttk.Frame(self.container, style="Card.TFrame", padding=(14, 12))
        panel.pack(fill="both", expand=True)
        toolbar = ttk.Frame(panel, style="Card.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Label(toolbar, text="Parameter library", style="CardTitle.TLabel").pack(side="left")
        self.remove_button = self.button(toolbar, "Remove selected", self.remove_selected, "Remove selected rows or categories from the output.\nDelete")
        self.remove_button.pack(side="right", padx=(8, 0))
        self.button(toolbar, "Select errors", self.select_invalid, "Select every invalid row.\nCtrl+E").pack(side="right", padx=(8, 0))
        self.next_error_button = self.button(toolbar, "Next error  ↓", self.next_error, "Jump to the next error.  F4\nShift+F4 or Ctrl+F4: add the next error to the selection.\nShift/Ctrl + click: also add the next error.")
        self.next_error_button.pack(side="right", padx=(8, 0))
        self.next_error_button.bind("<Shift-Button-1>", lambda e: self.add_error_click())
        self.next_error_button.bind("<Control-Button-1>", lambda e: self.add_error_click())
        frame = ttk.Frame(panel, style="Card.TFrame")
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        headings = ("CSV line", "Validation") + COLUMNS
        order = ("Index", "Subindex", "Raw Value", "Value", "Parameter Type", "Validation", "Unit", "Display parameter", "Display factor", "CSV line")
        display = order + tuple(column for column in headings if column not in order)
        self.table = ttk.Treeview(frame, columns=headings, displaycolumns=display, show="tree headings", selectmode="extended", height=6)
        self.table.heading("#0", text="CATEGORY / PARAMETER")
        self.table.column("#0", width=330, minwidth=180, stretch=False)
        for name in headings:
            self.table.heading(name, text=name.upper())
            self.table.column(name, width=270 if name in ("Text", "Validation") else 125, minwidth=65, stretch=False)
        for name in ("Index", "Subindex", "Unit", "CSV line"):
            self.table.column(name, width=85)
        p = self.palette
        self.table.tag_configure("invalid", background=p["redbg"], foreground=p["red"])
        self.table.tag_configure("category", background=p["group"], font=("Segoe UI", 10, "bold"))
        self.table.tag_configure("stripe", background=p["stripe"])
        self.table.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(frame, orient="vertical", command=self.table.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=self.table.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.populate_table()
        self.table.bind("<<TreeviewSelect>>", self.on_selection)
        self.table.bind("<Double-1>", self.begin_edit)
        ttk.Label(panel, text="Double-click a cell to edit  ·  Enter to apply  ·  Escape to cancel", style="CardMuted.TLabel").pack(anchor="w", pady=(9, 0))
        self.detail.set("Expand a category to review its rows. Select errors to inspect or remove them.")
        detail_label = ttk.Label(self.container, textvariable=self.detail, style="Muted.TLabel", wraplength=1180)
        save = ttk.Frame(self.container, style="Card.TFrame", padding=(18, 14))
        # Reserve space for export first, so the growing table cannot hide it.
        save.pack(side="bottom", fill="x", before=panel)
        detail_label.pack(side="bottom", anchor="w", pady=(12, 12), before=panel)
        labels = ttk.Frame(save, style="Card.TFrame")
        labels.pack(fill="x", pady=(0, 8))
        ttk.Label(labels, text="03 / EXPORT", style="CardTitle.TLabel").pack(side="left")
        self.export_hint = tk.StringVar()
        ttk.Label(labels, textvariable=self.export_hint, style="CardMuted.TLabel").pack(side="right")
        destination = ttk.Frame(save, style="Card.TFrame")
        destination.pack(fill="x")
        ttk.Entry(destination, textvariable=self.output_path).pack(side="left", fill="x", expand=True)
        self.button(destination, "Browse", self.choose_output, "Choose the TXT filename and output folder.").pack(side="left", padx=10)
        self.export_button = self.button(destination, "Create LASAL TXT  →", self.export, "Export the remaining valid parameters.\nCtrl+S", "Primary.TButton")
        self.export_button.pack(side="left")
        self.refresh_status()
        self.enable_file_drop(self.container)

    def group_for(self, row):
        if row.parameter is not None:
            return row.parameter.group_name
        display = row.fields[15].strip().upper() if len(row.fields) > 15 else ""
        display = display or get_display_parameter_from_fields(row.fields[17:])
        return get_group_name(get_group_number(display))

    def populate_table(self):
        grouped = {}
        for key, row in self.rows.items():
            grouped.setdefault(self.group_for(row), []).append((key, row))
        for number, name in enumerate(sorted(grouped)):
            parent = f"group:{number}"
            self.table.insert("", "end", iid=parent, text=name, open=True, tags=("category",))
            for position, (key, row) in enumerate(grouped[name]):
                self.insert_parameter(parent, key, row, position)

    def insert_parameter(self, parent, key, row, position=0):
        fields = (row.fields + [""] * len(COLUMNS))[:len(COLUMNS)]
        tags = ("invalid",) if row.error else (("stripe",) if position % 2 else ())
        self.table.insert(parent, "end", iid=key, text=fields[6] or f"CSV line {row.line_number}",
                          values=[row.line_number, row.error or "Ready"] + fields, tags=tags)

    def refresh_status(self):
        for parent in self.table.get_children():
            keys = self.table.get_children(parent)
            if not keys:
                self.table.delete(parent)
                continue
            errors = sum(bool(self.rows[key].error) for key in keys)
            tags = ("invalid", "category") if errors else ("category",)
            self.table.item(parent, values=["", f"{len(keys)} rows / {errors} errors"], tags=tags)
        invalid = sum(bool(row.error) for row in self.rows.values())
        self.total_count.set(str(len(self.rows)))
        self.ready_count.set(str(len(self.rows) - invalid))
        self.error_count.set(str(invalid))
        self.status.set(f"{len(self.rows)} rows / {len(self.rows) - invalid} ready / {invalid} invalid")
        self.export_hint.set(f"Resolve or remove {invalid} invalid rows to export" if invalid else ("All remaining parameters are ready" if self.rows else "Load a CSV to add parameters"))
        self.export_button.configure(state="normal" if self.rows and not invalid else "disabled")
        self.next_error_button.configure(state="normal" if invalid else "disabled")
        self.remove_button.configure(state="normal" if self.table.selection() else "disabled")

    def on_selection(self, event=None):
        selected = self.table.selection()
        if len(selected) == 1 and selected[0] in self.rows:
            row = self.rows[selected[0]]
            self.detail.set(f"CSV line {row.line_number}: {row.error or 'Ready to export.'}")
        elif len(selected) == 1 and self.table.exists(selected[0]):
            parent = selected[0]
            count = sum(bool(self.rows[key].error) for key in self.table.get_children(parent))
            self.detail.set(f"{self.table.item(parent, 'text')}: {count} invalid rows. Removing this category excludes all its parameters.")
        else:
            self.detail.set(f"{len(selected)} rows selected. Remove selected rows to exclude them from the output.")
        self.refresh_status()

    def select_invalid(self):
        self.finish_edit()
        keys = [key for parent in self.table.get_children() for key in self.table.get_children(parent) if self.rows[key].error]
        self.table.selection_set(keys)
        for key in keys:
            self.table.item(self.table.parent(key), open=True)
        if keys:
            self.table.focus(keys[0])
            self.table.see(keys[0])
        self.table.focus_set()
        self.on_selection()

    def next_error(self, additive=False):
        self.finish_edit()
        keys = [key for parent in self.table.get_children() for key in self.table.get_children(parent)]
        current = self.table.focus()
        start = keys.index(current) + 1 if current in keys else 0
        for key in keys[start:] + keys[:start]:
            if self.rows[key].error:
                self.table.item(self.table.parent(key), open=True)
                if additive:
                    self.table.selection_add(key)
                else:
                    self.table.selection_set(key)
                self.table.focus(key)
                self.table.see(key)
                self.table.focus_set()
                self.on_selection()
                return

    def add_error_click(self):
        self.next_error(True)
        return "break"

    def remove_selected(self):
        self.finish_edit()
        keys = set()
        for selected in self.table.selection():
            keys.update([selected] if selected in self.rows else self.table.get_children(selected))
        for key in keys:
            self.table.delete(key)
            del self.rows[key]
        self.refresh_status()
        self.on_selection()
        self.table.focus_set()

    def begin_edit(self, event):
        if self.table.identify_region(event.x, event.y) != "cell":
            return
        key = self.table.identify_row(event.y)
        column = self.table.identify_column(event.x)
        if key not in self.rows or column == "#0":
            return
        name = self.table["displaycolumns"][int(column[1:]) - 1]
        if name not in COLUMNS:
            return "break"
        self.open_cell_editor(key, name)
        return "break"

    def open_cell_editor(self, key, name):
        self.finish_edit()
        position = list(self.table["displaycolumns"]).index(name) + 1
        box = self.table.bbox(key, f"#{position}")
        if not box:
            return
        x, y, width, height = box
        self.table.selection_set(key)
        self.table.focus(key)
        index = COLUMNS.index(name)
        fields = self.rows[key].fields
        p = self.palette
        editor = tk.Entry(self.table, bg=p["surface"], fg=p["text"], insertbackground=p["text"],
                          relief="flat", highlightthickness=2, highlightcolor=p["accent"],
                          highlightbackground=p["accent"], font=("Segoe UI", 10))
        editor.insert(0, fields[index] if index < len(fields) else "")
        editor.place(x=x, y=y, width=width, height=height)
        self.editor = (editor, key, index)
        editor.bind("<Return>", lambda e: self.finish_edit())
        editor.bind("<Escape>", lambda e: self.cancel_edit())
        editor.bind("<FocusOut>", lambda e: self.finish_edit())
        editor.focus_set()
        editor.selection_range(0, "end")

    def finish_edit(self):
        if self.editor is None:
            return "break"
        editor, key, index = self.editor
        self.editor = None
        value = editor.get()
        editor.destroy()
        if key in self.rows:
            row = self.rows[key]
            self.rows[key] = edit_parameter_fields(row.fields, index, value, row.line_number)
            state = self.table_state()
            for parent in self.table.get_children():
                self.table.delete(parent)
            self.populate_table()
            self.restore_table_state(state)
            self.on_selection()
        self.table.focus_set()
        return "break"

    def cancel_edit(self):
        if self.editor is not None:
            editor, _, _ = self.editor
            self.editor = None
            editor.destroy()
            self.table.focus_set()
        return "break"

    def choose_output(self):
        current = Path(self.output_path.get())
        chosen = filedialog.asksaveasfilename(parent=self, title="Save LASAL table", initialdir=str(current.parent), initialfile=current.name, defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if chosen:
            self.output_path.set(chosen)

    def export(self):
        self.finish_edit()
        if not self.rows or any(row.error for row in self.rows.values()):
            return
        if not self.output_path.get().strip():
            self.choose_output()
            if not self.output_path.get().strip():
                return
        path = Path(self.output_path.get().strip())
        if path.suffix.lower() != ".txt":
            messagebox.showerror("Choose a TXT file", "The output filename must end in .txt.", parent=self)
            return
        if path.resolve() == self.input_path.resolve():
            messagebox.showerror("Choose another location", "The output cannot replace the input CSV.", parent=self)
            return
        if path.exists() and not messagebox.askyesno("Replace existing file?", f"Replace {path}?", parent=self):
            return
        groups = {}
        for row in self.rows.values():
            parameter = row.parameter
            groups.setdefault(parameter.group_name, []).append(parameter)
        try:
            build_output_file(groups, path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Unable to save table", str(exc), parent=self)
            return
        messagebox.showinfo("LASAL table created", f"Saved {len(self.rows)} parameters to:\n{path}", parent=self)
