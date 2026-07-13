import tkinter as tk
from tkinter import ttk
from typing import Any, cast

PALETTE = {
    "bg": "#16181c",
    "panel": "#1d2127",
    "panel_alt": "#252a31",
    "panel_soft": "#2d333c",
    "border": "#3c4654",
    "text": "#eef3f8",
    "muted": "#94a3b8",
    "accent": "#59d185",
    "accent_soft": "#243c2d",
    "selection": "#1c6dd0",
    "selection_soft": "#173554",
}

DEFAULT_FONT = ("Microsoft YaHei UI", 10)
HEADER_FONT = ("Segoe UI Semibold", 10)


def configure_theme(root: tk.Tk) -> dict[str, str]:
    palette = dict(PALETTE)
    root.configure(bg=palette["bg"])

    style = ttk.Style(root)
    _use_clam_theme(style)
    style.configure(".", font=DEFAULT_FONT)

    _configure_styles(style, palette)
    _configure_maps(style, palette)
    _configure_widget_options(root, palette)
    return palette


def _use_clam_theme(style: ttk.Style) -> None:
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass


def _configure_styles(style: ttk.Style, palette: dict[str, str]) -> None:
    bordered_panel = {
        "borderwidth": 1,
        "relief": "solid",
        "bordercolor": palette["border"],
    }
    text_on_panel = {
        "background": palette["panel"],
        "foreground": palette["text"],
    }
    muted_on_panel = {
        "background": palette["panel"],
        "foreground": palette["muted"],
    }

    styles = {
        "App.TFrame": {
            "background": palette["bg"],
            "borderwidth": 0,
        },
        "Panel.TFrame": {
            "background": palette["panel"],
            **bordered_panel,
        },
        "PanelAlt.TFrame": {
            "background": palette["panel_alt"],
            **bordered_panel,
        },
        "Header.TLabel": {
            "background": palette["bg"],
            "foreground": palette["text"],
            "font": ("Segoe UI Semibold", 13),
        },
        "SubHeader.TLabel": {
            "background": palette["bg"],
            "foreground": palette["muted"],
            "font": ("Segoe UI", 10),
        },
        "PanelTitle.TLabel": {
            **text_on_panel,
            "font": ("Segoe UI Semibold", 11),
        },
        "PanelCaption.TLabel": {
            **muted_on_panel,
            "font": ("Segoe UI", 9),
        },
        "StatValue.TLabel": {
            "background": palette["panel_alt"],
            "foreground": palette["text"],
            "font": ("Segoe UI Semibold", 16),
        },
        "StatLabel.TLabel": {
            "background": palette["panel_alt"],
            "foreground": palette["muted"],
            "font": ("Segoe UI", 9),
        },
        "Data.TLabel": text_on_panel,
        "Muted.TLabel": muted_on_panel,
        "Accent.TLabel": {
            "background": palette["panel"],
            "foreground": palette["accent"],
            "font": HEADER_FONT,
        },
        "TButton": {
            "background": palette["panel_soft"],
            "foreground": palette["text"],
            "borderwidth": 1,
            "relief": "flat",
            "focusthickness": 0,
            "padding": (10, 7),
        },
        "Primary.TButton": {
            "background": palette["accent_soft"],
            "foreground": palette["accent"],
            "bordercolor": palette["accent"],
            "font": HEADER_FONT,
            "padding": (12, 8),
        },
        "TEntry": {
            "fieldbackground": palette["panel_soft"],
            "background": palette["panel_soft"],
            "foreground": palette["text"],
            "insertcolor": palette["text"],
            "bordercolor": palette["border"],
            "lightcolor": palette["border"],
            "darkcolor": palette["border"],
            "padding": 6,
        },
        "Readonly.TEntry": {
            "fieldbackground": palette["panel_alt"],
            "foreground": palette["text"],
        },
        "TCombobox": {
            "fieldbackground": palette["panel_soft"],
            "background": palette["panel_soft"],
            "foreground": palette["text"],
            "arrowcolor": palette["text"],
            "bordercolor": palette["border"],
            "lightcolor": palette["border"],
            "darkcolor": palette["border"],
            "padding": 5,
        },
        "Treeview": {
            "background": palette["panel"],
            "fieldbackground": palette["panel"],
            "foreground": palette["text"],
            "bordercolor": palette["border"],
            "rowheight": 28,
            "font": DEFAULT_FONT,
        },
        "Treeview.Heading": {
            "background": palette["panel_alt"],
            "foreground": palette["muted"],
            "bordercolor": palette["border"],
            "relief": "flat",
            "font": HEADER_FONT,
            "padding": (8, 7),
        },
        "Vertical.TScrollbar": {
            "background": palette["panel_soft"],
            "troughcolor": palette["bg"],
            "bordercolor": palette["bg"],
            "arrowcolor": palette["muted"],
        },
    }

    for name, options in styles.items():
        style.configure(name, **options)


def _configure_maps(style: ttk.Style, palette: dict[str, str]) -> None:
    style_maps = {
        "TButton": {
            "background": [
                ("active", palette["selection"]),
                ("pressed", palette["selection_soft"]),
            ],
            "foreground": [("disabled", palette["muted"])],
            "bordercolor": [("active", palette["selection"])],
        },
        "Primary.TButton": {
            "background": [("active", "#2d4f39"), ("pressed", "#1f3828")],
        },
        "TCombobox": {
            "fieldbackground": [("readonly", palette["panel_soft"])],
            "selectbackground": [("readonly", palette["selection"])],
            "selectforeground": [("readonly", palette["text"])],
        },
        "Treeview": {
            "background": [("selected", palette["selection"])],
            "foreground": [("selected", palette["text"])],
        },
        "Treeview.Heading": {
            "background": [("active", palette["panel_soft"])],
        },
    }

    for name, options in style_maps.items():
        _apply_style_map(style, name, options)


def _apply_style_map(
    style: ttk.Style,
    style_name: str,
    options: dict[str, list[tuple[str, str]]],
) -> None:
    # tkinter stubs do not model ttk.Style.map's dynamic keyword options well.
    style.map(style_name, **cast(Any, options))


def _configure_widget_options(root: tk.Tk, palette: dict[str, str]) -> None:
    option_map = {
        "*TCombobox*Listbox.background": palette["panel"],
        "*TCombobox*Listbox.foreground": palette["text"],
        "*TCombobox*Listbox.selectBackground": palette["selection"],
        "*TCombobox*Listbox.selectForeground": palette["text"],
        "*Listbox.background": palette["panel_alt"],
        "*Listbox.foreground": palette["text"],
        "*Listbox.selectBackground": palette["selection"],
        "*Listbox.selectForeground": palette["text"],
        "*Listbox.highlightThickness": 0,
        "*Listbox.borderWidth": 0,
        "*Text.background": palette["panel_soft"],
        "*Text.foreground": palette["text"],
        "*Text.insertBackground": palette["text"],
        "*Text.highlightThickness": 0,
        "*Text.relief": "flat",
    }

    for pattern, value in option_map.items():
        root.option_add(pattern, value)
