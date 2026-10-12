# Module types

A **module** is anything plugged into MoveBot beyond the wheels, camera, lights and status
LEDs: distance sensors, an IMU, line sensors, a gripper... The firmware hides the bus
(UART, I²C, ...) and the wiring. On the wire every module is just an id, a type, some
values and some actions (protocol SPEC §8), so a new kind of module needs no new protocol
commands.

Each file here describes one module **type** and is the contract between the firmware
driver, the Python library, the simulator and the docs. Files must match
[`descriptor.schema.json`](descriptor.schema.json); the test suite checks this.

| Type | File | Values |
|---|---|---|
| `distance` | [distance.json](distance.json) | `distance` (m or null), `valid` |
| `imu` | [imu.json](imu.json) | `heading` (rad), `gyro_z` (rad/s), `accel_x`, `accel_y` (m/s²) |

## Adding a new module type

1. **Describe it.** Add `<type>.json` here: its values with units, its actions with their
   arguments, and any events. Values use SI units and radians like the rest of the protocol.
2. **Firmware.** Write a driver that reports the module in `hello.modules` (and
   `module.added` / `module.removed` if it can be plugged in while running), answers
   `module.read` with exactly the described values, and implements the actions.
3. **Library (optional).** Without any code, `bot.modules.<id>.<value>` and
   `bot.modules.<id>.<action>()` already work. For a nicer API (beginner units, docstrings),
   add a small driver class to `packages/movebot/src/movebot/modules.py`:

   ```python
   @register("line")
   class LineSensor(Module):
       @property
       def position(self) -> float:
           """Where the line is: -1 (far left) to 1 (far right)."""
           return self.read()["position"]
   ```

4. **Simulator (recommended).** Add a `SimModule` subclass to
   `packages/movebot/src/movebot/sim/modules.py` so lessons can use the module without
   hardware, and register it in `SIM_MODULES`.
5. **Tests.** The suite checks that simulated modules report exactly the values and actions
   their descriptor lists.

Bump `version` in the descriptor when a module type changes incompatibly; clients can see
the version in `hello.modules`.
