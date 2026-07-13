import ctypes
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from itertools import chain
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from hidpi_tk import DPIAwareTk

from ..i18n import i18n, tr
from ..save.locations import SaveLocation, iter_default_save_locations
from ..save.logic import CustomVarEntry, MetaVarEntry, SaveBinaryEditor, SaveView
from ..update import UpdateInfo, check_for_update
from .models import EntryModel, TableRow, section_labels
from .smooth_sheet import SmoothSheet
from .theme import configure_theme

APP_USER_MODEL_ID = "CTS.SaveEditor"


def resource_path(relative_path: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path

    return Path(__file__).resolve().parents[2] / relative_path


def set_windows_app_user_model_id() -> None:
    if sys.platform != "win32":
        return

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except AttributeError, OSError:
        pass


class SaveEditorApp:
    LEFT_PANEL_MIN_WIDTH = 280
    CENTER_PANEL_MIN_WIDTH = 720
    RIGHT_PANEL_MIN_WIDTH = 420
    TABLE_MIN_COLUMN_WIDTHS = (96, 130, 220, 160, 280)

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(tr("app.title"))
        self.root.minsize(1360, 760)
        self._set_window_icon()
        self._set_default_window_state()

        self.editor: SaveBinaryEditor | None = None
        self.view: SaveView | None = None
        self.current_file: Path | None = None
        self.dirty = False
        self._suspend_render = False
        self.item_map: dict[str, EntryModel] = {}
        self.default_locations = iter_default_save_locations()
        self.section_labels = section_labels()
        self.section_reverse_labels = {
            label: key for key, label in self.section_labels.items()
        }
        self.locale_display_var = tk.StringVar()
        self.editor_mode = "text"
        self._load_ticket = 0
        self._is_loading = False
        self._localized_labels: dict[str, ttk.Label] = {}
        self._localized_buttons: dict[str, ttk.Button] = {}
        self._inspector_labels: dict[str, ttk.Label] = {}
        self._update_dialog_open = False
        self._table_resize_after_id: str | None = None
        self._last_table_width = 0

        self._build_state()
        self.palette = configure_theme(self.root)
        self._build_ui()
        self._bind_shortcuts()
        self.root.after(1500, self.check_for_updates_on_startup)

    def _set_window_icon(self) -> None:
        icon_path = resource_path("cts/icon/icon.png")
        fallback_icon_path = resource_path("cts/icon/icon.ico")

        try:
            icon = tk.PhotoImage(file=icon_path)
            self.root.iconphoto(True, icon)
            self._window_icon = icon
        except tk.TclError:
            try:
                self.root.iconbitmap(default=str(fallback_icon_path))
            except tk.TclError:
                pass

    def _set_default_window_state(self) -> None:
        try:
            if sys.platform == "win32":
                self.root.state("zoomed")
            else:
                self.root.attributes("-zoomed", True)
        except tk.TclError:
            pass

    def _build_state(self) -> None:
        self.status_var = tk.StringVar(value=tr("message.waiting_load"))
        self.count_var = tk.StringVar(value=tr("common.items_count", shown=0, total=0))
        self.path_var = tk.StringVar(value=tr("common.empty_file"))
        self.section_var = tk.StringVar(value=self.section_labels["all"])
        self.category_var = tk.StringVar(value=tr("section.all"))
        self.filter_var = tk.StringVar()
        self.key_var = tk.StringVar(value=tr("common.unselected"))
        self.value_var = tk.StringVar()
        self.original_value_var = tk.StringVar(value=tr("common.dash"))
        self.value_type_var = tk.StringVar(value=tr("inspector.value_type_text"))
        self.category_note_var = tk.StringVar(value=tr("common.no_category_note"))
        self.selected_source_var = tk.StringVar(value=tr("common.dash"))
        self.selected_category_var = tk.StringVar(value=tr("common.dash"))
        self.search_hint_var = tk.StringVar(value=tr("filters.hint"))
        self.stat_vars = {
            "items": tk.StringVar(value="0"),
            "custom": tk.StringVar(value="0"),
            "meta": tk.StringVar(value="0"),
            "visible": tk.StringVar(value="0"),
        }

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, style="App.TFrame", padding=(14, 12, 14, 14))
        shell.pack(fill=tk.BOTH, expand=True)

        self._build_topbar(shell)
        self._build_dashboard(shell)

        content = ttk.Panedwindow(shell, orient=tk.HORIZONTAL)
        content.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.content_pane = content

        left = ttk.Frame(content, style="App.TFrame")
        center = ttk.Frame(content, style="App.TFrame")
        right = ttk.Frame(content, style="App.TFrame")
        content.add(left, weight=18)
        content.add(center, weight=74)
        content.add(right, weight=16)

        self._build_left_panel(left)
        self._build_center_panel(center)
        self._build_right_panel(right)
        self._init_pane_constraints(left, center, right)
        self._update_dashboard()

    def _build_topbar(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent, style="App.TFrame")
        top.pack(fill=tk.X)

        title_box = ttk.Frame(top, style="App.TFrame")
        title_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.header_title_label = ttk.Label(
            title_box, text=tr("app.title"), style="Header.TLabel"
        )
        self.header_title_label.pack(anchor="w")
        self.header_subtitle_label = ttk.Label(
            title_box,
            text=tr("app.header_subtitle"),
            style="SubHeader.TLabel",
        )
        self.header_subtitle_label.pack(anchor="w", pady=(2, 0))

        action_box = ttk.Frame(top, style="App.TFrame")
        action_box.pack(side=tk.RIGHT)
        self.locale_display_var.set(self._locale_display_value(i18n.get_locale()))
        locale_values = [
            self._locale_display_value(locale) for locale in i18n.available_locales()
        ]
        self.locale_box = ttk.Combobox(
            action_box,
            textvariable=self.locale_display_var,
            values=locale_values,
            width=18,
            state="readonly",
        )
        self.locale_box.pack(side=tk.LEFT, padx=(0, 8))
        self.locale_box.bind("<<ComboboxSelected>>", self._on_language_changed)
        self._bind_combobox_focus_behavior(self.locale_box)
        actions = (
            ("buttons.open", self.open_file, "TButton"),
            ("buttons.reload", self.reload_current, "TButton"),
            ("buttons.save_in_place", self.save_in_place, "Primary.TButton"),
            ("buttons.save_as", self.save_as, "TButton"),
            ("buttons.backup", self.make_backup, "TButton"),
        )
        for key, command, style_name in actions:
            button = ttk.Button(
                action_box,
                text=tr(key),
                command=command,
                style=style_name,
            )
            button.pack(side=tk.LEFT, padx=(8, 0))
            self._localized_buttons[key] = button

    def _build_dashboard(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent, style="App.TFrame")
        bar.pack(fill=tk.X, pady=(12, 0))

        file_panel = ttk.Frame(bar, style="Panel.TFrame", padding=12)
        file_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._localized_labels["dashboard.current_file"] = ttk.Label(
            file_panel, text=tr("dashboard.current_file"), style="PanelTitle.TLabel"
        )
        self._localized_labels["dashboard.current_file"].pack(anchor="w")
        ttk.Label(file_panel, textvariable=self.path_var, style="Data.TLabel").pack(
            anchor="w", pady=(8, 2)
        )
        ttk.Label(
            file_panel, textvariable=self.status_var, style="PanelCaption.TLabel"
        ).pack(anchor="w")

        stats_frame = ttk.Frame(bar, style="App.TFrame")
        stats_frame.pack(side=tk.RIGHT)
        for key, value in (
            ("dashboard.total_items", "items"),
            ("dashboard.string_items", "custom"),
            ("dashboard.numeric_items", "meta"),
            ("dashboard.visible_items", "visible"),
        ):
            card = ttk.Frame(stats_frame, style="PanelAlt.TFrame", padding=(14, 10))
            card.pack(side=tk.LEFT, padx=(10, 0))
            label = ttk.Label(card, text=tr(key), style="StatLabel.TLabel")
            label.pack(anchor="w")
            self._localized_labels[key] = label
            ttk.Label(
                card, textvariable=self.stat_vars[value], style="StatValue.TLabel"
            ).pack(anchor="w", pady=(6, 0))

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        quick = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        quick.grid(row=0, column=0, sticky="nsew")
        quick.columnconfigure(0, weight=1)
        quick.columnconfigure(1, weight=1)

        self._localized_labels["left_panel.quick_access"] = ttk.Label(
            quick, text=tr("left_panel.quick_access"), style="PanelTitle.TLabel"
        )
        self._localized_labels["left_panel.quick_access"].grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        self._localized_labels["left_panel.quick_access_desc"] = ttk.Label(
            quick,
            text=tr("left_panel.quick_access_desc"),
            style="PanelCaption.TLabel",
        )
        self._localized_labels["left_panel.quick_access_desc"].grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 10)
        )

        self.location_list = tk.Listbox(
            quick,
            activestyle="none",
            height=8,
            font=("Consolas", 10),
            exportselection=False,
        )
        self.location_list.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self.location_list.bind("<Double-Button-1>", self._open_selected_location)
        quick.rowconfigure(2, weight=1)

        self._localized_buttons["buttons.open_selected"] = ttk.Button(
            quick,
            text=tr("buttons.open_selected"),
            command=self._open_selected_location,
        )
        self._localized_buttons["buttons.open_selected"].grid(
            row=3, column=0, sticky="ew", pady=(10, 0), padx=(0, 4)
        )
        self._localized_buttons["buttons.reveal_path"] = ttk.Button(
            quick,
            text=tr("buttons.reveal_path"),
            command=self._reveal_selected_location,
        )
        self._localized_buttons["buttons.reveal_path"].grid(
            row=3, column=1, sticky="ew", pady=(10, 0), padx=(4, 0)
        )
        self._populate_location_list()

        guide = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        guide.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        self._localized_labels["left_panel.guide_title"] = ttk.Label(
            guide, text=tr("left_panel.guide_title"), style="PanelTitle.TLabel"
        )
        self._localized_labels["left_panel.guide_title"].pack(anchor="w")
        guide_lines = (
            "left_panel.guide_1",
            "left_panel.guide_2",
            "left_panel.guide_3",
            "left_panel.guide_4",
        )
        for index, key in enumerate(guide_lines):
            label = ttk.Label(guide, text=tr(key), style="Muted.TLabel")
            label.pack(anchor="w", pady=(8 if index == 0 else 4, 0))
            self._localized_labels[key] = label

        self._localized_labels["left_panel.shortcuts"] = ttk.Label(
            guide, text=tr("left_panel.shortcuts"), style="Accent.TLabel"
        )
        self._localized_labels["left_panel.shortcuts"].pack(anchor="w", pady=(18, 4))
        for key in (
            "left_panel.shortcut_open",
            "left_panel.shortcut_save",
            "left_panel.shortcut_reload",
            "left_panel.shortcut_search",
        ):
            label = ttk.Label(guide, text=tr(key), style="Muted.TLabel")
            label.pack(anchor="w", pady=2)
            self._localized_labels[key] = label

    def _build_center_panel(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        filters = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        filters.grid(row=0, column=0, sticky="ew")

        self._localized_labels["filters.title"] = ttk.Label(
            filters, text=tr("filters.title"), style="PanelTitle.TLabel"
        )
        self._localized_labels["filters.title"].grid(row=0, column=0, sticky="w")
        ttk.Label(
            filters, textvariable=self.search_hint_var, style="PanelCaption.TLabel"
        ).grid(row=0, column=1, columnspan=5, sticky="e")

        self._localized_labels["filters.source"] = ttk.Label(
            filters, text=tr("filters.source"), style="Muted.TLabel"
        )
        self._localized_labels["filters.source"].grid(
            row=1, column=0, sticky="w", pady=(10, 0)
        )
        self.section_box = ttk.Combobox(
            filters,
            textvariable=self.section_var,
            values=list(self.section_labels.values()),
            width=12,
            state="readonly",
        )
        self.section_box.grid(row=2, column=0, sticky="ew", padx=(0, 8), pady=(4, 0))
        self.section_box.bind("<<ComboboxSelected>>", lambda _e: self._request_render())
        self._bind_combobox_focus_behavior(self.section_box)

        self._localized_labels["filters.category"] = ttk.Label(
            filters, text=tr("filters.category"), style="Muted.TLabel"
        )
        self._localized_labels["filters.category"].grid(
            row=1, column=1, sticky="w", pady=(10, 0)
        )
        self.category_box = ttk.Combobox(
            filters,
            textvariable=self.category_var,
            values=[tr("section.all")],
            width=18,
            state="readonly",
        )
        self.category_box.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=(4, 0))
        self.category_box.bind(
            "<<ComboboxSelected>>", lambda _e: self._request_render()
        )
        self._bind_combobox_focus_behavior(self.category_box)

        self._localized_labels["filters.search"] = ttk.Label(
            filters, text=tr("filters.search"), style="Muted.TLabel"
        )
        self._localized_labels["filters.search"].grid(
            row=1, column=2, sticky="w", pady=(10, 0)
        )
        self.filter_var.trace_add("write", lambda *_: self._request_render())
        self.search_entry = ttk.Entry(filters, textvariable=self.filter_var)
        self.search_entry.grid(row=2, column=2, sticky="ew", padx=(0, 8), pady=(4, 0))

        self._localized_buttons["buttons.clear_filter"] = ttk.Button(
            filters, text=tr("buttons.clear_filter"), command=self._clear_filter
        )
        self._localized_buttons["buttons.clear_filter"].grid(
            row=2, column=3, sticky="ew", padx=(0, 8), pady=(4, 0)
        )
        ttk.Label(filters, textvariable=self.count_var, style="Accent.TLabel").grid(
            row=2, column=4, sticky="e", pady=(4, 0)
        )
        for idx in range(5):
            filters.columnconfigure(idx, weight=1 if idx in (1, 2) else 0)

        table_panel = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        table_panel.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        table_panel.rowconfigure(1, weight=1)
        table_panel.columnconfigure(0, weight=1)

        self._localized_labels["filters.overview"] = ttk.Label(
            table_panel, text=tr("filters.overview"), style="PanelTitle.TLabel"
        )
        self._localized_labels["filters.overview"].grid(row=0, column=0, sticky="w")

        self.tree = SmoothSheet(
            table_panel,
            headers=self._table_headers(),
            show_row_index=False,
            show_x_scrollbar=True,
            show_y_scrollbar=True,
            default_row_height=28,
            font=("Microsoft YaHei UI", 10, "normal"),
            header_font=("Microsoft YaHei UI", 10, "normal"),
            empty_vertical=0,
            empty_horizontal=0,
            scrollbar_theme_inheritance="clam",
        )
        self.tree.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.tree.bind("<Configure>", self._schedule_table_resize, add="+")
        self.tree.bind("<Map>", self._schedule_initial_table_resize, add="+")
        self.tree.set_column_widths(self.TABLE_MIN_COLUMN_WIDTHS)
        self.tree.set_options(
            table_bg=self.palette["panel"],
            table_fg=self.palette["text"],
            table_grid_fg=self.palette["border"],
            header_bg=self.palette["panel_alt"],
            header_fg=self.palette["muted"],
            header_grid_fg=self.palette["border"],
            table_selected_rows_bg=self.palette["selection"],
            table_selected_rows_fg=self.palette["text"],
            table_selected_rows_border_fg=self.palette["selection"],
            frame_bg=self.palette["panel"],
            vertical_scroll_background=self.palette["panel_soft"],
            vertical_scroll_troughcolor=self.palette["bg"],
            horizontal_scroll_background=self.palette["panel_soft"],
            horizontal_scroll_troughcolor=self.palette["bg"],
        )
        self.tree.enable_bindings("single_select", "arrowkeys")
        self.tree.bind("<<SheetSelect>>", self._on_sheet_select)
        self.tree.bind("<Double-Button-1>", self._focus_value_editor)
        self.tree.enable_smooth_scrolling()

    def _build_right_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        inspector = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        inspector.grid(row=0, column=0, sticky="nsew")
        self._localized_labels["inspector.title"] = ttk.Label(
            inspector, text=tr("inspector.title"), style="PanelTitle.TLabel"
        )
        self._localized_labels["inspector.title"].grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        self._localized_labels["inspector.subtitle"] = ttk.Label(
            inspector,
            text=tr("inspector.subtitle"),
            style="PanelCaption.TLabel",
        )
        self._localized_labels["inspector.subtitle"].grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 12)
        )

        self._add_info_field(inspector, 2, "inspector.key", self.key_var, readonly=True)
        self._add_info_field(
            inspector,
            4,
            "inspector.source",
            self.selected_source_var,
            readonly=True,
        )
        self._add_info_field(
            inspector,
            6,
            "inspector.category",
            self.selected_category_var,
            readonly=True,
        )
        self._add_info_field(
            inspector,
            8,
            "inspector.original_value",
            self.original_value_var,
            readonly=True,
        )
        self._add_info_field(
            inspector,
            10,
            "inspector.value_type",
            self.value_type_var,
            readonly=True,
        )

        self._localized_labels["inspector.new_value"] = ttk.Label(
            inspector, text=tr("inspector.new_value"), style="Muted.TLabel"
        )
        self._localized_labels["inspector.new_value"].grid(
            row=12, column=0, sticky="w", pady=(12, 0)
        )
        self.value_editor_frame = ttk.Frame(inspector, style="Panel.TFrame")
        self.value_editor_frame.grid(
            row=13, column=0, columnspan=2, sticky="ew", pady=(4, 0)
        )
        self.value_editor_frame.columnconfigure(0, weight=1)

        validate_number_cmd = (
            self.root.register(self._validate_numeric_input),
            "%P",
        )
        self.value_entry = ttk.Entry(
            self.value_editor_frame, textvariable=self.value_var
        )
        self.value_entry.grid(row=0, column=0, sticky="ew")
        self.value_entry.bind("<Return>", lambda _e: self.apply_change())

        self.numeric_value_entry = ttk.Entry(
            self.value_editor_frame,
            textvariable=self.value_var,
            validate="key",
            validatecommand=validate_number_cmd,
        )
        self.numeric_value_entry.grid(row=0, column=0, sticky="ew")
        self.numeric_value_entry.bind("<Return>", lambda _e: self.apply_change())

        self.bool_var = tk.StringVar(value="True")
        self.bool_box = ttk.Combobox(
            self.value_editor_frame,
            textvariable=self.bool_var,
            values=["True", "False"],
            state="readonly",
        )
        self.bool_box.grid(row=0, column=0, sticky="ew")
        self.bool_box.bind(
            "<<ComboboxSelected>>",
            lambda _e: self.value_var.set(self.bool_var.get()),
        )
        self._bind_combobox_focus_behavior(self.bool_box)

        self._localized_buttons["buttons.apply_change"] = ttk.Button(
            inspector,
            text=tr("buttons.apply_change"),
            command=self.apply_change,
            style="Primary.TButton",
        )
        self._localized_buttons["buttons.apply_change"].grid(
            row=14, column=0, sticky="ew", pady=(12, 0)
        )
        self._localized_buttons["buttons.restore_value"] = ttk.Button(
            inspector,
            text=tr("buttons.restore_value"),
            command=self._restore_selected_value,
        )
        self._localized_buttons["buttons.restore_value"].grid(
            row=14, column=1, sticky="ew", padx=(8, 0), pady=(12, 0)
        )

        self._localized_labels["inspector.category_note"] = ttk.Label(
            inspector, text=tr("inspector.category_note"), style="Muted.TLabel"
        )
        self._localized_labels["inspector.category_note"].grid(
            row=15, column=0, columnspan=2, sticky="w", pady=(16, 0)
        )
        note = tk.Text(
            inspector, height=5, wrap="word", font=("Microsoft YaHei UI", 10)
        )
        note.grid(row=16, column=0, columnspan=2, sticky="nsew", pady=(4, 0))
        note.insert("1.0", self.category_note_var.get())
        note.configure(state="disabled")
        self.note_text = note

        inspector.rowconfigure(16, weight=1)
        inspector.columnconfigure(0, weight=1)
        inspector.columnconfigure(1, weight=1)
        self._set_editor_mode("text")

    def _schedule_initial_table_resize(self, _event=None) -> None:
        self._schedule_table_resize(force=True)

    def _schedule_table_resize(self, _event=None, *, force: bool = False) -> None:
        if force:
            self._last_table_width = 0
        if self._table_resize_after_id is None:
            self._table_resize_after_id = self.root.after_idle(
                self._resize_table_columns
            )

    def _resize_table_columns(self) -> None:
        self._table_resize_after_id = None
        width = self.tree.winfo_width()
        if width <= 1 or abs(width - self._last_table_width) < 2:
            return
        self._last_table_width = width

        available = max(sum(self.TABLE_MIN_COLUMN_WIDTHS), width - 18)
        extra = available - sum(self.TABLE_MIN_COLUMN_WIDTHS)
        key_extra = round(extra * 0.30)
        value_extra = round(extra * 0.15)
        note_extra = extra - key_extra - value_extra
        widths = [
            self.TABLE_MIN_COLUMN_WIDTHS[0],
            self.TABLE_MIN_COLUMN_WIDTHS[1],
            self.TABLE_MIN_COLUMN_WIDTHS[2] + key_extra,
            self.TABLE_MIN_COLUMN_WIDTHS[3] + value_extra,
            self.TABLE_MIN_COLUMN_WIDTHS[4] + note_extra,
        ]
        self.tree.set_column_widths(widths)
        self.tree.refresh()

    def _init_pane_constraints(
        self, left: ttk.Frame, center: ttk.Frame, right: ttk.Frame
    ) -> None:
        self.left_pane = left
        self.center_pane = center
        self.right_pane = right
        self.content_pane.bind("<Configure>", self._enforce_pane_constraints, add="+")
        self.root.after_idle(self._enforce_pane_constraints)

    def _enforce_pane_constraints(self, _event=None) -> None:
        total_width = self.content_pane.winfo_width()
        if total_width <= 1:
            return

        left = self.LEFT_PANEL_MIN_WIDTH
        right = self.RIGHT_PANEL_MIN_WIDTH
        center = self.CENTER_PANEL_MIN_WIDTH
        required = left + center + right
        if total_width < required:
            center = max(240, total_width - left - right)

        first_sash = left
        second_sash = total_width - right
        min_second_sash = first_sash + center
        if second_sash < min_second_sash:
            second_sash = min_second_sash
        if second_sash > total_width - right:
            second_sash = total_width - right

        try:
            self.content_pane.sashpos(0, first_sash)
            self.content_pane.sashpos(1, second_sash)
        except tk.TclError:
            pass

    def _locale_display_value(self, locale: str) -> str:
        return f"{i18n.locale_display_name(locale)} ({locale})"

    def _on_language_changed(self, _event=None) -> None:
        display = self.locale_display_var.get()
        target_locale = next(
            (
                locale
                for locale in i18n.available_locales()
                if self._locale_display_value(locale) == display
            ),
            i18n.get_locale(),
        )
        if target_locale == i18n.get_locale():
            return
        category_was_all = self.category_var.get().strip() == tr("section.all")
        selected_category_key = None
        if not category_was_all and self.view:
            selected_category = self.category_var.get().strip()
            selected_category_key = next(
                (
                    entry.category_key
                    for entry in self.view.entries
                    if entry.category == selected_category
                ),
                None,
            )
        i18n.set_locale(target_locale)
        self._refresh_localized_ui(
            category_was_all=category_was_all,
            selected_category_key=selected_category_key,
        )

    def _refresh_localized_ui(
        self, category_was_all: bool, selected_category_key: str | None
    ) -> None:
        selected_identity = self._selected_entry_identity()
        selected_section = self.section_reverse_labels.get(
            self.section_var.get(), "all"
        )

        self.section_labels = section_labels()
        self.section_reverse_labels = {
            label: key for key, label in self.section_labels.items()
        }

        self.root.title(tr("app.title"))
        self.header_title_label.configure(text=tr("app.title"))
        self.header_subtitle_label.configure(text=tr("app.header_subtitle"))
        self.locale_display_var.set(self._locale_display_value(i18n.get_locale()))
        self.locale_box.configure(
            values=[
                self._locale_display_value(locale)
                for locale in i18n.available_locales()
            ]
        )

        for key, widget in self._localized_labels.items():
            widget.configure(text=tr(key))

        for key, widget in self._localized_buttons.items():
            widget.configure(text=tr(key))

        for key, widget in self._inspector_labels.items():
            widget.configure(text=tr(key))

        self.search_hint_var.set(tr("filters.hint"))
        self.section_box.configure(values=list(self.section_labels.values()))
        self.section_var.set(
            self.section_labels.get(selected_section, self.section_labels["all"])
        )
        self._populate_location_list()
        self._refresh_category_filter()
        self.category_var.set(
            tr("section.all")
            if category_was_all or not selected_category_key
            else tr(selected_category_key)
        )
        self.tree.headers(self._table_headers())
        if self.view:
            self.render_table()
            if selected_identity:
                self._select_entry_by_identity(*selected_identity)
            self.set_status(tr("message.loaded"))
        elif self._is_loading and self.current_file:
            self.set_status(tr("message.loading"))
        else:
            self.count_var.set(tr("common.items_count", shown=0, total=0))
            self._clear_inspector()
            self.set_status(tr("message.waiting_load"))

    def _add_info_field(
        self,
        parent: ttk.Frame,
        row: int,
        label_key: str,
        variable: tk.StringVar,
        readonly: bool,
    ) -> None:
        label = ttk.Label(parent, text=tr(label_key), style="Muted.TLabel")
        label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._inspector_labels[label_key] = label
        entry = ttk.Entry(
            parent,
            textvariable=variable,
            state="readonly" if readonly else "normal",
            style="Readonly.TEntry" if readonly else "TEntry",
        )
        entry.grid(row=row + 1, column=0, columnspan=2, sticky="ew", pady=(4, 0))

    def _bind_combobox_focus_behavior(self, widget: ttk.Combobox) -> None:
        widget.bind("<ButtonRelease-1>", self._clear_combobox_selection, add="+")
        widget.bind("<FocusIn>", self._clear_combobox_selection, add="+")
        widget.bind("<<ComboboxSelected>>", self._clear_combobox_selection, add="+")

    def _clear_combobox_selection(self, event=None) -> None:
        widget = event.widget if event else None
        if widget is None:
            return
        widget.after_idle(lambda: self._clear_combobox_selection_now(widget))

    def _clear_combobox_selection_now(self, widget: ttk.Combobox) -> None:
        try:
            widget.selection_clear()
            widget.icursor(tk.END)
        except tk.TclError:
            pass

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda _e: self.open_file())
        self.root.bind("<Control-s>", lambda _e: self.save_in_place())
        self.root.bind("<Control-f>", lambda _e: self._focus_search())
        self.root.bind("<F5>", lambda _e: self.reload_current())

    def _focus_search(self) -> None:
        self.search_entry.focus_set()
        self.search_entry.icursor(tk.END)

    def _validate_numeric_input(self, candidate: str) -> bool:
        if candidate == "":
            return True
        if candidate in {"-", "+", ".", "-.", "+."}:
            return True
        try:
            float(candidate)
            return True
        except ValueError:
            lowered = candidate.lower()
            if lowered.endswith(("e", "e-", "e+")):
                prefix = candidate[:-1] if lowered.endswith("e") else candidate[:-2]
                if prefix in {"", "-", "+", ".", "-.", "+."}:
                    return True
                try:
                    float(prefix)
                    return True
                except ValueError:
                    return False
            return False

    def _detect_editor_mode(self, entry: EntryModel) -> str:
        value = entry.display_value.strip()
        if isinstance(entry, MetaVarEntry):
            return "number"
        if value in {"True", "False"}:
            return "bool"
        try:
            float(value)
            return "number"
        except ValueError:
            return "text"

    def _set_editor_mode(self, mode: str) -> None:
        self.editor_mode = mode
        self.value_entry.grid_remove()
        self.numeric_value_entry.grid_remove()
        self.bool_box.grid_remove()

        if mode == "bool":
            self.value_type_var.set(tr("inspector.value_type_boolean"))
            self.bool_box.grid()
            self.bool_var.set(
                self.value_var.get()
                if self.value_var.get() in {"True", "False"}
                else "True"
            )
        elif mode == "number":
            self.value_type_var.set(tr("inspector.value_type_number"))
            self.numeric_value_entry.grid()
        else:
            self.value_type_var.set(tr("inspector.value_type_text"))
            self.value_entry.grid()

    def _active_value_widget(self):
        if self.editor_mode == "bool":
            return self.bool_box
        if self.editor_mode == "number":
            return self.numeric_value_entry
        return self.value_entry

    def _current_editor_value(self) -> str:
        if self.editor_mode == "bool":
            return self.bool_var.get().strip()
        return self.value_var.get().strip()

    def _sync_editor_value(self, value: str) -> None:
        self.value_var.set(value)
        if value in {"True", "False"}:
            self.bool_var.set(value)

    def _populate_location_list(self) -> None:
        previous = self.location_list.curselection()
        previous_index = previous[0] if previous else 0
        self.location_list.delete(0, tk.END)
        for location in self.default_locations:
            state = (
                tr("common.ready") if location.path.exists() else tr("common.missing")
            )
            self.location_list.insert(
                tk.END, f"[{state}] {location.label}\n{location.path}"
            )
        if self.default_locations:
            self.location_list.selection_clear(0, tk.END)
            self.location_list.selection_set(
                min(previous_index, len(self.default_locations) - 1)
            )

    def _selected_location(self) -> SaveLocation | None:
        selected = self.location_list.curselection()
        if not selected:
            return None
        index = selected[0]
        if 0 <= index < len(self.default_locations):
            return self.default_locations[index]
        return None

    def _reveal_in_file_manager(self, path: Path) -> None:
        path = path.resolve()

        if sys.platform == "win32":
            if path.exists():
                subprocess.run(
                    ["explorer", "/select,", str(path)],
                    check=False,
                )
            else:
                subprocess.run(
                    ["explorer", str(path.parent if path.suffix else path)],
                    check=False,
                )
            return

        if sys.platform == "darwin":
            if path.exists():
                subprocess.run(["open", "-R", str(path)], check=False)
            else:
                subprocess.run(["open", str(path.parent)], check=False)
            return

        target = path.parent if path.exists() or path.suffix else path
        subprocess.run(["xdg-open", str(target)], check=False)

    def _reveal_selected_location(self) -> None:
        location = self._selected_location()
        if not location:
            return

        try:
            self._reveal_in_file_manager(location.path)
        except Exception as ex:
            messagebox.showerror(tr("dialog.open_failed_title"), str(ex))

    def _open_selected_location(self, _event=None) -> None:
        location = self._selected_location()
        if not location:
            return

        if not location.path.is_file():
            messagebox.showwarning(
                tr("dialog.file_not_found_title"),
                str(location.path),
            )
            return

        self.load_file(location.path)

    def set_status(self, msg: str) -> None:
        self.path_var.set(
            str(self.current_file) if self.current_file else tr("common.empty_file")
        )
        self.status_var.set(msg)

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title=tr("dialog.select_save"),
            filetypes=[
                (tr("dialog.cts_save"), "*.gd"),
                (tr("dialog.all_files"), "*.*"),
            ],
        )
        if path:
            self.load_file(Path(path))

    def load_file(self, path: Path) -> None:
        self._load_ticket += 1
        ticket = self._load_ticket
        self.current_file = path
        self.editor = None
        self.view = None
        self.dirty = False
        self._is_loading = True
        self._refresh_category_filter()
        self.render_table()
        self.set_status(tr("message.loading"))
        self.root.update_idletasks()

        threading.Thread(
            target=self._load_file_worker,
            args=(path, ticket),
            daemon=True,
        ).start()

    def _load_file_worker(self, path: Path, ticket: int) -> None:
        try:
            editor = SaveBinaryEditor.from_file(path)
            view = editor.parse()
        except Exception as ex:
            self.root.after(0, lambda err=ex: self._finish_load_error(ticket, err))
            return

        self.root.after(
            0,
            lambda: self._finish_load_success(
                ticket=ticket, path=path, editor=editor, view=view
            ),
        )

    def _finish_load_success(
        self, ticket: int, path: Path, editor: SaveBinaryEditor, view: SaveView
    ) -> None:
        if ticket != self._load_ticket:
            return
        self.editor = editor
        self.view = view
        self.current_file = path
        self.dirty = False
        self._is_loading = False
        self._refresh_category_filter()
        self.render_table()
        self.set_status(tr("message.loaded"))

    def _finish_load_error(self, ticket: int, error: Exception) -> None:
        if ticket != self._load_ticket:
            return
        self.editor = None
        self.view = None
        self.dirty = False
        self._is_loading = False
        self._refresh_category_filter()
        self.render_table()
        self.set_status(tr("message.load_failed"))
        messagebox.showerror(tr("dialog.load_failed_title"), str(error))

    def check_for_updates_on_startup(self) -> None:
        threading.Thread(target=self._check_for_updates_worker, daemon=True).start()

    def _check_for_updates_worker(self) -> None:
        try:
            update = check_for_update()
        except Exception:
            return
        if update:
            self.root.after(0, lambda: self._show_update_dialog(update))

    def _show_update_dialog(self, update: UpdateInfo) -> None:
        if self._update_dialog_open:
            return
        self._update_dialog_open = True

        dialog = tk.Toplevel(self.root)
        dialog.title(tr("update.title"))
        dialog.transient(self.root)
        dialog.resizable(True, True)
        dialog.minsize(460, 320)

        def close_dialog() -> None:
            self._update_dialog_open = False
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", close_dialog)

        body = ttk.Frame(dialog, style="App.TFrame", padding=16)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)

        title = update.title or tr("update.available", version=update.version)
        ttk.Label(body, text=title, style="Header.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            body,
            text=tr("update.current_new", version=update.version),
            style="SubHeader.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 12))

        notes_frame = ttk.Frame(body, style="Panel.TFrame", padding=8)
        notes_frame.grid(row=2, column=0, sticky="nsew")
        notes_frame.rowconfigure(0, weight=1)
        notes_frame.columnconfigure(0, weight=1)

        notes = tk.Text(notes_frame, wrap=tk.WORD, height=10)
        notes.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(notes_frame, orient=tk.VERTICAL, command=notes.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        notes.configure(yscrollcommand=scroll.set)
        notes.insert("1.0", update.changelog or tr("update.no_changelog"))
        notes.configure(state=tk.DISABLED)

        buttons = ttk.Frame(body, style="App.TFrame")
        buttons.grid(row=3, column=0, sticky="e", pady=(14, 0))

        def open_download() -> None:
            webbrowser.open(update.download_url)
            close_dialog()

        ttk.Button(
            buttons,
            text=tr("update.later"),
            command=close_dialog,
        ).pack(side=tk.RIGHT)
        ttk.Button(
            buttons,
            text=tr("update.download"),
            style="Primary.TButton",
            command=open_download,
        ).pack(side=tk.RIGHT, padx=(0, 8))

    def autoload_default_save(self) -> None:
        if sys.platform != "win32":
            return
        for location in self.default_locations:
            if location.path.exists():
                self.load_file(location.path)
                break

    def _clear_filter(self) -> None:
        self._suspend_render = True
        try:
            self.filter_var.set("")
            self.section_var.set(self.section_labels["all"])
            self.category_var.set(tr("section.all"))
        finally:
            self._suspend_render = False
        self.render_table()

    def _request_render(self) -> None:
        if not self._suspend_render:
            self.render_table()

    def _focus_value_editor(self, _event=None) -> None:
        widget = self._active_value_widget()
        widget.focus_set()
        if hasattr(widget, "icursor"):
            widget.icursor(tk.END)

    def reload_current(self) -> None:
        if self.current_file:
            self.load_file(self.current_file)

    def render_table(self) -> None:
        self.tree.stop_smooth_scrolling()
        previous_identity = self._selected_entry_identity()
        self.item_map.clear()

        if not self.view:
            self.tree.set_sheet_data([], reset_col_positions=False)
            self._schedule_table_resize(force=True)
            self.count_var.set(tr("common.items_count", shown=0, total=0))
            self._update_dashboard(visible=0)
            self._clear_inspector()
            return

        data: list[list[str]] = []
        matched_row: int | None = None
        for row in self._table_rows():
            if not self._row_matches_filters(row):
                continue
            entry = row.entry
            row_index = len(data)
            data.append(
                [
                    self.section_labels.get(row.section, row.section),
                    entry.category,
                    entry.key,
                    entry.display_value,
                    entry.note,
                ]
            )
            self.item_map[str(row_index)] = entry
            if (
                previous_identity == (row.section, row.entry.key)
                and matched_row is None
            ):
                matched_row = row_index

        self.tree.set_sheet_data(
            data,
            reset_col_positions=False,
            reset_row_positions=True,
        )
        self._schedule_table_resize(force=True)

        shown = len(data)
        total = len(self.view.entries)
        self.count_var.set(tr("common.items_count", shown=shown, total=total))
        self._update_dashboard(visible=shown)

        if matched_row is not None:
            self._select_table_row(matched_row)
        elif shown:
            self._select_table_row(0)
        else:
            self._clear_inspector()

        self.on_select()
        self.set_status(
            tr("message.rendered") if self.current_file else tr("message.waiting_load")
        )

    def _update_dashboard(self, visible: int | None = None) -> None:
        if not self.view:
            items = custom = meta = 0
        else:
            custom = len(self.view.custom_vars)
            meta = len(self.view.meta_vars)
            items = custom + meta

        self.stat_vars["items"].set(str(items))
        self.stat_vars["custom"].set(str(custom))
        self.stat_vars["meta"].set(str(meta))
        self.stat_vars["visible"].set(str(visible if visible is not None else items))

    def _table_rows(self) -> list[TableRow]:
        if not self.view:
            return []
        return list(
            chain.from_iterable(
                (TableRow(section, entry) for entry in entries)
                for section, entries in (
                    ("custom", self.view.custom_vars),
                    ("meta", self.view.meta_vars),
                )
            )
        )

    def _table_headers(self) -> list[str]:
        return [
            tr("filters.column_source"),
            tr("filters.column_category"),
            tr("filters.column_key"),
            tr("filters.column_value"),
            tr("filters.column_note"),
        ]

    def _row_matches_filters(self, row: TableRow) -> bool:
        section_filter = self.section_var.get().strip()
        section_key = self.section_reverse_labels.get(section_filter, "all")
        if section_key not in ("all", row.section):
            return False

        category_filter = self.category_var.get().strip()
        if (
            category_filter not in ("", tr("section.all"))
            and row.entry.category != category_filter
        ):
            return False

        q = self.filter_var.get().strip().casefold()
        if not q:
            return True
        searchable = "\n".join(
            [
                row.section,
                row.entry.category,
                row.entry.key,
                row.entry.display_value,
                row.entry.note,
            ]
        ).casefold()
        return q in searchable

    def _refresh_category_filter(self) -> None:
        if not self.view:
            self.category_box.configure(values=[tr("section.all")])
            self.category_var.set(tr("section.all"))
            return
        categories = sorted({entry.category for entry in self.view.entries})
        values = [tr("section.all"), *categories]
        self.category_box.configure(values=values)
        if self.category_var.get() not in values:
            self.category_var.set(tr("section.all"))

    def on_select(self, _event=None) -> None:
        entry = self._selected_entry()
        if not entry:
            self._clear_inspector()
            return
        self.key_var.set(entry.key)
        self.original_value_var.set(entry.display_value)
        self._sync_editor_value(entry.display_value)
        self._set_editor_mode(self._detect_editor_mode(entry))
        self.selected_source_var.set(
            self.section_labels["custom"]
            if isinstance(entry, CustomVarEntry)
            else self.section_labels["meta"]
        )
        self.selected_category_var.set(entry.category)
        self.category_note_var.set(entry.note or tr("common.no_category_note_short"))
        self._set_note_text(self.category_note_var.get())

    def _on_sheet_select(self, _event=None) -> None:
        selected = self.tree.get_currently_selected()
        if not selected:
            self._clear_inspector()
            return
        if selected.type_ != "rows":
            self.tree.select_row(selected.row, run_binding_func=False)
        self.on_select()

    def _select_table_row(self, row: int) -> None:
        self.tree.select_row(row, run_binding_func=False)
        self.tree.see(row, 0)

    def _set_note_text(self, text: str) -> None:
        self.note_text.configure(state="normal")
        self.note_text.delete("1.0", tk.END)
        self.note_text.insert("1.0", text)
        self.note_text.configure(state="disabled")

    def _clear_inspector(self) -> None:
        self.key_var.set(tr("common.unselected"))
        self.value_var.set("")
        self.bool_var.set("True")
        self.original_value_var.set(tr("common.dash"))
        self.value_type_var.set(tr("inspector.value_type_text"))
        self.selected_source_var.set(tr("common.dash"))
        self.selected_category_var.set(tr("common.dash"))
        self.category_note_var.set(tr("common.no_category_note"))
        self._set_note_text(self.category_note_var.get())
        self._set_editor_mode("text")

    def _restore_selected_value(self) -> None:
        entry = self._selected_entry()
        if entry:
            self._sync_editor_value(entry.display_value)
            self._set_editor_mode(self._detect_editor_mode(entry))

    def apply_change(self) -> None:
        entry = self._selected_entry()
        if not entry:
            messagebox.showinfo(tr("dialog.hint_title"), tr("message.select_row_first"))
            return
        if not self.editor:
            return

        new_value = self._current_editor_value()
        if new_value == "":
            messagebox.showwarning(
                tr("dialog.invalid_value_title"), tr("message.value_required")
            )
            return
        if self.editor_mode == "number":
            try:
                float(new_value)
            except ValueError:
                messagebox.showwarning(
                    tr("dialog.invalid_value_title"), tr("message.number_required")
                )
                return

        try:
            if isinstance(entry, CustomVarEntry):
                self.editor.set_custom_entry(entry, new_value)
            else:
                self.editor.set_meta_entry(entry, new_value)
            self.view = self.editor.parse()
            self.dirty = True
            self._refresh_category_filter()
            self.render_table()
            self.set_status(tr("message.change_applied"))
        except Exception as ex:
            messagebox.showerror(tr("dialog.change_failed_title"), str(ex))

    def _selected_entry(self) -> EntryModel | None:
        selected = self.tree.get_currently_selected()
        if not selected:
            return None
        return self.item_map.get(str(selected.row))

    def _selected_entry_identity(self) -> tuple[str, str] | None:
        entry = self._selected_entry()
        if not entry:
            return None
        section = "custom" if isinstance(entry, CustomVarEntry) else "meta"
        return section, entry.key

    def _select_entry_by_identity(self, section: str, key: str) -> None:
        for row, entry in self.item_map.items():
            entry_section = "custom" if isinstance(entry, CustomVarEntry) else "meta"
            if entry.key != key or entry_section != section:
                continue
            self._select_table_row(int(row))
            self.on_select()
            return

    def save_in_place(self) -> None:
        if not self.editor or not self.current_file:
            return
        try:
            targets = self.editor.save_effective(self.current_file)
            self.dirty = False
            if len(targets) > 1:
                self.set_status(
                    tr("message.saved")
                    + f" ({', '.join(path.name for path in targets)})"
                )
            else:
                self.set_status(tr("message.saved"))
        except Exception as ex:
            messagebox.showerror(tr("dialog.save_failed_title"), str(ex))

    def save_as(self) -> None:
        if not self.editor:
            return
        path = filedialog.asksaveasfilename(
            title=tr("dialog.save_as"),
            defaultextension=".gd",
            filetypes=[
                (tr("dialog.cts_save"), "*.gd"),
                (tr("dialog.all_files"), "*.*"),
            ],
        )
        if not path:
            return

        out = Path(path)
        try:
            targets = self.editor.save_effective(out)
            self.current_file = out
            self.dirty = False
            if len(targets) > 1:
                self.set_status(
                    tr("message.saved_as")
                    + f" ({', '.join(path.name for path in targets)})"
                )
            else:
                self.set_status(tr("message.saved_as"))
        except Exception as ex:
            messagebox.showerror(tr("dialog.save_failed_title"), str(ex))

    def make_backup(self) -> None:
        if not self.current_file:
            return
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            bak = self.current_file.with_suffix(
                self.current_file.suffix + f".{stamp}.bak"
            )
            shutil.copy2(self.current_file, bak)
            messagebox.showinfo(tr("dialog.backup_done_title"), str(bak))
        except Exception as ex:
            messagebox.showerror(tr("dialog.backup_failed_title"), str(ex))


def main() -> None:
    set_windows_app_user_model_id()
    root = DPIAwareTk()
    app = SaveEditorApp(root)
    root.after_idle(app.autoload_default_save)
    root.mainloop()
