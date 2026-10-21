"""Runtime user settings (A3.4): JSON overrides layered on env defaults.

User-facing fields (per contracts/openapi.yaml Settings): user_names,
vip_people, keywords, digest_time, model. GET /settings returns the merged
view; PUT /settings persists a partial update to ``settings.json`` next to
the SQLite db so the scheduler and digest runs pick it up without restart.
"""

import json
from pathlib import Path
from typing import Any

from app.config import Settings

FIELDS = ("user_names", "vip_people", "keywords", "digest_time", "model")


class UserSettings:
    def __init__(self, settings: Settings, path: str | Path | None = None) -> None:
        self._settings = settings
        default = Path(settings.db_path).parent / "settings.json"
        self.path = Path(path) if path is not None else default

    def _overrides_path(self) -> Path:
        return self.path

    def load_overrides(self) -> dict[str, Any]:
        try:
            data = json.loads(self._overrides_path().read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if k in FIELDS}

    def view(self) -> dict[str, Any]:
        base = {field: getattr(self._settings, field) for field in FIELDS}
        overrides = self.load_overrides()
        return {**base, **overrides}

    def update(self, patch: dict[str, Any]) -> dict[str, Any]:
        overrides = {
            field: patch[field] for field in FIELDS if field in patch and patch[field] is not None
        }
        merged = {**self.load_overrides(), **overrides}
        self._overrides_path().parent.mkdir(parents=True, exist_ok=True)
        self._overrides_path().write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return self.view()
