"""Setting the bot up: Wi-Fi modes and passwords, name, restart (SPEC §12).

The simulator "sees" made-up networks: Classroom (password robots123), School-Guest (open),
eduroam (enterprise) and Home-2.4G.
"""

from __future__ import annotations

import pytest

pytest.importorskip("movebot_studio.sim", reason="the simulator comes with the MoveBot app")
from movebot import Bot, WifiJoinFailed
from movebot.bot import _static_address
from movebot.cli import main


@pytest.fixture
def bot():
    b = Bot.simulated(time_scale=20)
    yield b
    b.close()


def test_a_new_bot_uses_its_own_network(bot):
    status = bot.wifi.status()
    assert status.mode == "ap" and status.hotspot["ssid"] == bot.name
    assert status.ip == "192.168.4.1" and status.network is None
    assert status.hostname.startswith("movebot-") and not status.pending_restart
    assert "own network" in str(status)


def test_scan_lists_networks_strongest_first(bot):
    networks = bot.wifi.scan()
    assert networks[0].ssid == "Classroom"
    assert [n.rssi for n in networks] == sorted((n.rssi for n in networks), reverse=True)
    guest = next(n for n in networks if n.ssid == "School-Guest")
    assert not guest.needs_password and 0 <= guest.bars <= 4
    assert "▮" in str(networks[0])


def test_testing_a_network_changes_nothing(bot):
    wrong = bot.wifi.test("Classroom", "nope")
    assert not wrong.joined and wrong.reason == "wrong_password"
    assert "password is wrong" in wrong.message
    assert bot.wifi.test("Nowhere", "x").reason == "not_found"
    assert bot.wifi.test("eduroam", "x").reason == "unsupported"
    right = bot.wifi.test("Classroom", "robots123")
    assert right.joined and right.ip.startswith("192.168.1.")
    assert bot.wifi.status().saved["mode"] == "ap"


def test_join_tries_first_and_saves_nothing_when_it_fails(bot):
    with pytest.raises(WifiJoinFailed, match="password is wrong") as info:
        bot.wifi.join("Classroom", "nope")
    assert info.value.reason == "wrong_password"
    assert bot.wifi.status().saved["mode"] == "ap"


def test_join_a_network_and_keep_the_hotspot(bot):
    boot = bot.info["boot_id"]
    result = bot.wifi.join("Classroom", "robots123")  # restarts, then reconnects
    assert result.joined
    assert bot.info["boot_id"] != boot
    status = bot.wifi.status()
    assert status.mode == "ap+sta" and status.network["state"] == "connected"
    assert status.ip == result.ip and status.address == f"{status.hostname}.local"
    assert status.saved["has_password"] and "password" not in status.saved
    assert "on the network Classroom" in str(status)


def test_static_address(bot):
    good = bot.wifi.test(
        "Classroom", "robots123", static_ip="192.168.1.20/24", gateway="192.168.1.1"
    )
    assert good.joined and good.ip == "192.168.1.20"
    wrong_subnet = bot.wifi.test("Classroom", "robots123", static_ip="10.0.0.5", gateway="10.0.0.1")
    assert wrong_subnet.reason == "no_ip"
    assert _static_address("192.168.1.20/24", "192.168.1.1", None) == {
        "ip": "192.168.1.20", "netmask": "255.255.255.0", "gateway": "192.168.1.1",
    }  # fmt: skip
    with pytest.raises(ValueError, match="gateway"):
        _static_address("192.168.1.20", None, None)
    with pytest.raises(ValueError, match="address"):
        _static_address("192.168.1.300/24", "192.168.1.1", None)


def test_hotspot_password_and_reset(bot):
    bot.wifi.hotspot(password="classroom7", restart=False)
    assert bot.wifi.status().pending_restart is False  # same mode and security: nothing new
    with pytest.raises(Exception, match="8-63"):
        bot.wifi.hotspot(password="short", restart=False)
    bot.wifi.join("School-Guest", restart=False)  # an open network
    assert bot.wifi.status().pending_restart is True
    bot.wifi.reset(restart=False)
    assert bot.wifi.status().saved["mode"] == "ap"


def test_rename_and_restart(bot):
    bot.rename("Rover 7")
    assert bot.name != "Rover 7"  # only after a restart
    bot.restart()
    assert bot.name == "Rover 7"
    assert bot.wifi.status().hotspot["ssid"] == "Rover 7"
    with pytest.raises(Exception, match="1-24"):
        bot.rename("Robot/One!")


def test_command_line(capsys, monkeypatch):
    assert main(["wifi", "--target", "sim", "scan"]) == 0
    assert "Classroom" in capsys.readouterr().out
    assert main(["wifi", "--target", "sim", "status"]) == 0
    assert "own network" in capsys.readouterr().out
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "nope")
    assert main(["wifi", "--target", "sim", "join", "Classroom"]) == 1  # wrong password
    assert "password is wrong" in capsys.readouterr().err
