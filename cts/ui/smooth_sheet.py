import sys
import tkinter as tk
from typing import Any

from tksheet import Sheet


class SmoothSheet(Sheet):
    """A tksheet table with pixel scrolling and short wheel easing."""

    FRAME_MS = 16
    WHEEL_PIXELS = 84
    TOUCHPAD_SCALE = 1.0
    FOLLOW_FACTOR = 0.45

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._scroll_after_id: str | None = None
        self._scroll_target = 0.0

    def enable_smooth_scrolling(self) -> None:
        for canvas in (self.MT, self.CH, self.RI):
            canvas.bind("<MouseWheel>", self._on_mousewheel)
            canvas.bind("<Button-4>", self._on_mousewheel)
            canvas.bind("<Button-5>", self._on_mousewheel)
        self.bind("<Destroy>", self._on_destroy, add="+")

    def stop_smooth_scrolling(self) -> None:
        self._cancel_animation()
        self._scroll_target = self._current_pixel()

    def _on_mousewheel(self, event: tk.Event) -> str:
        button = getattr(event, "num", None)
        if button in (4, 5):
            self._queue_pixels(-self.WHEEL_PIXELS if button == 4 else self.WHEEL_PIXELS)
            return "break"

        delta = int(getattr(event, "delta", 0))
        if not delta:
            return "break"

        if sys.platform == "darwin" or abs(delta) < 120:
            self._queue_pixels(-delta * self.TOUCHPAD_SCALE)
        else:
            self._queue_pixels(-delta / 120 * self.WHEEL_PIXELS)
        return "break"

    def _queue_pixels(self, offset: float) -> None:
        if self._scroll_after_id is None:
            self._scroll_target = self._current_pixel()
        self._scroll_target = self._clamp_pixel(self._scroll_target + offset)
        if self._scroll_after_id is None:
            self._scroll_after_id = self.after_idle(self._animation_frame)

    def _animation_frame(self) -> None:
        self._scroll_after_id = None
        current = self._current_pixel()
        remaining = self._scroll_target - current
        # Tk Canvas positions are integer pixels; snap the final pixel so the
        # animation cannot stall one pixel away from its target.
        if abs(remaining) <= 1.0:
            self._move_to_pixel(self._scroll_target)
            return

        self._move_to_pixel(current + remaining * self.FOLLOW_FACTOR)
        self._scroll_after_id = self.after(self.FRAME_MS, self._animation_frame)

    def _move_to_pixel(self, position: float) -> None:
        total = self._content_height()
        if total <= 0:
            return
        self.MT.yview_moveto(self._clamp_pixel(position) / total)
        self.MT.main_table_redraw_grid_and_text(
            redraw_header=False,
            redraw_row_index=False,
        )

    def _current_pixel(self) -> float:
        return float(self.MT.canvasy(0))

    def _content_height(self) -> float:
        return float(self.MT.row_positions[-1]) if self.MT.row_positions else 0.0

    def _clamp_pixel(self, position: float) -> float:
        maximum = max(0.0, self._content_height() - self.MT.winfo_height())
        return min(maximum, max(0.0, position))

    def _cancel_animation(self) -> None:
        if self._scroll_after_id is None:
            return
        try:
            self.after_cancel(self._scroll_after_id)
        except tk.TclError:
            pass
        self._scroll_after_id = None

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is self:
            self._cancel_animation()
