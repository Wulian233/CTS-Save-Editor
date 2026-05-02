from dataclasses import dataclass
from itertools import chain

from ..i18n import tr
from .numbers import owned_exp_to_decimal


@dataclass(slots=True)
class CustomVarEntry:
    key: str
    value: str
    value_len_pos: int
    value_len_size: int
    value_start: int
    value_end: int
    category_key: str = "category.unclassified"
    category_note_key: str = ""
    description_key: str = ""

    @property
    def display_value(self) -> str:
        return self.value

    @property
    def category(self) -> str:
        return tr(self.category_key)

    @property
    def category_note(self) -> str:
        return tr(self.category_note_key) if self.category_note_key else ""

    @property
    def note(self) -> str:
        if self.description_key:
            return tr(self.description_key)
        return self.category_note


@dataclass(slots=True)
class MetaVarEntry:
    key: str
    object_id: int
    owned: float
    exponent: int
    object_record_pos: int
    category_key: str = "category.unclassified"
    category_note_key: str = ""
    description_key: str = ""

    @property
    def display_value(self) -> str:
        return owned_exp_to_decimal(self.owned, self.exponent)

    @property
    def category(self) -> str:
        return tr(self.category_key)

    @property
    def category_note(self) -> str:
        return tr(self.category_note_key) if self.category_note_key else ""

    @property
    def note(self) -> str:
        if self.description_key:
            return tr(self.description_key)
        return self.category_note


@dataclass(slots=True)
class SaveView:
    custom_vars: list[CustomVarEntry]
    meta_vars: list[MetaVarEntry]

    @property
    def entries(self) -> list[CustomVarEntry | MetaVarEntry]:
        return list(chain(self.custom_vars, self.meta_vars))


@dataclass(slots=True, frozen=True)
class StringRecord:
    pos: int
    end: int
    object_id: int
    text: str
    len_pos: int
    len_size: int
    value_start: int
    value_end: int
