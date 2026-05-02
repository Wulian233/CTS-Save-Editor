import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

CURRENT_VERSION = "0.1.0"
DEFAULT_UPDATE_JSON_URL = "http://cdn.maxing.site/update/app/cts_save_editor.json"
UPDATE_JSON_URL = os.environ.get("CTS_UPDATE_JSON_URL", DEFAULT_UPDATE_JSON_URL).strip()
UPDATE_TIMEOUT_SECONDS = 6


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    download_url: str
    changelog: str
    title: str = ""


def check_for_update(url: str = UPDATE_JSON_URL) -> UpdateInfo | None:
    if not url:
        return None

    payload = _fetch_json(url)
    info = _parse_update_info(payload)
    if not info or not info.download_url:
        return None
    if _compare_versions(info.version, CURRENT_VERSION) <= 0:
        return None
    return info


def _fetch_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"CTS-Save-Editor/{CURRENT_VERSION}",
        },
    )
    with urlopen(request, timeout=UPDATE_TIMEOUT_SECONDS) as response:
        content = response.read(64 * 1024)
    data = json.loads(content.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Update JSON root must be an object")
    return data


def _parse_update_info(data: dict[str, Any]) -> UpdateInfo | None:
    version = _first_text(data, "version", "latest_version", "tag_name")
    if not version:
        return None

    download_url = _first_text(data, "download_url", "download", "url", "html_url")

    changelog = _localized_text(
        data.get("changelog")
        or data.get("release_notes")
        or data.get("notes")
        or data.get("body")
    )
    title = _first_text(data, "title", "name")

    return UpdateInfo(
        version=version.lstrip("vV"),
        download_url=download_url,
        changelog=changelog,
        title=title,
    )


def _first_text(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _localized_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, dict):
        for key in ("zh-CN", "zh", "en-US", "en", "default"):
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                return text.strip()
        return "\n".join(
            f"{key}: {text}" for key, text in value.items() if isinstance(text, str)
        )
    return ""


def _compare_versions(left: str, right: str) -> int:
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    length = max(len(left_parts), len(right_parts))
    left_parts.extend([0] * (length - len(left_parts)))
    right_parts.extend([0] * (length - len(right_parts)))
    return (left_parts > right_parts) - (left_parts < right_parts)


def _version_parts(version: str) -> list[int]:
    parts: list[int] = []
    for part in version.lstrip("vV").replace("-", ".").split("."):
        digits = "".join(char for char in part if char.isdigit())
        parts.append(int(digits or "0"))
    return parts
