"""``movebot`` command-line tool."""

from __future__ import annotations

import argparse
import asyncio
import code
import json
import logging
import sys

from ._version import __version__
from .errors import MoveBotError
from .protocol import DEFAULT_LOCAL_PORT, PROTOCOL_VERSION


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="movebot", description="Tools for the MoveBot robot.")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sim = sub.add_parser("sim", help="run a simulated MoveBot on this computer")
    p_sim.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to allow other computers")
    p_sim.add_argument("--port", type=int, default=DEFAULT_LOCAL_PORT)
    p_sim.add_argument("--time-scale", type=float, default=1.0, help="run faster than real time")
    p_sim.add_argument("--noise", type=float, default=0.01, help="wheel slip (0 = perfect wheels)")
    p_sim.add_argument("--seed", type=int, default=None)
    p_sim.add_argument("--name", default=None)
    p_sim.add_argument("--world", default="ball_arena", help="ball_arena or empty")
    p_sim.add_argument(
        "--module",
        action="append",
        default=[],
        metavar="TYPE[:ID]",
        help="add a simulated module, e.g. --module distance:front_distance --module imu",
    )

    p_relay = sub.add_parser("relay", help="share one bot with several programs on this computer")
    p_relay.add_argument("target", nargs="?", default="192.168.4.1", help="the bot's address")
    p_relay.add_argument("--host", default="127.0.0.1")
    p_relay.add_argument("--port", type=int, default=DEFAULT_LOCAL_PORT)
    p_relay.add_argument("--max-clients", type=int, default=8)

    p_info = sub.add_parser("info", help="show what a bot says about itself")
    p_info.add_argument(
        "target", nargs="?", default=None, help="address, 'sim', or empty to search"
    )

    p_shell = sub.add_parser("shell", help="Python prompt with a connected `bot`")
    p_shell.add_argument("target", nargs="?", default=None)

    p_panel = sub.add_parser("panel", help="open a control panel (camera, joystick, lights)")
    p_panel.add_argument("target", nargs="?", default=None, help="address, 'sim', or empty")
    p_panel.add_argument("--port", type=int, default=None, help="web page port (default: any)")
    p_panel.add_argument("--no-browser", action="store_true", help="do not open a browser")

    p_route = sub.add_parser("route", help='drive a route, e.g. "forward 0.5; left; forward 0.5"')
    p_route.add_argument("text", help="the route, or @file to read it from a file")
    p_route.add_argument("--target", default=None)
    p_route.add_argument("--preview", action="store_true", help="only print the expected poses")

    p_wifi = sub.add_parser("wifi", help="set up how the bot connects (its own Wi-Fi or yours)")
    p_wifi.add_argument("--target", default=None, help="the bot's address (default: search)")
    wifi = p_wifi.add_subparsers(dest="wifi_command", required=True)
    wifi.add_parser("status", help="how the bot is connected now")
    wifi.add_parser("scan", help="the networks the bot can see")
    w_join = wifi.add_parser(
        "join", help="make the bot join a Wi-Fi network (asks for the password)"
    )
    w_join.add_argument("ssid", help="the network's name")
    w_join.add_argument("--no-hotspot", action="store_true",
                        help="turn the bot's own network off (default: keep it on)")  # fmt: skip
    w_join.add_argument("--static-ip", default=None, metavar="IP/BITS", help="e.g. 192.168.1.20/24")
    w_join.add_argument("--gateway", default=None)
    w_join.add_argument("--dns", default=None)
    w_join.add_argument("--open", action="store_true", help="the network has no password")
    w_hot = wifi.add_parser("hotspot", help="use only the bot's own network (direct mode)")
    w_hot.add_argument("--change-password", action="store_true", help="choose a new password")
    wifi.add_parser("reset", help="factory Wi-Fi settings (the password on the bot's label)")

    p_rename = sub.add_parser("rename", help="give the bot a new name (and its network)")
    p_rename.add_argument("name")
    p_rename.add_argument("--target", default=None)

    p_restart = sub.add_parser("restart", help="restart the bot")
    p_restart.add_argument("--target", default=None)

    sub.add_parser("version", help="print versions")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return _COMMANDS[args.command](args)
    except MoveBotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def _sim(args: argparse.Namespace) -> int:
    from ._studio import load

    sim = load("sim", "The simulator (movebot sim)")
    SimOptions, SimServer = sim.SimOptions, sim.SimServer

    async def run() -> None:
        options = SimOptions(
            time_scale=args.time_scale,
            noise=args.noise,
            seed=args.seed,
            name=args.name,
            world=args.world,
            modules=args.module,
        )
        server = SimServer(host=args.host, port=args.port, options=options)
        await server.start()
        print(f"Simulated {server.bot.name} is running at {server.url}")
        print("Connect with Bot() from this computer. Press Ctrl+C to stop.")
        await asyncio.Event().wait()

    try:
        asyncio.run(run())
    except OSError as exc:
        print(f"error: could not start the simulator on port {args.port}: {exc}", file=sys.stderr)
        return 1
    return 0


def _relay(args: argparse.Namespace) -> int:
    from .relay import Relay

    async def run() -> None:
        relay = Relay(args.target, host=args.host, port=args.port, max_clients=args.max_clients)
        await relay.start()
        print(f"Sharing {relay.conn.hello.get('name', 'MoveBot')} at {relay.url}")
        print("Programs on this computer can now use Bot(). Press Ctrl+C to stop.")
        try:
            await asyncio.Event().wait()
        finally:
            await relay.stop()

    try:
        asyncio.run(run())
    except OSError as exc:
        print(f"error: could not start the relay: {exc}", file=sys.stderr)
        return 1
    return 0


def _panel(args: argparse.Namespace) -> int:
    from .bot import Bot
    from .ui import control_panel

    with Bot(args.target) as bot:
        app = control_panel(bot)
        app.port = args.port if args.port is not None else app.port
        if args.no_browser:
            app.open_browser = False
        app.run()
    return 0


def _info(args: argparse.Namespace) -> int:
    from .bot import Bot

    with Bot(args.target) as bot:
        print(json.dumps(bot.info, indent=2))
    return 0


def _shell(args: argparse.Namespace) -> int:
    from .bot import Bot
    from .route import Route

    with Bot(args.target) as bot:
        banner = (
            f"Connected to {bot.name}. Try: bot.forward(0.2), bot.left(), bot.lights.on(), "
            "print(bot.pose)\nExit with exit() or Ctrl+Z / Ctrl+D."
        )
        code.interact(banner=banner, local={"bot": bot, "Route": Route}, exitmsg="Bye!")
    return 0


def _route(args: argparse.Namespace) -> int:
    from .bot import Bot
    from .models import Pose
    from .route import Route

    text = args.text
    if text.startswith("@"):
        with open(text[1:], encoding="utf-8") as fh:
            text = fh.read()
    try:
        route = Route.parse(text)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.preview:
        for i, compiled in enumerate(route.compile(Pose()), 1):
            print(f"{i:>3}  {compiled.label:<24} -> {compiled.expected}")
        return 0
    with Bot(args.target) as bot:
        print(bot.run_route(route))
    return 0


def _wifi(args: argparse.Namespace) -> int:
    import getpass

    from .bot import Bot

    with Bot(args.target) as bot:
        command = args.wifi_command
        if command == "status":
            status = bot.wifi.status()
            print(f"{bot.name}: {status}")
            if status.address:
                print(f"Reach it at: {status.address}")
        elif command == "scan":
            for network in bot.wifi.scan():
                print(network)
        elif command == "join":
            password = "" if args.open else getpass.getpass(f"Password for {args.ssid}: ")
            print(f"Trying {args.ssid}…")
            result = bot.wifi.join(
                args.ssid, password, keep_hotspot=not args.no_hotspot, static_ip=args.static_ip,
                gateway=args.gateway, dns=args.dns,
            )  # fmt: skip
            print(f"Done: {bot.name} {result.message if result else 'saved the network'}.")
            hostname = bot.wifi.status().hostname if not args.no_hotspot else None
            if args.no_hotspot:
                print(f"Connect this computer to {args.ssid}, then use the robot's address "
                      f"({result.ip if result else 'see its screen'}).")  # fmt: skip
            elif hostname:
                print(f"On {args.ssid} it is {hostname}.local; its own network stays on too.")
        elif command == "hotspot":
            password = None
            if args.change_password:
                password = getpass.getpass("New password for the bot's network (8+ characters): ")
            bot.wifi.hotspot(password=password)
            print(f"{bot.name} now uses only its own network. Connect this computer to it.")
        elif command == "reset":
            bot.wifi.reset()
            print("Factory Wi-Fi settings: the bot's own network, with the password on its label.")
    return 0


def _rename(args: argparse.Namespace) -> int:
    from .bot import Bot

    with Bot(args.target) as bot:
        bot.rename(args.name, restart=True)
        print(f"The bot is now called {bot.name}.")
    return 0


def _restart(args: argparse.Namespace) -> int:
    from .bot import Bot

    with Bot(args.target) as bot:
        bot.restart()
        print(f"{bot.name} restarted.")
    return 0


def _version(args: argparse.Namespace) -> int:
    print(f"movebot {__version__} (protocol {PROTOCOL_VERSION})")
    return 0


_COMMANDS = {
    "sim": _sim,
    "relay": _relay,
    "panel": _panel,
    "info": _info,
    "shell": _shell,
    "route": _route,
    "wifi": _wifi,
    "rename": _rename,
    "restart": _restart,
    "version": _version,
}

if __name__ == "__main__":
    raise SystemExit(main())
