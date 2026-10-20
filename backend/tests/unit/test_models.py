"""Models must stay in sync with contracts/digest.schema.json.

Reads the contract JSON and asserts every model's field set matches the schema's
required + optional properties. Catches contract drift at test time without an
extra jsonschema dependency.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel

from app.models import (
    Deadline,
    Decision,
    Digest,
    GroupDigest,
    Message,
    NeedsYouItem,
    PersonPoints,
    Platform,
    Window,
)

JSON_SCHEMA = dict[str, Any]

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "digest.schema.json"

MODELS: dict[str, Callable[[], type[BaseModel]]] = {
    "Message": lambda: Message,
    "Window": lambda: Window,
    "NeedsYouItem": lambda: NeedsYouItem,
    "Decision": lambda: Decision,
    "PersonPoints": lambda: PersonPoints,
    "Deadline": lambda: Deadline,
    "GroupDigest": lambda: GroupDigest,
    "Digest": lambda: Digest,
}


def schema_defs() -> JSON_SCHEMA:
    contract = cast(JSON_SCHEMA, json.loads(CONTRACT_PATH.read_text(encoding="utf-8")))
    defs: JSON_SCHEMA = contract["$defs"]
    return defs


def test_platform_enum_matches_schema() -> None:
    platform: JSON_SCHEMA = schema_defs()["Platform"]
    schema_enum = set(cast(list[str], platform["enum"]))
    assert {p.value for p in Platform} == set(schema_enum)


@pytest.mark.parametrize("def_name", list(MODELS))
def test_fields_match_contract(def_name: str) -> None:
    schema: JSON_SCHEMA = schema_defs()[def_name]
    props: JSON_SCHEMA = schema["properties"]
    schema_props = set(props)
    model = MODELS[def_name]()
    wire_names = set()
    required_wire = set()
    for name, field in model.model_fields.items():
        alias = field.alias if field.alias is not None else name
        wire_names.add(alias)
        if field.is_required():
            required_wire.add(alias)
    assert wire_names == schema_props, (
        f"{def_name}: fields drift\nmodel={wire_names}\nschema={schema_props}"
    )
    assert set(cast(list[str], schema["required"])) <= required_wire


def test_needs_you_alias_round_trip() -> None:
    item = NeedsYouItem.model_validate(
        {"message_id": "m1", "from": "Asha", "summary": "picked venue", "reason": "question"}
    )
    assert item.from_ == "Asha"
    dumped = item.model_dump(by_alias=True)
    assert dumped["from"] == "Asha"


def test_digest_round_trip_example() -> None:
    digest = Digest.model_validate(
        {
            "id": "2026-03-14-1830-abcdef",
            "generated_at": "2026-03-14T18:30:00Z",
            "window": {"start": "2026-03-13T18:00:00Z", "end": "2026-03-14T06:00:00Z"},
            "model": "fake",
            "prompt_version": "v1",
            "groups": [
                {
                    "conversation_id": "conv1",
                    "platform": "whatsapp",
                    "name": "Food Friends",
                    "message_count": 3,
                    "skipped_count": 1,
                    "tldr": "Two sentences max.",
                    "needs_you": [
                        {
                            "message_id": "wa:conv1:2",
                            "from": "Asha",
                            "summary": "?",
                            "reason": "asked you",
                        }
                    ],
                    "decisions": [{"text": "meet 7pm", "message_ids": ["wa:conv1:3"]}],
                    "by_person": [{"name": "Asha", "points": ["proposed 6pm"]}],
                    "deadlines": [{"text": "reply by Friday", "message_ids": ["wa:conv1:4"]}],
                }
            ],
        }
    )
    assert digest.groups[0].needs_you[0].message_id == "wa:conv1:2"
