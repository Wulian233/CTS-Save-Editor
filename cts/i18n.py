import locale
from pathlib import Path

import json


class I18nManager:
    def __init__(self) -> None:
        self._locale_dir = Path(__file__).resolve().parent / "locales"
        self._fallback_locale = "en-US"
        self._default_locale = self._detect_default_locale()
        self._current_locale = self._default_locale
        self._catalog_cache: dict[str, dict[str, str]] = {}

    def available_locales(self) -> list[str]:
        if not self._locale_dir.exists():
            return [self._fallback_locale]
        locales = sorted(path.stem for path in self._locale_dir.glob("*.json"))
        return locales or [self._fallback_locale]

    def set_locale(self, locale: str) -> str:
        normalized = (
            locale if locale in self.available_locales() else self._default_locale
        )
        self._current_locale = normalized
        return self._current_locale

    def get_locale(self) -> str:
        return self._current_locale

    def locale_display_name(self, locale: str) -> str:
        return self.translate(f"locale.{locale}", locale=locale)

    def translate(self, key: str, **kwargs) -> str:
        text = self._lookup(self._current_locale, key)
        if text is None:
            text = self._lookup(self._fallback_locale, key)
        if text is None:
            text = key
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def has_translation(self, key: str, locale: str | None = None) -> bool:
        target_locale = locale or self._current_locale
        return (
            self._lookup(target_locale, key) is not None
            or self._lookup(self._fallback_locale, key) is not None
        )

    def _lookup(self, locale: str, key: str) -> str | None:
        return self._load_catalog(locale).get(key)

    def _load_catalog(self, locale: str) -> dict[str, str]:
        if locale in self._catalog_cache:
            return self._catalog_cache[locale]

        path = self._locale_dir / f"{locale}.json"
        if not path.exists():
            self._catalog_cache[locale] = {}
            return self._catalog_cache[locale]

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}

        catalog = _flatten_dict(raw)
        self._catalog_cache[locale] = catalog
        return catalog

    def _detect_default_locale(self) -> str:
        try:
            current_locale = locale.getdefaultlocale(
                envvars=("LC_ALL", "LC_CTYPE", "LANG", "LANGUAGE")
            )[0]
        except Exception:
            current_locale = None
        normalized = (current_locale or "").strip().replace("_", "-").casefold()
        return "zh-CN" if normalized.startswith("zh") else "en-US"


def _flatten_dict(data: dict, prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(_flatten_dict(value, full_key))
        else:
            flat[full_key] = str(value)
    return flat


i18n = I18nManager()


def tr(key: str, **kwargs) -> str:
    return i18n.translate(key, **kwargs)
