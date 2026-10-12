# 6. The simulator and the UI kit ship with the (closed) MoveBot app

Date: 2026-10-12 · Status: accepted (amends the open/closed split in plan §3.1)

## Context

Students and teachers use MoveBot through the installable app. The simulator and the UI kit
are part of what makes the app worth having, and the app is closed source.

## Decision

* `movebot_studio.sim` (simulator) and `movebot_studio.ui` (UI kit) live in the private
  `movebot-studio` repository.
* The public `movebot` library keeps everything needed to program a robot: protocol,
  connection, `Bot`, routes, plans, camera, modules, relay, and the conformance suite.
* The public API does not change: `from movebot.ui import App`, `Bot("sim")`,
  `Bot.simulated()`, `movebot sim` and `movebot panel` load the app's implementation when it
  is installed (as it always is in the app's Python) and otherwise raise `NeedsMoveBotApp`
  with an explanation.
* The UI kit's API is documented publicly ([docs/ui.md](../ui.md)), and examples and lessons
  stay public (`content/`).
* `movebot-studio` includes this repository as a **git submodule**, not the other way round.
  Anyone with access clones the studio repository and has both, with every test runnable;
  this repository stays self-contained for outside contributors, and its lock file and CI
  never refer to private code. Studio releases pin the exact library commit they shipped.

## Consequences

* In this repository alone, tests that need the simulator are skipped (`pytest.importorskip`);
  they run in full from a studio checkout. The conformance suite still runs against real
  firmware with `--target`.
* Outside contributors can change the library and examples, but test them against a real
  robot or ask a maintainer to run the full suite.
* A future, more detailed simulator (a real model of the bot) also goes into the app.
