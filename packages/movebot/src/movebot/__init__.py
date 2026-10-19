"""movebot – program the MoveBot learning robot from Python.

>>> from movebot import Bot
>>> bot = Bot("sim")        # a simulated bot; use Bot() for the real one
>>> bot.forward(0.5)
>>> bot.left()
"""

from ._version import __version__
from .aio import AsyncBot
from .bot import Bot, MoveHandle, RouteHandle
from .errors import (
    BotBusy,
    BotInUse,
    BotNotFound,
    BotTimeout,
    CommandError,
    ConnectionLost,
    IncompatibleBot,
    InvalidParameter,
    MoveBotError,
    MoveCancelled,
    MoveFailed,
    PlanLost,
    WifiJoinFailed,
)
from .models import Encoders, Pose, RouteResult, StepResult, WifiNetwork, WifiStatus, WifiTest
from .protocol import PROTOCOL_VERSION
from .route import Route

__all__ = [
    "PROTOCOL_VERSION",
    "AsyncBot",
    "Bot",
    "BotBusy",
    "BotInUse",
    "BotNotFound",
    "BotTimeout",
    "CommandError",
    "ConnectionLost",
    "Encoders",
    "IncompatibleBot",
    "InvalidParameter",
    "MoveBotError",
    "MoveCancelled",
    "MoveFailed",
    "MoveHandle",
    "PlanLost",
    "Pose",
    "Route",
    "RouteHandle",
    "RouteResult",
    "StepResult",
    "WifiJoinFailed",
    "WifiNetwork",
    "WifiStatus",
    "WifiTest",
    "__version__",
]
