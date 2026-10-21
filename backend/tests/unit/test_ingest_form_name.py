"""Regression: /ingest/file must read conversation_name from multipart form data.

B caught this via the demo flow: without the Form() annotation FastAPI treats
the field as a query parameter, so Frontend uploads (FormData) fell back to
the file stem as conversation name (7.12: exports carry no group name).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app

SAMPLE = "19/10/2026, 20:02 - Riya: camp is booked for the 21st"


def test_conversation_name_form_field_is_honored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SLOTH_DB_PATH", str(tmp_path / "sloth.db"))
    monkeypatch.setenv("SLOTH_DROP_FOLDER", str(tmp_path / "drop"))
    (tmp_path / "drop").mkdir()
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.post(
                "/ingest/file",
                files={"file": ("group-export.txt", SAMPLE.encode())},
                data={"conversation_name": "Fresh Kills and Chills"},
            )
            assert response.status_code == 200, response.text
            names = {conv["name"] for conv in client.get("/sources").json()["conversations"]}
            assert "Fresh Kills and Chills" in names
            assert "group-export" not in names
    finally:
        get_settings.cache_clear()
