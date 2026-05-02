from dataclasses import dataclass

from ..save.logic import CustomVarEntry, MetaVarEntry
from ..i18n import tr

type EntryModel = CustomVarEntry | MetaVarEntry


def section_labels() -> dict[str, str]:
    return {
        "all": tr("section.all"),
        "custom": tr("section.customVars"),
        "meta": tr("section.metaVars"),
    }


@dataclass(slots=True, frozen=True)
class TableRow:
    iid: str
    section: str
    entry: EntryModel


@dataclass(slots=True, frozen=True)
class DashboardStat:
    label: str
    value: str
