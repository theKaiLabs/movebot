# 3. Units and coordinate frames

Date: 2026-10-12 · Status: accepted

## Decision

* **Wire protocol:** SI units (metres, seconds, radians), durations in integer milliseconds,
  ROS REP-103 frames (x forward, y left, yaw counter-clockwise positive, wrapped to [-π, π)).
  The odometry frame starts at power-on or the last `odom.reset`.
* **Beginner Python API:** metres, seconds and **degrees** (`bot.left(90)`,
  `bot.drive(0.1, turn_rate=30)`); the speed limit is in percent (`bot.speed = 50`).
  `Pose` has `yaw` (radians) and `heading` (degrees).
* Robot geometry and limits come from `hello` (`geometry`, `limits`), never from constants in
  client code.

## Consequences

The ROS bridge maps messages one to one without unit conversions. The library converts
degrees to radians in exactly one place (route compilation).
