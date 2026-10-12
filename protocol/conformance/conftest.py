"""Conformance suite for the MoveBot wire protocol.

    pytest protocol/conformance                          # against the simulator (MoveBot app)
    pytest protocol/conformance --target ws://192.168.4.1/ws   # against a real bot

The client here deliberately speaks raw JSON over WebSocket instead of using the movebot
library, so it tests the wire behaviour itself. Every message received is validated
against ``protocol/schema/movebot.schema.json``.

Tests marked ``sim_only`` need simulator fault injection and are skipped on real bots.
"""

from __future__ import annotations

import json
import pathlib
import secrets
import time
from dataclasses import dataclass
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match
from websockets.sync.client import ClientConnection, connect

PROTOCOL_DIR = pathlib.Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROTOCOL_DIR / "schema" / "movebot.schema.json"
MODULES_DIR = PROTOCOL_DIR / "modules"


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("movebot conformance")
    group.addoption(
        "--target", default=None, help="ws:// URL of the bot to test (default: simulator)"
    )
    group.addoption("--time-scale", type=float, default=20.0, help="simulator speed-up")
    group.addoption(
        "--via-relay",
        action="store_true",
        help="test the simulator through a movebot relay (checks the relay behaves like a bot)",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "sim_only: needs simulator fault injection")


@dataclass
class Target:
    url: str
    sim: Any  # SimulatorThread when testing the simulator, else None
    hello: dict[str, Any]


@pytest.fixture(scope="session")
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.fixture(scope="session")
def target(request: pytest.FixtureRequest, validator: Draft202012Validator) -> Any:
    url = request.config.getoption("--target")
    if url:
        with Client(url, validator) as probe:
            hello = probe.hello
        yield Target(url, None, hello)
        return
    sim = pytest.importorskip(
        "movebot_studio.sim",
        reason="no --target given and the simulator (MoveBot app) is not installed",
    )
    SimOptions, SimulatorThread = sim.SimOptions, sim.SimulatorThread

    scale = request.config.getoption("--time-scale")
    options = SimOptions(time_scale=scale, modules=["distance:front_distance", "imu"])
    with SimulatorThread(options) as sim:
        if request.config.getoption("--via-relay"):
            from movebot.relay import RelayThread

            with RelayThread(sim.url) as relay:
                with Client(relay.url, validator) as probe:
                    hello = probe.hello
                yield Target(relay.url, sim, hello)
            return
        with Client(sim.url, validator) as probe:
            hello = probe.hello
        yield Target(sim.url, sim, hello)


@pytest.fixture(autouse=True)
def _skip_sim_only(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("sim_only"):
        target = request.getfixturevalue("target")
        if target.sim is None:
            pytest.skip("needs the simulator")


@pytest.fixture
def connect_client(target: Target, validator: Draft202012Validator) -> Any:
    """Factory for extra connections; all are closed after the test."""
    clients: list[Client] = []

    def factory() -> Client:
        client = Client(target.url, validator)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


@pytest.fixture
def client(connect_client: Any) -> Client:
    """A fresh connection to an idle bot (any running plan is stopped first)."""
    c = connect_client()
    c.ok("stop")
    c.ok("unsub", topics=["odom", "encoders", "power", "net", "status"])
    c.drain()
    return c


def plan_id() -> str:
    return "t" + secrets.token_hex(6)


class Client:
    def __init__(self, url: str, validator: Draft202012Validator) -> None:
        self.validator = validator
        self.ws: ClientConnection = connect(
            url, open_timeout=5, ping_interval=None, close_timeout=1
        ).__enter__()
        self.prefix = secrets.token_hex(4)
        self.counter = 0
        self.inbox: list[dict[str, Any]] = []
        self.hello = self.recv(5)
        assert self.hello["type"] == "hello", self.hello

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self.ws.__exit__(None, None, None)

    def next_id(self) -> str:
        self.counter += 1
        return f"{self.prefix}-{self.counter}"

    def recv(self, timeout: float) -> dict[str, Any]:
        message = json.loads(self.ws.recv(timeout=timeout))
        error = best_match(self.validator.iter_errors(message))
        if error is not None:
            raise AssertionError(f"message does not match the schema: {error.message}\n{message}")
        return message

    def send(self, message: dict[str, Any] | str) -> None:
        self.ws.send(message if isinstance(message, str) else json.dumps(message))

    def req(
        self, cmd: str, *, rid: Any = None, timeout: float = 5, **params: Any
    ) -> dict[str, Any]:
        rid = self.next_id() if rid is None else rid
        self.send({"type": "req", "id": rid, "cmd": cmd, **params})
        return self.response(rid, timeout)

    def response(self, rid: Any, timeout: float = 5) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            message = self.recv(max(0.01, deadline - time.monotonic()))
            if message["type"] == "res" and message["id"] == rid:
                return message
            self.inbox.append(message)

    def ok(self, cmd: str, **params: Any) -> dict[str, Any]:
        res = self.req(cmd, **params)
        assert res["ok"], f"{cmd} failed: {res.get('error')}"
        return res

    def err(self, cmd: str, code: str, **params: Any) -> dict[str, Any]:
        res = self.req(cmd, **params)
        assert not res["ok"], f"{cmd} should have failed with {code}"
        assert res["error"]["code"] == code, res["error"]
        return res

    def wait_for(
        self, kind: str, name: str | None = None, timeout: float = 5, **match: Any
    ) -> dict[str, Any]:
        """Wait for an event (kind='evt', name=evt) or telemetry (kind='tlm', name=topic)."""
        key = "evt" if kind == "evt" else "topic"

        def matches(m: dict[str, Any]) -> bool:
            return (
                m["type"] == kind
                and (name is None or m.get(key) == name)
                and all(m.get(k) == v for k, v in match.items())
            )

        for i, message in enumerate(self.inbox):
            if matches(message):
                return self.inbox.pop(i)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f"no {kind} {name} {match} within {timeout}s")
            message = self.recv(remaining)
            if matches(message):
                return message
            self.inbox.append(message)

    def drain(self) -> None:
        self.inbox.clear()
        while True:
            try:
                self.inbox.append(self.recv(0.05))
            except TimeoutError:
                break
        self.inbox.clear()

    def wait_state(self, pid: str, states: set[str], timeout: float = 10) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            status = self.ok("plan.status", plan_id=pid)
            if status["state"] in states:
                return status
            if time.monotonic() > deadline:
                raise AssertionError(f"plan {pid} stayed {status['state']}, wanted {states}")
            time.sleep(0.02)
