# MoveBot wire protocol – v0.1 (draft)

Status: **draft, frozen at the end of Phase 1** (see `docs/software-plan.md`). Until 1.0, any
minor version may break compatibility; clients and bots must match `MAJOR.MINOR` exactly.

This document is normative. The machine-readable companion is
[`schema/movebot.schema.json`](schema/movebot.schema.json); the reference implementation is
the simulator in `packages/movebot/src/movebot/sim/`; and the executable test is the
[conformance suite](conformance/) (`pytest protocol/conformance --target ws://<bot>/ws`).
If they disagree, this document wins and the others get fixed.

The key words MUST, SHOULD and MAY are used as in RFC 2119.

## 1. Transport

| Channel | Where | Notes |
|---|---|---|
| Control and telemetry | WebSocket `ws://<bot>:80/ws`, text frames | One JSON object per frame, UTF-8, no NaN/Infinity. |
| Video | MJPEG over HTTP, `http://<bot>:<stream_port>/stream` (port 81 on the bot) | See §7. `hello.capabilities.camera` is `false` when there is no camera. |
| Direct mode | Bot runs an access point `MoveBot-XXXX`, bot address `192.168.4.1` | Classroom default. |
| Network mode | Bot joins a Wi-Fi network | Discovery via mDNS `_movebot._tcp` (to be specified in v0.2). |

* A bot MUST accept at least `limits.max_clients` simultaneous connections (≥ 1, recommended 2–4).
  It MUST refuse more with WebSocket close code **1013** before sending `hello`.
* Clients SHOULD send WebSocket pings (the reference client pings every 1 s and drops the
  link after 2 s without a pong).
* A simulator or a host-side relay (§11) serves the same protocol on `ws://127.0.0.1:8765/ws`.

## 2. Units and frames

SI units everywhere: metres, seconds, radians; durations in integer milliseconds (`*_ms`).
Coordinates follow ROS REP-103: **x forward, y left, yaw counter-clockwise positive**, yaw
wrapped to [-π, π). The odometry frame starts at power-on or the last `odom.reset`.
Timestamps `t` are integer milliseconds since the bot booted.

## 3. Message kinds

| `type` | Direction | Purpose |
|---|---|---|
| `hello` | bot → client | First frame on every connection. |
| `req` | client → bot | A command. Has `id` and `cmd`; parameters are top-level fields. |
| `res` | bot → client | Exactly one per request, same `id`. `ok: true` plus result fields, or `ok: false` plus `error`. |
| `evt` | bot → **all** clients | Something happened (`evt` names below). |
| `tlm` | bot → subscribed client | Periodic telemetry for one `topic`. |

Unknown fields MUST be ignored by both sides (forward compatibility).

### 3.1 hello

```json
{"type":"hello","protocol":"0.1","firmware":"1.0.0","model":"movebot-r1","name":"MoveBot-1A2B",
 "bot_id":"3f1a2b","mac":"02:4d:42:3f:1a:2b","boot_id":"c3d29e01",
 "geometry":{"wheel_diameter":0.065,"track_width":0.12,"ticks_per_rev":360},
 "limits":{"max_linear":0.4,"max_angular":4.0,"command_timeout_ms":500,"plan_queue":32,
           "plan_max_duration_ms":600000,"results_buffer":64,"max_clients":4},
 "capabilities":{"lights":["light_left","light_right"],"status_leds":["status","rgb"],
                 "color_leds":["rgb"],
                 "status_patterns":["off","on","blink","blink_fast","pulse"],
                 "topics":["odom","encoders","power","net","status"],
                 "step_ops":["drive","turn","turn_to","arc","drive_for","wait","light","status","speed","marker","stop"],
                 "camera":{"stream_port":81,"stream_path":"/stream","capture_path":"/capture",
                           "resolutions":["320x240","640x480","1280x720"],"max_fps":30,
                           "presets":{"fast":{"resolution":"320x240","fps":25,"quality":75}, ...},
                           "privacy_indicator":"dedicated"}},
 "modules":[{"id":"front_distance","type":"distance","version":1,
             "values":["distance","valid"],"actions":["set_range"],"info":{"max_range":2.0}}]}
```

* `boot_id` MUST change on every boot (random, ≥ 32 bits). Clients use it to detect restarts.
* `limits` and `capabilities` are what a client must respect; they replace any hard-coded
  pin numbers or sizes. **There is no GPIO access in the protocol.**
* `modules` lists the add-on modules attached right now (§8); it may be empty.
* A simulator adds `"sim": true`.

### 3.2 Requests and responses

```json
→ {"type":"req","id":"9f2c41aa-17","cmd":"light.set","name":"light_left","level":1}
← {"type":"res","id":"9f2c41aa-17","ok":true,"name":"light_left","level":1}
← {"type":"res","id":"9f2c41aa-18","ok":false,"error":{"code":"invalid_param","msg":"'level' must be between 0 and 1"}}
```

* `id` is a string (≤ 64 chars) or integer, **unique for the lifetime of the client**. The
  recommended form is `<random 8 hex>-<counter>`.
* **Idempotency.** Every command is either a read or sets an absolute value (there is no
  "toggle"); relative motion only exists as numbered plan steps (§6). Therefore re-sending a
  request after a lost connection is safe.
* **De-duplication.** The bot MUST remember the responses to at least its last 64 request
  ids and reply to a repeated `id` with the stored response without executing it again.
* **Reserved names.** Request parameters MUST NOT be called `type`, `id` or `cmd`, and
  result fields MUST NOT be called `type`, `id`, `ok` or `error`: they would overwrite the
  envelope. (That is why modules use `module_id` and `module_type`.)
* A frame that is not valid JSON, not an object, or not a `req` with an `id` gets
  `{"type":"res","id":null,"ok":false,"error":{"code":"bad_request",...}}`.

Error codes: `bad_request`, `unknown_command`, `invalid_param`, `invalid_state`, `busy`,
`unknown_plan`, `unknown_module`, `gap` (with `next_seq`), `not_supported`, `internal`.

## 4. Commands

| Command | Parameters | Result | Notes |
|---|---|---|---|
| `ping` | – | `t` | |
| `info` | – | the hello payload | |
| `stop` | – | – | E-stop: stops motors, ends manual control, cancels the active plan (`plan.cancelled`, reason `stop`). Emits `motion.stopped`. Always succeeds. |
| `motor.write` | `left`, `right` ∈ [-1, 1] | – | Raw open-loop power. Manual control (§5). |
| `drive.velocity` | `v` (m/s), `w` (rad/s) | `v`, `w` as applied | Closed loop; clamped to the current speed limit. Manual control (§5). |
| `speed.set` | `linear` (m/s) and/or `angular` (rad/s), > 0 | `linear`, `angular` | Speed **limits** used by moves and velocity control; clamped to `limits.max_*`. Reset to safe defaults on boot. |
| `speed.get` | – | `linear`, `angular` | |
| `encoder.get` | – | `left`, `right`: `{ticks, speed}` | `speed` in m/s at the wheel surface. |
| `odom.get` | – | `x`, `y`, `yaw`, `v`, `w` | |
| `odom.reset` | – | `x`, `y`, `yaw` (all 0) | |
| `light.set` | `name` (from capabilities), `level` ∈ [0, 1] | `name`, `level` | |
| `light.get` | – | `lights`: `{name: level}` | |
| `status.set` | `name`, `pattern` ∈ off, on, blink, blink_fast, pulse, optional `color` `[r, g, b]` (0-255) | `name`, `pattern` (+ `color` for colour LEDs) | The bot animates patterns itself. `color` only for LEDs listed in `capabilities.color_leds` (else `invalid_param`); without it a colour LED keeps its last colour. |
| `wifi.status` | – | `mode` (`ap`/`sta`), `ssid`, `ip`, `rssi` | |
| `wifi.set` | `ssid`, `password`, optional `ip`, `gateway`, `netmask` | `applied_on_reboot` | Static IP when `ip` is given. |
| `wifi.reset_ap` | – | `applied_on_reboot` | Back to direct (AP) mode. |
| `camera.get` | – | `preset`, `resolution`, `fps`, `quality`, `streaming` | §7. `not_supported` without a camera. |
| `camera.set` | `preset` and/or `resolution`, `fps`, `quality` | as `camera.get` | §7. |
| `module.list` | – | `modules` | Same list as `hello.modules` (§8). |
| `module.read` | `module_id` | `module_id`, `module_type`, `values` | Fresh values. |
| `module.call` | `module_id`, `action`, `args` (object) | `module_id`, `action`, `result` | Runs a module action. |
| `sub` | `topics` (list), `rate_hz` (default 10, max 50) | `topics` (all subscribed) | Per connection. Module topics are `module.<id>`. |
| `unsub` | `topics` | `topics` | |
| `plan.*` | see §6 | | |

Simulator-only commands use the `sim.` prefix (`sim.reboot`, `sim.fault`, `sim.truth`,
`sim.drop_connections`, `sim.attach`, `sim.detach`). Real bots answer them with `unknown_command`.

**Lights and LEDs on movebot-r1.** `light_left` / `light_right` are the headlights
(brightness 0-1). `status` is the controller board's own LED (one colour) and `rgb` is the
RGB status LED; both show patterns, and `rgb` also takes a colour. After boot `status` is `on`
and `rgb` is `off` (colour white). The bot may use them itself only as documented here
(the privacy indicator is a separate LED).

## 5. Manual control and arbitration

* `motor.write` and `drive.velocity` **expire after `limits.command_timeout_ms`** unless
  repeated. On expiry the bot stops and emits `motion.stopped` (reason `command_timeout`).
  This is the motor watchdog: a crashed program, or one whose link dropped, cannot leave the
  bot driving. Clients that want continuous motion re-send the command (the reference
  library sends it every `command_timeout_ms / 3`).
* If the connection that issued the current manual command closes, the bot stops at once
  (`motion.stopped`, reason `disconnect`).
* While a plan is **moving** (a step is running or queued in a `running` plan), manual
  commands fail with `busy`. A paused, finished or idle plan does not block them.
* When a plan step starts, it takes over from manual control.
* `stop` always wins.

## 6. Plans: numbered, queued, resumable moves

A plan is a list of steps the bot executes on its own, so motion does not depend on the
link. Every relative move (drive 0.5 m, turn 90°, ...) is a plan step. A client that wants a
single move sends a one-step plan (or appends a step to an open plan it already has).

### 6.1 Steps

Every step has `seq` (integer ≥ 1) and `op`; optional `timeout_ms`.

| `op` | Fields | Meaning |
|---|---|---|
| `drive` | `dist` (m, ±), optional `speed` (m/s) | Straight line, heading held. |
| `turn` | `yaw` (rad, + = left), optional `speed` (rad/s) | Relative turn on the spot. |
| `turn_to` | `yaw` (rad) | Turn on the spot to an absolute odometry heading. |
| `arc` | `radius` (m, ≥ 0), `angle` (rad, + = left), optional `speed` (m/s) | Drive forward along a circle. `radius` 0 = turn. |
| `drive_for` | `v` (m/s), `w` (rad/s), `ms` | Velocity for a fixed time. |
| `wait` | `ms` | Stand still. |
| `light` | `name`, `level` | Instant. |
| `status` | `name`, `pattern`, optional `color` | Instant. Same rules as `status.set`. |
| `speed` | `linear` and/or `angular` | Instant. Changes the speed limit (like `speed.set`). |
| `marker` | `label` (≤ 64 chars) | Instant. Emits `plan.marker`. |
| `stop` | – | Instant. Brief stop between steps. |

Speeds in steps are clamped to the current speed limit. Instant steps complete immediately and
the next step starts in the same control cycle.

### 6.2 Commands

| Command | Parameters | Notes |
|---|---|---|
| `plan.load` | `plan_id` (≤ 32 chars), `steps`, `autostart`, `end`, `on_disconnect`, `replace` | Creates the plan (state `loaded`, or `running` with `autostart`). If a plan with the **same** `plan_id` exists, this behaves like `plan.append` (retries are safe). If a **different** plan is active (`loaded`, `running`, `paused`): `busy`, unless `replace: true`, which cancels it first. |
| `plan.append` | `plan_id`, `steps`, `end` | Adds steps. |
| `plan.start` / `plan.resume` | `plan_id` | `loaded`/`paused` → `running`. No-op if already running. |
| `plan.pause` | `plan_id` | Takes effect **at the end of the current step** (immediately if none is running), then emits `plan.paused`. |
| `plan.cancel` | `plan_id` | Stops immediately. The running step is recorded as `cancelled`; queued steps are dropped. No-op on a finished plan. |
| `plan.status` | optional `plan_id` | See below. Without `plan_id`: the current plan, or `{"plan_id":null,"state":"none"}`. |
| `plan.results` | `plan_id`, `from_seq` (default 1) | `results`: outcomes with `seq ≥ from_seq` still in the ring buffer; `oldest_seq`. |

Every successful `plan.*` response (except `plan.results`) is a **status**:

```json
{"plan_id":"a91f0007","state":"running","next_seq":6,"running_seq":2,"done_seq":1,"queue_free":29,"end":true,"boot_id":"c3d29e01"}
```

`next_seq` is the next step the bot expects. `done_seq` is the last step that finished (in any
way). `queue_free` is free space in the step queue (capacity `limits.plan_queue`; the running
step does not count). `end` is true once the client said no more steps will come.

Any `plan.*` command naming a plan makes the sending connection its **owner** (§6.5).
A `plan_id` that is not the bot's current plan gives `unknown_plan`.

### 6.3 Numbering rules: ordered and exactly-once

For each step in a `plan.load`/`plan.append`, in order:

1. `seq < next_seq` → **duplicate**: ignored (it was accepted before; it will never run twice).
2. `seq == next_seq` → accepted if the queue has room (`next_seq` += 1); if the queue is full,
   processing stops and the rest are not accepted.
3. `seq > next_seq` → **gap**: processing stops. If no step of this request was accepted the
   request fails with `gap` and `error.next_seq`; otherwise it succeeds and the returned
   `next_seq` tells the client where to continue.

`end: true` takes effect only if every step in the request was accepted (or was a duplicate).
The client compares the returned `next_seq` with what it sent and re-sends from there. So
re-sending, re-ordering or partially delivering steps can never skip a step or run one twice.

A step is started at most once. When it finishes, its outcome is appended to a ring buffer of
`limits.results_buffer` entries:

```json
{"seq":3,"op":"drive","result":"ok","pose":{"x":0.5,"y":0.3,"yaw":1.57},"t_start":5120,"t_end":7480}
```

`result` is `ok`, `failed` (with `reason`) or `cancelled` (with `reason`).

### 6.4 Execution and plan states

`loaded → running ⇄ paused → done | failed | cancelled`

* In `running`, the bot starts the next queued step as soon as the previous one finishes.
  With an empty queue and `end` not yet set, it stands still and waits for more steps.
  With an empty queue and `end` set, the plan is `done` (`plan.done`).
* A step fails with reason `timeout` (default limit: twice the expected duration plus 2 s),
  `stalled` (motion commanded but no encoder tick for 0.5 s), `low_battery`, or
  `max_duration` (plan running longer than `limits.plan_max_duration_ms`). A failure stops the
  motors, drops the queue, and the plan becomes `failed` (`plan.failed`).
* Plans live in RAM. After a reboot (new `boot_id`) there is no plan; clients must not resume.

### 6.5 Disconnect policy

`on_disconnect` (set by `plan.load`, default `continue`) applies when the owner's connection
closes without cancelling:

| Policy | Behaviour |
|---|---|
| `continue` | Keep executing; the client resumes supervision after reconnecting. |
| `finish_step` | Finish the running step, then cancel (reason `disconnect`). |
| `stop` | Cancel immediately (reason `disconnect`). |

An open plan (no `end` yet) whose owner disconnected under `continue` and that has nothing
left to run (no running step, empty queue) MUST NOT block other clients: a `plan.load` of a
different plan cancels it (reason `replaced`) instead of failing with `busy`. If the owner
reconnects first and sends any command for the plan, it owns it again.

Speed limits, step timeouts, stall detection and the maximum plan duration apply whatever the
policy. A deliberate stop (e.g. the app's Stop button) sends `plan.cancel` or `stop`; the
policy only covers unplanned link loss.

### 6.6 Resuming after a disconnect (client behaviour)

1. Reconnect and read `hello`. If `boot_id` changed, the plan is gone: report it to the user.
2. `plan.status` → `next_seq`, `done_seq`, `state`.
3. `plan.results` from the first step whose outcome the client has not seen.
4. Re-send steps from `next_seq` on, as `queue_free` allows.

## 7. Camera

The camera streams MJPEG over HTTP on `hello.capabilities.camera.stream_port`, path
`stream_path` (`/stream`). `capture_path` (`/capture`) returns a single JPEG.

```
GET /stream HTTP/1.1

HTTP/1.1 200 OK
Content-Type: multipart/x-mixed-replace;boundary=movebotframe

--movebotframe
Content-Type: image/jpeg
Content-Length: 10342
X-Timestamp: 51234          ← ms since boot, when the image was captured
X-Frame: 815                ← frame number, increases by 1 per captured frame
X-Pose: 0.4981,0.0012,0.0103 ← odometry x,y,yaw at capture time

<JPEG bytes>
```

* Every part MUST carry `Content-Length`, `X-Timestamp`, `X-Frame` and `X-Pose`, so programs
  can reason about latency and about where the bot was when it took the picture.
* Settings: `camera.set` with a `preset`, and/or custom `resolution` (one of
  `capabilities.camera.resolutions`), `fps` (1–`max_fps`, an upper bound) and `quality`
  (1–100, higher is better; the firmware maps it to the sensor's scale). A preset is applied
  first and explicit fields override it; custom fields set `preset` to `null`.
  Presets every bot MUST offer:

  | Preset | Resolution | fps | Use |
  |---|---|---|---|
  | `fast` (default after boot) | 320×240 | 25 | vision control loops |
  | `balanced` | 640×480 | 15 | viewing, ML models |
  | `detail` | 1280×720 | 8 | photos, inspection |

* After a change, frames at the old size may still arrive briefly; clients check the JPEG
  size.
* **Privacy.** While at least one client receives the stream, the privacy indicator named
  in `capabilities.camera.privacy_indicator` MUST be lit (`dedicated` = its own LED; otherwise
  the name of a status LED). `camera.streaming` events report changes.
* A bot MAY serve only one stream client at a time; a host-side relay (§11) then shares it.

## 8. Modules

Add-on modules (sensors, actuators) are abstracted by the firmware; the protocol never
exposes buses or pins. Each attached module is described in `hello.modules`:

```json
{"id":"front_distance","type":"distance","version":1,"values":["distance","valid"],
 "actions":["set_range"],"info":{"min_range":0.02,"max_range":2.0}}
```

* `id` names this instance (`^[a-z][a-z0-9_]{0,31}$`); `type` and `version` refer to a
  **module type descriptor** in `protocol/modules/<type>.json`, which defines the values
  (with units), actions, info fields and events. Adding a module type needs a descriptor
  and a firmware driver, not new protocol commands.
* `module.read{module_id}` returns `values` with exactly the names listed in `values`.
* `module.call{module_id, action, args}` runs an action; unknown actions give
  `invalid_param`, unknown modules `unknown_module`.
* Telemetry topic `module.<id>` streams `{"module_id": ..., "values": {...}}`.
* Hot-plug: `module.added` (with the full `module` descriptor) and `module.removed`
  (`module_id`). Modules can raise their own events as `module.event{module_id, event, data}`.

## 9. Events

| `evt` | Fields |
|---|---|
| `plan.step_started` | `plan_id`, `seq`, `op`, `queue_free` |
| `plan.step_done` | `plan_id`, `queue_free`, plus the outcome fields (`seq`, `op`, `result`, `pose`, `t_start`, `t_end`, `reason`) |
| `plan.marker` | `plan_id`, `seq`, `label` |
| `plan.paused` | `plan_id`, `done_seq` |
| `plan.done` | `plan_id`, `done_seq` |
| `plan.failed` | `plan_id`, `seq` (or null), `reason` |
| `plan.cancelled` | `plan_id`, `seq` (running step, or null), `reason` (`cancelled`, `stop`, `disconnect`) |
| `motion.stopped` | `reason`: `stop`, `command_timeout`, `disconnect` |
| `camera.streaming` | `active` (privacy indicator on/off) |
| `module.added` | `module` (descriptor) |
| `module.removed` | `module_id` |
| `module.event` | `module_id`, `event`, `data` (as the module's descriptor defines) |

Every event has `t`. Events are hints: a client that may have missed some (e.g. while
disconnected) catches up with `plan.status` and `plan.results`.

## 10. Telemetry topics

| Topic | Fields |
|---|---|
| `odom` | `x`, `y`, `yaw`, `v`, `w` |
| `encoders` | `left`, `right`: `{ticks, speed}` |
| `power` | `percent`, `voltage` |
| `net` | `rssi` (dBm) |
| `status` | `mode` (`idle`, `raw`, `velocity`, `plan`), `plan_state` (or null), `lights`, `status_leds`, `status_colors` (`{name: [r, g, b]}` for colour LEDs), `camera_streaming` |
| `module.<id>` | `module_id`, `values` |

## 11. Relays

A host-side relay (the MoveBot app, `movebot relay`, or the ROS node) owns the single
connection to the bot and serves **this same protocol** to programs on the host, so to them it
is indistinguishable from a bot. The conformance suite is run through the reference relay
(`pytest protocol/conformance --via-relay`) to check exactly that. A relay:

* MUST send the bot's `hello`, with `limits.max_clients` set to its own limit, the camera
  `stream_port` replaced by its own, the current module list, and a `relay` object
  (`version`, `upstream`).
* MUST keep request ids unique towards the bot, and MUST replay its stored response to a
  repeated local id (§3.2).
* MUST forward every event to every local client, and telemetry to each subscribed client at
  that client's own rate (it subscribes upstream at the highest requested rate).
* MUST apply the disconnect rules to its local clients: when the client that issued the
  current manual command disconnects, it stops the motion and emits `motion.stopped`
  (`disconnect`); when a plan's owner disconnects, it applies the plan's `on_disconnect`
  policy (`stop` → `plan.cancel`; `finish_step` → `plan.pause`, then `plan.cancel` once
  paused; `continue` → `plan.append` with no steps and `end: true`, because a local client
  that disconnects from the relay has ended and will not add more steps).
* MUST close its local connections with close code **1012** when the bot restarted (new
  `boot_id`), so clients notice, and MUST NOT accept local connections while it cannot reach
  the bot (it waits up to 10 s, then refuses with 1013).
* SHOULD open the bot's camera stream only while a local client is watching and share it
  between all local viewers.

## 12. Open items for v0.2

mDNS service and TXT record · signed OTA (`ota.*`) ·
optional pairing token · `repeat` step · step blending · binary encoding.
