import struct
from pathlib import Path

from .binary import (
    encode_7bit_int,
    extract_custom_vars,
    extract_meta_vars,
    scan_string_records,
)
from .categories import classify_var_key
from .models import CustomVarEntry, MetaVarEntry, SaveView
from .numbers import normalize_to_owned_exp


class SaveBinaryEditor:
    def __init__(self, data: bytes):
        self._data = data

    @classmethod
    def from_file(cls, path: Path) -> "SaveBinaryEditor":
        return cls(path.read_bytes())

    @property
    def data(self) -> bytes:
        return self._data

    def save_effective(self, path: Path) -> list[Path]:
        targets = get_effective_save_targets(path)
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self._data)
        return targets

    def parse(self) -> SaveView:
        records = scan_string_records(self._data)
        parsed_view = SaveView(
            custom_vars=extract_custom_vars(records),
            meta_vars=extract_meta_vars(self._data, records),
        )
        categorize_view(parsed_view)
        return parsed_view

    def set_custom_var(self, key: str, value: str) -> None:
        entry = find_entry(self.parse().custom_vars, key, "custom var")
        self.set_custom_entry(entry, value)

    def set_custom_entry(self, entry: CustomVarEntry, value: str) -> None:
        new_raw = value.encode("utf-8")
        new_len = encode_7bit_int(len(new_raw))
        old_len_total = entry.value_len_size + (entry.value_end - entry.value_start)
        old_chunk_start = entry.value_len_pos
        old_chunk_end = entry.value_len_pos + old_len_total
        self._replace_chunk(old_chunk_start, old_chunk_end, new_len + new_raw)

    def set_meta_var(self, key: str, value: str) -> None:
        entry = find_entry(self.parse().meta_vars, key, "meta var")
        self.set_meta_entry(entry, value)

    def set_meta_entry(self, entry: MetaVarEntry, value: str) -> None:
        new_owned, new_exp = normalize_to_owned_exp(value)
        out = bytearray(self._data)
        struct.pack_into("<d", out, entry.object_record_pos + 9, new_owned)
        struct.pack_into("<q", out, entry.object_record_pos + 17, int(new_exp))
        self._data = bytes(out)

    def _replace_chunk(self, start: int, end: int, payload: bytes) -> None:
        self._data = self._data[:start] + payload + self._data[end:]


def categorize_view(view: SaveView) -> None:
    for section, entries in (("custom", view.custom_vars), ("meta", view.meta_vars)):
        for entry in entries:
            category = classify_var_key(entry.key, section)
            entry.category_key = category.name
            entry.category_note_key = category.note
            entry.description_key = category.description


def find_entry[T: CustomVarEntry | MetaVarEntry](
    entries: list[T], key: str, label: str
) -> T:
    entry = next((item for item in entries if item.key == key), None)
    if entry is None:
        raise KeyError(f"{label} not found: {key}")
    return entry


def get_effective_save_targets(path: Path) -> list[Path]:
    resolved = path.expanduser()
    name = resolved.name.lower()
    if name not in {"savedgames.gd", "savedgames2.gd"}:
        return [resolved]

    parent = resolved.parent
    primary = parent / "savedGames.gd"
    secondary = parent / "savedGames2.gd"
    return [primary, secondary]
