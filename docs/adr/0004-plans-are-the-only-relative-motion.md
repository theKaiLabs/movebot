# 4. Plans are the only way to send relative motion

Date: 2026-10-12 · Status: accepted

## Context

Wi-Fi in schools drops and jitters. A script that has to feed the bot every few
milliseconds makes the robot only as reliable as the link. Retried commands must not move the
bot twice.

## Decision

* All relative motion (drive 0.5 m, turn 90°, arc, wait) is a numbered **plan step**. A plan
  is uploaded once and executed by the bot on its own (protocol §6).
* A single move such as `bot.forward(0.5)` is just a step appended to an open "session" plan
  owned by the library. There are no separate `move.*` commands, so the firmware has one
  motion-sequencing mechanism.
* Steps carry consecutive `seq` numbers. The bot ignores duplicates and rejects gaps, a step
  starts at most once, and `boot_id` exposes reboots. Together these give ordered,
  exactly-once execution across reconnects.
* Every other command sets an absolute value (no "toggle"), and the bot de-duplicates request
  ids, so the transport may re-send any pending request after reconnecting.
* What happens when the owner disconnects is chosen per plan (`continue`, `finish_step`,
  `stop`). Manual control (`drive.velocity`, `motor.write`) instead always expires after
  `command_timeout_ms`.

## Consequences

* Routes keep running through Wi-Fi drops, and the library resumes supervision with
  `plan.status` / `plan.results`.
* The firmware needs a small queue (`limits.plan_queue`) and a results ring buffer. The
  library streams longer routes as space frees up.
* Conditionals ("if blocked, turn") are not possible bot-side in v0.1. Reactive behaviour
  (vision) uses manual velocity control from the host.
