"""Protocol helpers and the schema test vectors."""

from __future__ import annotations

import json
import pathlib

import pytest
from jsonschema import Draft202012Validator
from movebot.connection import normalize_url
from movebot.protocol import is_compatible

PROTOCOL_DIR = pathlib.Path(__file__).resolve().parents[3] / "protocol"
SCHEMA = json.loads((PROTOCOL_DIR / "schema" / "movebot.schema.json").read_text(encoding="utf-8"))
VECTORS = json.loads((PROTOCOL_DIR / "vectors" / "messages.json").read_text(encoding="utf-8"))


def test_schema_is_valid():
    Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=lambda v: v["name"])
def test_vectors(vector):
    errors = list(Draft202012Validator(SCHEMA).iter_errors(vector["message"]))
    assert (not errors) == vector["valid"], [e.message for e in errors]


@pytest.mark.parametrize(
    ("remote", "local", "ok"),
    [
        ("0.1", "0.1", True),
        ("0.2", "0.1", False),  # before 1.0 minors must match
        ("1.3", "1.2", True),  # after 1.0 newer minors only add features
        ("1.1", "1.2", False),
        ("2.0", "1.0", False),
        ("garbage", "0.1", False),
    ],
)
def test_version_compatibility(remote, local, ok):
    assert is_compatible(remote, local) is ok


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("192.168.4.1", "ws://192.168.4.1:80/ws"),
        ("localhost:8765", "ws://localhost:8765/ws"),
        ("ws://10.0.0.5:81/ws", "ws://10.0.0.5:81/ws"),
        ("movebot-1a2b.local", "ws://movebot-1a2b.local:80/ws"),
    ],
)
def test_normalize_url(given, expected):
    assert normalize_url(given) == expected


def test_normalize_url_rejects_other_schemes():
    with pytest.raises(ValueError):
        normalize_url("http://192.168.4.1")
