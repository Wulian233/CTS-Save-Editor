from dataclasses import dataclass

from ..i18n import i18n


@dataclass(slots=True, frozen=True)
class VarCategory:
    name: str
    note: str = ""
    description: str = ""


_EXACT_KEY_CATEGORIES = dict(
    {
        "statTotal": VarCategory(
            "category.stats_progress", "category_note.stats_progress"
        ),
        "statTotalIdeas": VarCategory(
            "category.stats_progress", "category_note.stats_progress"
        ),
        "primary_lock_level": VarCategory(
            "category.stats_progress", "category_note.stats_progress"
        ),
        "stat_doober": VarCategory(
            "category.currency_resource", "category_note.currency_resource"
        ),
        "idle_darwin": VarCategory(
            "category.currency_resource", "category_note.currency_resource"
        ),
        "kGuid": VarCategory(
            "category.account_settings", "category_note.account_settings"
        ),
        "LastReward": VarCategory(
            "category.account_settings", "category_note.account_settings"
        ),
        "w_primary_sim": VarCategory(
            "category.account_settings", "category_note.account_settings"
        ),
    }
)

_PREFIX_CATEGORIES = dict(
    {
        ("achievement_", "achivement_", "ach_", "ac_", "ab_"): VarCategory(
            "category.achievement", "category_note.achievement_source"
        ),
        ("stat_",): VarCategory(
            "category.stats_progress", "category_note.stats_progress"
        ),
        ("bank", "beyond_bank"): VarCategory(
            "category.currency_resource", "category_note.bank_pool"
        ),
        ("sim_score", "gs_"): VarCategory(
            "category.stats_progress", "category_note.sim_score"
        ),
        ("effect_",): VarCategory(
            "category.effect_bonus", "category_note.effect_bonus"
        ),
        ("prestige", "rebirth_", "re_"): VarCategory(
            "category.prestige", "category_note.prestige"
        ),
        ("item_", "tech_", "m_", "i_", "t_", "man_", "znew_", "glitch_"): VarCategory(
            "category.primary_sim", "category_note.primary_sim"
        ),
        ("d_",): VarCategory("category.dinosaur_sim", "category_note.dinosaur_sim"),
        ("s_", "beyond_", "constellation_"): VarCategory(
            "category.universe_sim", "category_note.universe_sim"
        ),
        (
            "lte",
            "event_",
            "lastEvent",
            "lastRedeemed",
            "EggDateEvent",
            "minBoostEvent",
        ): VarCategory("category.event", "category_note.event"),
        ("store_", "premium", "iap_", "pricing", "bundle_"): VarCategory(
            "category.shop_paid", "category_note.shop_paid"
        ),
        ("glass_",): VarCategory(
            "category.appearance_collection", "category_note.appearance_collection"
        ),
        ("a_", "automation", "nanobot"): VarCategory(
            "category.automation", "category_note.automation"
        ),
    }
)

_SUBSTRING_CATEGORIES = dict(
    {
        ("date", "time", "boost"): VarCategory(
            "category.time_boost", "category_note.time_boost"
        ),
        ("tutorial", "tut_", "ftue", "first"): VarCategory(
            "category.tutorial", "category_note.tutorial"
        ),
        ("save", "version", "migrate", "rebootconv", "patch"): VarCategory(
            "category.save_migration", "category_note.save_migration"
        ),
    }
)


def classify_var_key(key: str, section: str) -> VarCategory:
    lowered = key.casefold()
    if category := _EXACT_KEY_CATEGORIES.get(key):
        return _localize_category(_with_description(key, category))
    for prefixes, category in _PREFIX_CATEGORIES.items():
        if key.startswith(prefixes):
            return _localize_category(_with_description(key, category))
    for tokens, category in _SUBSTRING_CATEGORIES.items():
        if any(token in lowered for token in tokens):
            return _localize_category(_with_description(key, category))
    if section == "meta":
        return _localize_category(
            _with_description(
                key,
                VarCategory(
                    "category.numeric_item", "category_note.numeric_item_source"
                ),
            )
        )
    return _localize_category(
        _with_description(
            key,
            VarCategory("category.custom_var", "category_note.custom_var_string"),
        )
    )


def _localize_category(category: VarCategory) -> VarCategory:
    return category


def _with_description(key: str, category: VarCategory) -> VarCategory:
    description = _description_key_for(key) or category.description
    return VarCategory(category.name, category.note, description)


def _description_key_for(key: str) -> str:
    description_key = f"item_note.{key}"
    return description_key if i18n.has_translation(description_key) else ""
