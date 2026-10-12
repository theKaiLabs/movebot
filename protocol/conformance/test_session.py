"""Connection, hello, request/response basics (SPEC §1, §3)."""

from __future__ import annotations

import time

import pytest


def test_hello_describes_the_bot(target):
    hello = target.hello
    assert hello["protocol"] == "0.1"
    assert len(hello["boot_id"]) >= 8, "boot_id should carry at least 32 random bits"
    assert hello["limits"]["plan_queue"] >= 4
    assert set(hello["capabilities"]["step_ops"]) >= {"drive", "turn", "wait"}


def test_boot_id_is_stable_across_connections(target, connect_client):
    assert connect_client().hello["boot_id"] == target.hello["boot_id"]


def test_ping_and_info(client):
    assert isinstance(client.ok("ping")["t"], int)
    info = client.ok("info")
    assert info["boot_id"] == client.hello["boot_id"]


def test_integer_ids_are_accepted(client):
    assert client.req("ping", rid=4242)["ok"]


def test_malformed_frames_get_bad_request(client):
    client.send("this is not json")
    assert client.response(None)["error"]["code"] == "bad_request"
    client.send('{"type":"req","cmd":"ping"}')  # no id
    assert client.response(None)["error"]["code"] == "bad_request"


def test_unknown_command(client):
    client.err("teleport", "unknown_command")


def test_duplicate_request_id_is_not_executed_twice(client):
    rid = client.next_id()
    first = client.req("light.set", rid=rid, name="light_left", level=1)
    assert first["ok"]
    # Same id, different content: the bot must replay the stored response, not run it.
    again = client.req("light.set", rid=rid, name="light_left", level=0)
    assert again == first
    assert client.ok("light.get")["lights"]["light_left"] == 1
    client.ok("light.set", name="light_left", level=0)


def test_too_many_clients_are_refused(target, connect_client, validator):
    from websockets.exceptions import ConnectionClosed

    from .conftest import Client

    time.sleep(0.2)  # let the bot notice connections closed by earlier tests
    limit = target.hello["limits"]["max_clients"]
    for _ in range(limit):
        connect_client()
    with pytest.raises(ConnectionClosed) as info:
        Client(target.url, validator)
    assert info.value.rcvd is not None and info.value.rcvd.code == 1013
