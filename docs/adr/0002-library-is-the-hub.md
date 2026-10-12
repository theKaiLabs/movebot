# 2. No separate hub: one connection owner, the library can relay

Date: 2026-10-12 · Status: accepted, implemented (`movebot.relay`, `movebot relay`)

## Context

An ESP32 bot handles very few simultaneous connections (and usually one camera viewer), but
the app's live view, a running student script and the ROS node may all want the bot at once.

## Decision

* Exactly one process on the host owns the connection to the bot: the student's script when
  run on its own, the app when scripts run from the app, the ROS node in ROS setups.
* Others reach the bot through that owner using the **same protocol** (a relay), so the
  library does not care whether it talks to a bot, a relay or the simulator.
* `Bot()` without arguments resolves `$MOVEBOT_URL`, then `ws://127.0.0.1:8765/ws` (simulator
  or app relay), then the bot's own access point `ws://192.168.4.1/ws`.
* The bot refuses connections beyond `limits.max_clients` with close code 1013, which the
  library turns into a clear "already in use" message.

## Consequences

* No extra service to install. The relay is a library feature that the app embeds.
* The relay re-applies the bot's disconnect rules to its local clients (SPEC §11), and the
  conformance suite runs through it (`--via-relay`) to prove it behaves like a bot.
* Safety does not depend on the relay: manual commands expire on the bot itself
  (`command_timeout_ms`), and closing the controlling connection stops manual motion.
