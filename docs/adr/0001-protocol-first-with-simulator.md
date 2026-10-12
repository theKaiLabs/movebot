# 1. Protocol first, simulator second, hardware last

Date: 2026-10-12 · Status: accepted

## Context

The firmware for the ESP32-CAM does not exist yet, but the library, the desktop app, the
lessons and the ROS bridge all need a bot to talk to. Students in a class will often share
one robot between several people.

## Decision

* The wire protocol (`protocol/SPEC.md`) is the contract between all parts. It is versioned
  `MAJOR.MINOR` and checked at connect time (`hello.protocol`).
* A simulator in the `movebot` package implements the full protocol, including the plan
  engine and fault injection. It is the **reference implementation**.
* A conformance suite (`protocol/conformance`) talks raw JSON to any endpoint. It runs against
  the simulator in CI and against real firmware with `--target`.
* A JSON Schema validates every message the suite receives.

## Consequences

* Software work is not blocked by hardware, and the firmware team gets an executable spec.
* Students can learn without a robot (`Bot("sim")`).
* The simulator must be kept honest. When real firmware behaves differently, the spec decides
  who is wrong, and the simulator's noise and timing are calibrated against the real bot.
