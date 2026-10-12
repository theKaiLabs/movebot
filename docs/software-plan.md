# MoveBot – Software Development Plan (Revision 1)

Status: draft v0.6 · Scope: everything except the ESP32 firmware · Last updated: 2026-10-12

"Studio" below is a working name for the installable desktop app that students and teachers use.

### Confirmed decisions (v0.6)
| Topic | Decision |
|---|---|
| Audience | **High-school students and their teachers** – primarily a learning product |
| Team | Software (library, app, ROS node, lessons, and later the firmware) is built by **us**. Hardware is designed by someone else. Firmware work starts when the hardware arrives |
| Bot hardware | **ESP32-S3 with camera** (or similar), PSRAM assumed. More sensors/modules will be added over time (e.g. on UART); the firmware abstracts them and the protocol/library must make new modules easy to add (§4.6) |
| Camera | Configurable presets plus custom resolution/fps/quality (§4.7) |
| Platforms | No fixed support tiers: every lesson/example declares the OS and hardware it supports |
| Bots per host | **One bot at a time.** No multi-bot support in rev 1 (keeps the API, UI and docs simple) |
| Hardware access | **No GPIO/pin access at all.** The hardware is fixed; students program behaviour, not wiring. Lights and status LEDs have dedicated commands |
| Python | Required and managed by us; the host (laptop / PC / RPi) runs Studio and user scripts |
| Hub | **No separate hub.** The library acts as the hub (connection-owner/relay model); on ROS setups the ROS node is the hub (§2.2) |
| Editor | **Text-based Python editor only** (no block-based coding), and it is **free to tinker**: everything in the workspace is editable |
| App modes | **Three modes**: **Code** (IDE), **Apps** (ready-made GUIs for every example: buttons, outputs, video), **Learn** (lessons as rendered Markdown that also act as the documentation) – §7 |
| Shipped content | The installer **seeds the workspace with our examples and lessons**; teachers can run them as-is or edit them. Every example comes with a built-in GUI and a pre-written lesson page (§7.2b, §10) |
| Source | **Installable app and ESP firmware are closed source; GitHub is used only as the release system** (public releases repo, private source repos – §3.1). Protocol, library, ROS node, examples, lessons and docs are open (confirmed) |
| Lessons | Written by us **and** teachers. Teachers write them in the installed workspace with the app's editor; a separate public **community examples** repo collects shared ones (§10). Flagship examples: blue-ball follow/hit, gesture control with an ML model |
| Name | `movebot` is final |

---

## 1. Goals and non-goals

**Goal.** A student or teacher can unbox MoveBot, connect it, drive it, see its camera, write their first Python program, and later bridge it to ROS 2. This should take under 15 minutes, with no terminal and no Python setup, on a typical school laptop.

**In scope (this plan):** wire protocol, Python library, simulator, host app ("Studio"), UI kit, ROS 2 node, docs, CI/release.

**Out of scope (separate plan):** ESP32 firmware, hardware design. We only produce the *spec and test suite* the firmware must satisfy.

**Non-goals for rev 1:** cloud services, accounts, multi-bot / multi-user classroom management, SLAM/navigation, any user access to hardware pins, block-based (Scratch-like) coding (decided: text only), user access to firmware source.

---

## 2. Key strategic decisions

These shape everything else. Each should become a short ADR (`docs/adr/NNNN-*.md`) in Phase 0.

### 2.1 Protocol first, simulator second, hardware last
The firmware doesn't exist yet, so the **protocol spec is the contract**. The Python library, Studio, and ROS node are all built against a **software simulator of the bot** that speaks the same protocol. When firmware arrives, we run the same conformance test suite against it. Benefits:
- Software work is never blocked by hardware.
- The firmware team gets an executable spec, not a PDF.
- Beginners can use MoveBot *without a robot* (classroom with 1 robot per 10 students, home trial, CI).

### 2.2 The library is the hub: "connection owner" model (no separate hub component)
There is **no standalone hub**. An ESP32-CAM tolerates very few simultaneous clients (and its video stream copes badly with more than one viewer), so the rule is: **exactly one process on the host owns the connection to the bot**; anything else that wants the bot goes through that owner. Who the owner is depends on the situation:

| Situation | Connection owner | Others |
|---|---|---|
| A student runs a script alone (terminal, Thonny, anywhere) | the script's own `Bot()` – direct to the bot, no extra moving parts | – |
| Script run from Studio, with Studio's live preview | **Studio**, using the library's built-in relay mode | the script's `Bot()` automatically connects to Studio's local relay (Studio sets `MOVEBOT_URL`) |
| ROS 2 in use | **the ROS node** (on the PC/RPi) – it is the hub of the ROS world | other code uses ROS topics/services; optionally the node also enables the library relay |
| No robot | the simulator, same protocol | same as above |

How it works:
- The relay is a **feature of the `movebot` library** (`movebot.Relay`, a few hundred lines): it speaks the **identical protocol** as the bot, so the library doesn't care whether it talks to a bot, a relay, or the simulator (`Bot("ws://192.168.4.1")`, `Bot("ws://localhost:8765")`, `Bot("sim")`).
- `Bot()` with no arguments resolves in order: `MOVEBOT_URL` env var → local relay on localhost → discovery (192.168.4.1, mDNS, …). Students never type an address.
- The owner fans out video/telemetry, allows one controller at a time, and **stops the motors when the controlling client disconnects or dies** (plus the firmware's own watchdog as the real safety net).
- It can record/replay a session (debugging, classroom demos).
- A second program trying to connect directly to a bot that already has an owner gets a clear message ("MoveBot is already in use by Studio – run your script from Studio or close it").

### 2.3 Studio = local web app, not a native GUI
FastAPI backend (Python) + web frontend, launched as `movebot studio` (opens the browser) and later wrapped in a desktop shell/installer.
- One codebase for Windows, macOS, Linux, **and headless Raspberry Pi** (use it from another device's browser).
- Monaco (VS Code's editor) and xterm.js give a good IDE almost for free; MJPEG video is trivial in a browser.
- The app has **three modes sharing one connection and one workspace** – *Code*, *Apps*, *Learn* – with a split view (e.g. lesson on the left, code on the right). See §7.
- Python for user scripts runs in a **managed interpreter + venv** that Studio installs (e.g. via `uv` / python-build-standalone) so beginners never hit "which Python?" problems. This is the single biggest source of beginner pain, so it gets its own work item.
- Because Python on the host is a given, there is no browser-only (Pyodide) variant in rev 1. Chromebooks are supported only through their Linux (Crostini) container.
- Alternative considered: PySide6 (all-Python, but embedded terminal/editor/video are more work and look dated). Alternative to *reuse*: a Thonny plugin or VS Code extension instead of building an IDE – cheaper, but we lose the connection panel/demo mode/one-product feel. Revisit if Phase 3 slips.

### 2.4 UI kit: our own API on a small server of our own
Beginner API (`button`, `video`, `slider`, `joystick`, …) is ours. *Update 2026-10-12:* instead of NiceGUI underneath, it runs on a small server built on the `websockets` library we already use, with one static page (no build step, no CDN): no extra dependencies, student callbacks run on worker threads (blocking robot calls are fine), and source mapping/embedding/video flow control are built in. See ADR 0005. Gradio is poor for live video and continuous control; Streamlit reruns the whole script on interaction (confusing for beginners).

### 2.5 School requirements that drive design
- **Direct (AP) mode is a first-class operating mode, not just a setup step.** School Wi-Fi often has client isolation, blocks mDNS, or needs a login. The most reliable classroom path is: laptop joins the bot's own `MoveBot-XXXX` network and talks to 192.168.4.1. The bot then has no internet, so Studio, docs, and examples must work fully **offline**. "Network mode" (bot joins an existing Wi-Fi) is the second option for home use.
- **No admin rights.** School-managed laptops often forbid installers. Provide a per-user install / portable build; no system-wide changes, no drivers needed.
- **Low-end machines.** Studio must run acceptably on an old 4 GB laptop and a Raspberry Pi (keep the UI light, video decode in the browser, optional OpenCV).
- **Privacy.** A camera on a robot in a classroom: video never leaves the host, no accounts, no telemetry by default, and the bot shows a **status LED when the camera is streaming** (protocol event + required capability).
- **Safe for small hands and desks.** Conservative default speed limits, a visible e-stop, auto-stop on connection loss, friendly error messages written for a 12-year-old.
- **Teachers are first-class users**: a teacher guide, lesson plans, a "reset the bot to a known state" button, and a 5-minute pre-class checklist (`movebot doctor`).

### 2.6 Units and conventions (decide once, never change)
- Wire protocol: SI units, radians, **ROS REP-103 frame** (x forward, y left, yaw counter-clockwise positive), odom frame origin = power-on or last `odom.reset`.
- Beginner Python API: friendly units (`turn(90)` in degrees, `forward(0.5)` in metres, `speed` 0–100 %); every function documents its unit, and `_rad` variants exist.
- Robot geometry (wheel diameter, track width, ticks/rev, max speeds) is reported by the bot in its hello message – the simulator, ROS node, and library read it rather than hard-coding.

---

## 3. System architecture

```
┌─────────────────────────── host (laptop / PC / RPi) ───────────────────────────┐
│                                                                                │
│  Studio frontend (browser)   ←HTTP/WS→   Studio backend (FastAPI)              │
│   • connection panel                      • movebot lib (owner + Relay mode)   │
│   • Code mode (Monaco, files, console)    • discovery + provisioning           │
│   • Apps mode (example GUIs)              • script runner (subprocess, venv)   │
│   • Learn mode (lessons = docs)           • workspace seeding + lesson renderer│
│                                                                                │
│  User script / demo (python)  ── movebot lib ──► Studio relay *or* bot directly│
│  ROS 2 node (movebot_ros)     ── movebot lib ──► bot directly (ROS node = hub) │
│  Vision / ML scripts          ── movebot lib ──► frames in, drive commands out │
└────────────────────────────────────────────────────────────────────────────────┘
                     │  Wi-Fi: ws (control/telemetry) + http mjpeg (video)
                     ▼
              MoveBot (ESP32-CAM)   — or —   movebot simulator (same protocol)
```

### 3.1 Repositories, licensing and GitHub as the release system
The installable app and the firmware are **closed source**; GitHub is used **only as the release system** for them. Everything students and teachers *write against* (protocol, library, examples, lessons) is assumed **open**. That gives these repos:

| Repo | Visibility | Contains |
|---|---|---|
| `movebot` | public | protocol, library, relay, ROS package, **examples, lessons, docs** (incl. the UI kit reference) |
| `movebot-studio` | private | app backend + frontend, **simulator and UI kit** (ADR 0006), installer/packaging, signing config; includes `movebot` as a git submodule |
| `movebot-firmware` | private | ESP32 code, signing, firmware builds |
| `movebot-community` | public | examples and lessons shared by teachers and students (same example-pack format, lighter review than the official content) |
| `movebot-releases` | **public, no source** | only release assets (installers, offline bundle, signed firmware images), changelogs, the update manifest (`latest.json`), and the public issue tracker/discussions for support |

Why a separate public releases repo: GitHub release downloads from a *private* repo need authentication, so end users could not download installers from the private repos. CI in the private repos publishes into `movebot-releases`.

Release-system details to plan for:
- **In-app updater** reads `latest.json` from `movebot-releases` (raw file / Pages / release asset). Keep checks infrequent and cached: unauthenticated GitHub API calls are rate-limited **per IP (60/hour)** and a whole school shares one IP behind NAT. A static file avoids the API limit entirely. Update manifests and installers are **signed**; the app verifies before installing.
- Schools must allow-list `github.com` and `objects.githubusercontent.com` (or use the offline installer + firmware file downloaded by IT). Updates are always optional and never required to run.
- Release assets are limited to 2 GiB each, comfortable for an offline bundle even with ML wheels.
- Channels: stable and beta (GitHub *pre-release* flag), so pilot classes get betas.
- Private-repo Actions minutes are billed and macOS/Windows runners cost more (minute multipliers) – budget for it, or use self-hosted runners for the heavy builds.
- Firmware images ship **inside the app bundle** (so no internet is needed to flash) and as separate release assets (so firmware can be updated without a new app version).

Repos in detail – first the open one:

**`movebot` (public, e.g. Apache-2.0 / MIT)** – what teachers, students and the community can read, extend and contribute to:
```
movebot/
├─ protocol/            spec (markdown) + JSON Schemas + test vectors + conformance suite
├─ packages/
│  ├─ movebot/          core Python lib: protocol codec, transport, discovery, Bot API, Relay, CLI
│  │                    extras: movebot[vision] (OpenCV), movebot[ml] (gesture/ML examples); movebot.ui and
│  │                    Bot("sim") load the app's implementation (ADR 0006)
│  └─ movebot-ros/      ROS 2 package (ament_python, pure rclpy – no compile step)
├─ content/             examples + lessons (one folder each, see §10), shipped in the installer
│                       and seeded into the user's workspace
├─ docs/                mkdocs-material site (built from the same Markdown as the in-app lessons) + ADRs
└─ tools/ , .github/
```
`movebot-studio` and `movebot-firmware` hold the closed code, installers, signing and release pipelines (see the table above).

Consequences of closing Studio and firmware:
- The **protocol spec stays public**: it is what makes the open library, the ROS node, and third-party/teacher tools possible. Publishing it costs nothing the firmware needs to hide.
- Firmware reaches users **only through Studio** (signed OTA/flash tool); students never get firmware source or build it. Signature verification on the bot is required so modified images cannot be installed casually.
- Studio ships as installers (per-user/portable) from the public `movebot-releases` repo, **not** as a public PyPI package. (Be realistic: Python and JS shipped inside an installer can be unpacked. Obfuscation/Nuitka raises effort but is not protection – so don't put secrets in Studio. The real moat is the firmware signing key and the lesson/brand ecosystem.)
- **Licence hygiene for a closed Studio**: no GPL/AGPL/LGPL-static dependencies in it (e.g. avoid PyQt; use permissive components – Monaco, xterm.js, FastAPI, NiceGUI are MIT/BSD-style). Same care for ML examples: **Ultralytics YOLO is AGPL** – use MediaPipe (Apache-2.0) / ONNX Runtime (MIT) or classic OpenCV in anything we bundle.
- Public repo CI must be able to test the library without Studio or firmware; Studio's CI pulls the library as a dependency like any consumer (eats our own dog food).

Python workspace managed by **uv**; ROS package built with colcon in a Docker CI job. PyPI names `movebot` and `movebot-ros` (public) are currently free (checked 2026-10-11); `movebot-studio` was also free, reserve it defensively even if unused. Check the same names on the ROS index/GitHub org before announcing.

---

## 4. Workstream A – Protocol (the contract)

### 4.1 Transport
| Channel | Tech | Why |
|---|---|---|
| Control + telemetry | WebSocket, JSON text frames | Human-readable (great for teaching/debugging), works from browsers. Binary (CBOR/MessagePack) can be added later via negotiation. |
| Video | MJPEG over HTTP (`multipart/x-mixed-replace`, separate port/path) | Native ESP32-CAM capability; OpenCV, browsers, and ROS `CompressedImage` consume it directly with no re-encode. |
| Discovery | mDNS (`movebot-<id>.local`, service `_movebot._tcp`) + UDP beacon fallback; MAC in hello for the "find by MAC" feature, ARP/subnet scan as last resort | mDNS is far more reliable than IP scanning; scanning stays as a fallback. |
| Connection modes | **Direct**: bot AP (`MoveBot-XXXX`, fixed IP 192.168.4.1), laptop joins it. **Network**: bot joins existing Wi-Fi, found via mDNS. Same WS endpoint in both. | Direct mode is the reliable classroom default (no router, no client isolation, no mDNS). |

### 4.2 Message model
Every message has `type`, and requests have an `id`.
- `req` → `res` (`ok` or `error{code,msg}`) for immediate commands (set/get).
- **Relative motion lives only in numbered plan steps** (§4.5). There are no separate `move.*` commands: the library sends a single move as a step appended to an open plan it owns (ADR 0004). Steps have a lifecycle: `accepted` → `started` → `done | failed | cancelled`, which is what makes blocking *and* non-blocking library calls possible, and it means the firmware has **one** motion-sequencing mechanism instead of two.
- **All other wire commands are absolute and idempotent** (`light.set level=1`, never "toggle"; `speed.set 0.3`), so a retried request after a timeout is harmless. The library implements toggles by reading state. The bot also remembers the responses to its last N request ids and replays them for a duplicate id.
- `sub` / `unsub` for telemetry topics with a requested rate; `evt` for async events (button, low battery, wifi lost, fault).
- `hello` on connect: protocol version, firmware version, bot id/MAC, geometry, **capabilities** (which lights/LEDs/topics exist). Library refuses incompatible major versions with a friendly message.
- Heartbeat/ping and a **motor watchdog**: for manual and streaming control (`motor.write`, `drive.velocity`), if no command or heartbeat arrives within N ms the bot stops. (Non-negotiable for safety and for dead scripts.) A running **plan** follows its own `on_disconnect` policy instead (§4.5), since surviving link loss is its purpose.

### 4.3 Command set (mapping your original list)

| Your item | Protocol commands | Notes |
|---|---|---|
| set wifi / reset to AP | `wifi.set{ssid,pass,ip?}`, `wifi.reset_ap`, `wifi.status` | Static IP is a field of `wifi.set`. |
| set speed | `speed.set{linear_max, angular_max}` | Defined as the **limit** used by velocity/move modes. |
| read encoder | `encoder.get`; topic `encoders` | ticks + wheel velocity. |
| write motors | `motor.write{left,right}` | **Raw open-loop** −1..1. |
| (new) velocity mode | `drive.velocity{v, w}` | Closed-loop; this is what ROS `cmd_vel` maps to. |
| move yaw / Δyaw, x / Δx | plan steps `drive{dist}`, `turn{yaw}`, `turn_to{yaw}` (a single move is a one-step plan) | `go_to{x,y}` is composed on the host (turn→drive) in rev 1. Absolute-`x` alone is ambiguous on a differential drive. |
| (new) abstracted moves | plan steps `drive`, `turn`, `arc{radius,angle}`, `drive_for{v,w,ms}`, `wait{ms}`, `stop`; library sugar `forward/back/left/right/u_turn/spin` | Left/right/u-turn are library names for `turn` (±90°, 180°); the wire stays small. |
| (new) route / queued moves | `plan.load`, `plan.append`, `plan.start`, `plan.pause`, `plan.resume`, `plan.cancel`, `plan.status`, `plan.results` + events | Upload N steps once; the bot runs them without the PC in the loop. Ordered, exactly-once, resumable (§4.5). |
| stream info | `sub{topics:[...], rate}`; topics: `odom`, `encoders`, `status`, `net` (RSSI), `power` | Only whitelisted topics. |
| set lights | `light.set{name, level}` | Logical names from capabilities (`light_left`, …), not pins. |
| set status LEDs | `status.set{name, pattern}` | Patterns (solid/blink/pulse) so the bot animates locally. |
| pin set/value | **Dropped** (decision: no GPIO access) | Lights/LEDs have dedicated commands; the protocol never exposes pin numbers. |
| (new) | `stop` (e-stop), `odom.reset`, `info`, `ping`, `ota.*` (flash hook), `log.sub` | |

### 4.4 Deliverables
1. `protocol/SPEC.md` – human-readable, versioned (`MAJOR.MINOR`).
2. JSON Schemas per message – single source for codec validation, docs generation, and Studio typing.
3. Golden **test vectors** (request/response pairs).
4. **Conformance suite** (`pytest`) runnable against any endpoint (`--target ws://…`): first the simulator, later real firmware, later HIL in CI. This is the hand-off to the firmware team. It includes the plan tests of §4.5 (duplicates, gaps, disconnects, reboot).

### 4.5 Planned routes: queued, numbered, resumable moves

**Why.** Wi-Fi drops and jitters; a script that must feed the bot every 50 ms makes the robot only as reliable as the link, and every step costs a round trip. Instead the host can send a whole route, the bot executes it locally (using its own encoder control), and the host only supervises. Benefits: robust to interruptions, smoother and faster motion (no stop-and-wait between steps), less traffic, and the same mechanism powers "run this route" lessons. Closed-loop *reactive* behaviour (follow the ball) still uses streaming `drive.velocity` – the two are complementary.

**Message example** (wire units: metres, radians):
```json
→ {"type":"req","id":41,"cmd":"plan.load","plan_id":"a91f0007","autostart":true,"on_disconnect":"continue",
   "steps":[
     {"seq":1,"op":"drive","dist":0.5},
     {"seq":2,"op":"turn","yaw":1.5708},
     {"seq":3,"op":"wait","ms":1000},
     {"seq":4,"op":"light","name":"light_left","level":1},
     {"seq":5,"op":"drive","dist":0.5,"speed":0.15}]}
← {"type":"res","id":41,"ok":true,"plan_id":"a91f0007","next_seq":6,"queue_free":27,"boot_id":"c3d2"}
← {"type":"evt","evt":"plan.step_done","plan_id":"a91f0007","seq":1,"result":"ok","pose":{"x":0.49,"y":0.00,"yaw":0.01}}
```

**Ordering and "never twice" – the numbering rules** (this is the part the conformance suite pins down):
1. A plan has a client-generated unique `plan_id`; steps carry a consecutive `seq` starting at 1. The bot tracks `next_seq` (next step it expects) and `done_seq` (last finished).
2. Step with `seq == next_seq` → accepted. `seq < next_seq` → **duplicate**: ignored, answered `ok` with the current `next_seq` (so blind retries are safe). `seq > next_seq` → rejected with `gap` and the expected `next_seq`, so the sender resends from there. Out-of-order or repeated delivery can therefore never run a move twice or skip one.
3. A step is **started at most once**; `done_seq` advances atomically with completion. The result of the last K steps (including the pose reached) is kept in a ring buffer and available via `plan.results{from_seq}`.
4. After a disconnect the library reconnects, calls `plan.status` (`state, next_seq, running_seq, done_seq, queue_free, boot_id`) and resumes by sending only steps from `next_seq`. A step that was running during the outage simply finished on the bot; the library learns its result from `plan.results`.
5. `boot_id` changes on every bot reboot. Plans live in RAM only, so a changed `boot_id` means the plan is gone; the library raises a clear `PlanLost` instead of guessing.
6. One active plan at a time in rev 1. Loading another plan id while one is active is rejected (`busy`) unless `replace:true` (which cancels the old one).

**Flow control.** `hello.limits` advertises `plan_queue` (e.g. 32 steps, a firmware RAM decision). Every response carries `queue_free`; the library streams longer routes with `plan.append` as space frees, and execution can start before the upload finishes.

**Step set (rev 1, kept deliberately small):** `drive{dist}`, `turn{yaw}`, `turn_to{yaw}`, `arc{radius,angle}`, `drive_for{v,w,ms}`, `wait{ms}`, `light{name,level}`, `status{name,pattern}`, `speed{linear,angular}` (limit change mid-route), `marker{label}` (emits an event when reached – "waypoint 3"), `stop`. Optional per-step `speed`, `timeout_ms`. Stretch (firmware cost, decide with the firmware owner): `repeat{count, steps}` for compact loops (a square = repeat 4 of drive+turn), single nesting level. No conditionals in rev 1 – the bot has no sensors beyond encoders and camera, and vision runs on the host.

**Control and safety:**
- `plan.pause` takes effect at the end of the current step (no mid-step resume maths in rev 1); `plan.cancel` stops immediately; the e-stop `stop` always cancels the plan.
- **Arbitration:** while a plan runs, `motor.write` / `drive.velocity` are rejected with `busy` (unless the plan is paused or cancelled), so two controllers can't fight. `stop` always wins.
- **`on_disconnect`** (per plan): `continue` (default for plans – surviving the outage is the point), `finish_step` (stop at the next step boundary), or `stop`. Reactive streaming commands keep their short velocity timeout, so a crashed controller still stops the bot. An explicit **Stop button in Studio sends `plan.cancel` + `stop`** – the policy only applies to *unplanned* disconnects.
- Hard guard rails regardless of policy: speed limits from `speed.set`, per-step timeouts (default derived from distance and speed), and **stall detection** (encoders not moving while commanded → step `failed: stalled`, plan aborted). Failures emit `plan.failed{seq, reason}` (`timeout | stalled | cancelled | low_battery`). A maximum total plan duration is part of `limits`.
- Dead-reckoning drifts: each `step_done` event includes the pose, so the host can compare planned vs. actual, and lessons can show the error accumulating.

**Library side (§5.2c)** builds routes, tracks the expected pose to turn absolute waypoints into relative steps, previews them, and handles upload, resume and results transparently.

### 4.6 Modules: making new sensors easy to add
Rev 1 has only wheels, camera, lights and LEDs, but more sensors and modules will follow (distance, IMU, line sensors, grippers, ... possibly on UART). The firmware hides the bus and wiring; the protocol only sees **modules**:
- `hello.modules` lists what is attached: `{id, type, version, topics, actions}`, e.g. `{"id":"front_distance","type":"distance","version":1}`. Hot-plug is reported with `module.added` / `module.removed` events.
- Generic commands work for every module: `module.read{id}` (latest values), `module.call{id, action, ...}` (actions such as `calibrate`), and telemetry topic `module.<id>`. So a new module type needs **no new protocol commands**.
- Each module *type* is described once in `protocol/modules/<type>.json`: its values (name, unit), actions and parameters. That file is the contract between firmware driver, library, simulator and docs.
- Adding a module type = firmware driver + descriptor file (+ optionally a tiny library class for a friendlier API, and a simulated version so lessons work without hardware). Without the optional class, `bot.modules.front_distance.read()` already works.
- Students never see buses or pins (consistent with "no GPIO access").

### 4.7 Camera
ESP32-S3 + OV2640/OV5640-class sensor, MJPEG over HTTP on port 81 (`/stream`), per-frame headers with timestamp, frame number and odometry pose.

| Preset | Resolution | Max fps | Use |
|---|---|---|---|
| `fast` (default) | 320×240 | 25 | Vision control loops (follow the ball), lowest latency |
| `balanced` | 640×480 | 15 | Viewing, ML models |
| `detail` | 1280×720 | 8 | Photos, inspection |

Custom settings: any resolution the bot lists in `hello.capabilities.camera.resolutions`, fps 1–30 (an upper bound; Wi-Fi decides the rest), JPEG quality 1–100. A privacy indicator LED is on whenever the camera streams.

---

## 5. Workstream B – Python library `movebot`

### 5.1 Layers
1. `movebot.protocol` – message types, codec, schema validation.
2. `movebot.transport` – async WS client (reconnect, heartbeat, request/response correlation), MJPEG reader.
3. `movebot.discovery` – mDNS, UDP beacon, MAC lookup, subnet scan.
4. `movebot.Bot` – high-level API, **synchronous by default** (runs an asyncio loop in a background thread so beginners never see `await`), with `movebot.aio.Bot` for advanced users.
5. `movebot.sim` – the simulator (see §6).
6. `movebot` CLI – `discover`, `connect`, `shell` (REPL with a `bot` object), `sim`, `studio`, `record/replay`, `doctor` (diagnoses network/Python issues).

### 5.2 Beginner API sketch
```python
from movebot import Bot

bot = Bot()                     # auto-discovers; Bot("sim") uses the simulator
bot.forward(0.5)                # metres, blocks until done
bot.turn(90)                    # degrees, + = left
bot.forward(0.5, wait=False)    # returns a handle: .done, .wait(), .cancel()
bot.lights.on()                 # bot.lights.left.level = 0.5
bot.status.blink("green")
print(bot.encoders.left.ticks, bot.pose)       # x, y, yaw
frame = bot.camera.frame()                     # numpy array (BGR) – opencv-ready
bot.on("low_battery", lambda e: print("charge me"))
```
Design rules: friendly exceptions with a fix ("Bot not found – is it on the same Wi-Fi?"), sane defaults, everything discoverable via `help()`/autocomplete (full type hints), no hidden global state (a `Bot` object is explicit, so multi-bot can be added later without breaking code), always stop the motors on exit/Ctrl-C (`atexit`, the relay, and the firmware watchdog as the final net).

### 5.2b Streaming / vision-control API (needed by the flagship lessons)
Lessons like "follow the blue ball" and "gesture control" are **closed-loop control over a video stream**, which has different needs from `forward(0.5)`:
```python
for frame in bot.camera.frames():          # always the LATEST frame; old ones are dropped, never queued
    x, area = find_blue_ball(frame)        # student code (OpenCV)
    bot.drive(v=0.15, w=-0.004 * (x - 160))   # continuous velocity command, ~10–20 Hz
```
Requirements this puts on the design:
- **Streaming velocity control** (`bot.drive(v, w)`) with a short bot-side timeout, so a stalled script stops the bot.
- **Latest-frame semantics** and **timestamps**: every frame carries a capture timestamp and the odometry at that moment (protocol requirement), so students can reason about latency (~100–300 ms over Wi-Fi) – itself a good lesson.
- A tiny, optional `movebot.vision` helper module (colour-blob finder, draw overlays, FPS counter) so lessons can start simple, while the OpenCV-only version is shown alongside.
- Frames can also be shown in Studio's video dock with **student-drawn overlays** (`bot.camera.show(frame)`), so students see what their code sees.
- Webcam-driven control (gestures) uses the **laptop's own webcam**, not the bot's; the lib doesn't wrap that – lessons use OpenCV/MediaPipe directly and just call `bot.drive`.

### 5.2c Abstracted moves and routes
Beginner-friendly names on top of the wire steps (defaults are friendly, every one has an explicit-argument form):
```python
bot.forward(0.5); bot.back(0.2)
bot.left()            # 90°, left(45) for other angles
bot.right()           # 90°
bot.u_turn()          # 180°
bot.spin(360)         # turn on the spot
bot.arc(radius=0.3, angle=90)
bot.wait(1.0)
bot.stop()
```
Each of these is a one-step plan under the hood (§4.5), so they are ordered and exactly-once for free. For a whole route, build it first and hand it over:
```python
route = bot.route()                       # nothing is sent yet
route.forward(0.5).left().forward(0.5)    # chainable
route.wait(1).lights.on().right().forward(1)
route.go_to(1.0, 0.5)                     # absolute waypoint -> compiled to turn + drive from the expected pose
route.preview()                           # draws the predicted path (Apps/Code mode map, or matplotlib)

result = route.run()                      # upload + start + wait; returns per-step poses and timings
handle = route.run(wait=False)            # handle.pause() / .resume() / .cancel() / .progress / .on_step(...)
```
- **Resilient by default**: `run()` survives disconnects (reconnect → `plan.status` → resume from `next_seq`), reports `PlanLost` if the bot rebooted, and fires `on_disconnect` / `on_resume` callbacks students can print.
- `route.on_disconnect = "continue" | "finish_step" | "stop"` exposes the policy; beginner default is `continue` with a conservative total-duration cap.
- A route is plain data: `route.to_json()` / `Route.from_json()` (save, share, replay, put in a lesson), and a Logo-style text form for teaching, e.g. `Route.parse("forward 0.5; left; wait 1; forward 0.5")`.
- Planned vs. actual: `result.steps[i].pose` vs `route.expected[i].pose`, with a helper to plot the drift.

### 5.3 Quality
Type-checked (pyright/mypy strict), ≥90 % coverage on codec/transport, fault-injection tests (drop, delay, disconnect mid-move), Python 3.10–3.13, Windows/macOS/Linux/RPi-ARM64.

---

## 6. Workstream C – Simulator (`movebot sim`)

Minimum viable (Phase 1):
- Implements the full protocol, including goal lifecycle, watchdog, capability list, mDNS advertisement (so discovery is testable).
- Differential-drive kinematics with configurable noise, slip, encoder quantisation, motor dead-zone, acceleration limits.
- Virtual camera: Phase 1 = generated test pattern. By Phase 4 a **simple first-person perspective render** of a 2D world (floor, walls, lines, coloured balls drawn as discs scaled by distance – cheap, CPU-only, deterministic, no GPU or game engine) so **the flagship lessons work in the sim**: follow/hit the blue ball, line following, colour tracking. Worlds are small files (`ball_arena`, `line_track`, `empty`) lessons can pick.
- Moveable objects: a ball the bot can push (simple collision/friction) and optionally a scripted moving ball; ground-truth state exposed to lesson **checks** ("did the bot touch the ball within 20 s?").
- Frame timing like the real thing: configurable resolution/fps/latency, so latency-sensitive control behaves realistically.
- Full plan engine per §4.5 (queue limit, `next_seq` / duplicate / gap handling, `boot_id`, results ring buffer, stall and timeout failures, `on_disconnect` policies) – it is the **reference implementation the firmware is compared against**.
- Fault injection flags: latency, packet loss, duplicate/reordered messages, random disconnects (including mid-step), simulated reboot (new `boot_id`), low battery, blocked wheels (stall).
- A tiny viewer (served by Studio) showing the bot moving in the 2D world.

Later (not rev 1 blockers): Gazebo model + URDF shared with the ROS package.

---

## 7. Workstream D – Studio (host app)

### 7.1 Shell and connection panel (header/side)
- Connection state (disconnected / connecting / connected / reconnecting / incompatible), bot name, signal strength, battery, firmware/protocol version.
- **Find bot**: first try 192.168.4.1 (direct mode) → mDNS → manual IP → MAC lookup → subnet scan. Remembers the last bot (one active connection at a time).
- **Setup wizard** with two paths:
  - **Direct mode (default for classrooms):** detect that the laptop is on `MoveBot-XXXX`, connect, done. Nothing to configure.
  - **Network mode (home):**
    1. Connect in direct mode.
    2. Pick Wi-Fi + password → `wifi.set` (+ optional static IP).
    3. Guide the user back to their normal Wi-Fi (laptop loses connectivity to the bot's AP – a real UX trap; optionally automate with `netsh` / `nmcli` / `networksetup` after explicit consent).
    4. Re-discover and confirm.
  - "Reset to AP mode" button, with an explanation of what it does.
- Mode switch: **Code** (IDE) / **Apps** (example GUIs) / **Learn** (lessons + docs). All share the same connection, workspace and current project; a **split view** lets you keep a lesson open beside the editor or an app beside its source.
- Diagnostics page (`doctor`): ping, ws latency, video fps, packet loss, RSSI. Saves a support bundle.
- Settings: workspace folder, Python env status/repair, language (i18n-ready from the start), update check.

### 7.2 Code mode (the IDE) – free to tinker
- **Everything in the workspace is editable**: teachers and students can modify our examples, copy them, delete them, add their own files and folders. Nothing is locked, and nothing breaks the app (originals can always be restored, §7.2b).
- File tree (workspace folder, examples, my-code), tabs, Monaco editor with movebot autocomplete (type stubs) and inline error markers.
- Run / Stop / Run-selection; script runs in a **subprocess** of the managed venv; stdout/stderr streamed to the console panel; Stop kills the process and the relay stops the motors.
- **Text editor only** (decision): Monaco with Python highlighting, autocomplete from type stubs, snippets for common movebot calls, simple "Insert example" menu. No block editor.
- Console: output log first (Phase 3a); interactive REPL with a ready-made `bot` (Phase 3b; Windows needs ConPTY); an optional full terminal in the managed environment for people who want to tinker further.
- **Run as app** button next to **Run**: if the script uses the UI kit, it opens its GUI in the Apps pane (§7.3) with the console still visible beside it.
- Side dock: live camera, pose/encoder telemetry, joystick for manual jog, e-stop always visible.
- Friendly tracebacks (highlight the user's line, hint at the common cause).
- Package installs: **offline-first** – numpy, OpenCV, and the ML extras (MediaPipe + model files) ship in the offline bundle and install from local wheels through a guarded UI ("Enable Vision", "Enable ML"); online `pip` only as an optional extra. The managed Python version is pinned to whatever the ML wheels support (decide in Phase 0; check MediaPipe/OpenCV availability on Windows, macOS, and Raspberry Pi ARM64 – MediaPipe on Pi is the likeliest gap).

### 7.2b Workspace seeding and updates (how our examples land on the teacher's machine)
On first launch (installation) Studio creates a visible workspace folder, e.g. `Documents/MoveBot/`:
```
MoveBot/
  examples/     ← copied from the installer, grouped by course level; editable
  my-code/      ← empty, the teacher's/students' own projects
  my-lessons/   ← optional: lessons the teacher authors (appear in Learn mode)
```
- A pristine, read-only copy of all shipped content lives in the app's data folder, plus a manifest of content versions and file hashes.
- **Never overwrite user edits.** On an app/content update: new examples are added; unchanged files are updated silently; **files the user has modified are left alone** and the new version is offered as a side-by-side copy (`name (new version).py`) or via a *Compare* view.
- **Restore original** (per file or per example folder) from the pristine copy – works offline, and removes the fear of "breaking" an example.
- "Duplicate to my-code" is offered prominently when opening a shipped example for editing, as a gentle nudge (not a restriction).
- Classroom use: a teacher can point the workspace at a shared/network folder or export/import a workspace as a zip (handy for sharing a configured set with a class).

### 7.3 Apps mode (a ready-made GUI for every example)
- A gallery of **apps** (cards with a thumbnail, title, difficulty, and whether it needs the real bot, the sim, or a webcam). Each card is a normal example script that builds its interface with the UI kit (§8). Click → the script starts in the managed Python environment and its GUI (buttons, sliders, video, output panels) appears in the pane. Teachers and students can use these directly with **no code at all**.
- Works with the real bot or the simulator (a clear "Simulator / Real bot" indicator, one click to switch).
- **Show code** bridges "play" to "program": a per-app button opens the script in Code mode, and an *inspector* toggle highlights any widget and jumps to the exact line that created it (§8).
- **Open lesson** on each app jumps to its Learn page.
- Apps that a student *edits* in Code mode run from the same card (their copy shows up in the gallery under "My apps").

### 7.3b Learn mode (lessons as the documentation)
- Renders lesson Markdown (with images, callouts, tabs, and code snippets) in a clean reading pane with a table of contents, search (offline), and prev/next through the course.
- **Every shipped example has a pre-written lesson page** (enforced by CI, §10). Two styles, declared per lesson: *walkthrough* (step by step, annotated screenshots showing how each button/output on the UI maps to code) and *overview* (a broad explanation of what the example does and the idea behind it).
- Embedded code is **pulled from the real example file** (not copy-pasted), so docs and code cannot drift; each snippet has *Open in Code* and, where it makes sense, *Run this app* buttons.
- The same Learn mode hosts the rest of the documentation: getting started, connecting the bot, troubleshooting, the library API reference, and teacher guides – all offline.
- Rendered with the same Markdown toolchain (Python-Markdown + pymdown-extensions) used for the public docs site, so what teachers see in the app matches the website exactly.

### 7.4 Backend modules
Uses the open `movebot` library for connection, discovery, relay and recording (no hub code of its own); Studio adds `provisioning` · `runner` (scripts and app subprocesses) · `workspace` (seeding, manifest, restore) · `learn` (Markdown rendering, snippet embedding, search) · `env` (managed Python, offline bundle) · `api` (REST + WS for the frontend) · `updates` (incl. signed firmware flashing/OTA).

### 7.5 Risks specific to Studio
| Risk | Mitigation |
|---|---|
| Managed Python / venv breaking on student machines | Dedicated env manager + `doctor`; bundle runtime; test on clean VMs |
| AP-mode provisioning UX (lose internet, OS Wi-Fi quirks) | Wizard with live state detection; consider BLE provisioning as a future firmware feature; spike early |
| Windows firewall / mDNS blocked on school networks | Manual IP + MAC fallback; docs for IT admins; the relay binds to localhost by default |
| ML/vision dependencies are big and version-picky (OpenCV, MediaPipe; Pi ARM64) | Pin one managed Python version; bundle wheels + model files; make "Vision/ML" an opt-in pack so the base install stays small; label ML lessons "needs a PC, not a Pi" if necessary |
| Vision lessons feel laggy on school Wi-Fi/low-end CPUs | Latest-frame semantics, QVGA default, timestamps, teach latency compensation; tune lesson difficulty on real hardware in Phase 7 |
| Content updates clobbering a teacher's edited examples | Manifest + hashes, never overwrite modified files, side-by-side new versions, one-click restore (§7.2b); test this flow explicitly |
| Example GUIs / lessons drifting out of sync with the code | Lessons embed snippets from the real files; CI runs every example against the sim, renders every lesson, and fails if an example lacks a lesson or a snippet anchor is missing |
| Installers & code signing (Windows SmartScreen, macOS notarisation) cost money/time | Start with `pipx`/`uv tool install` + a one-line installer; signed installers in Phase 6 |
| School laptops: no admin rights, locked-down IT, no internet | Per-user/portable install, fully offline bundle (Python, wheels, docs, examples), IT-admin guide |
| Student laptop must leave its internet Wi-Fi to join the bot's AP | Make this explicit in the UX; keep everything offline-capable; teach "two networks" once in the first tutorial |

---

## 8. Workstream E – UI kit (`movebot.ui`)

- Components: `Button`, `Toggle`, `Slider`, `Joystick`, `Dpad`, `Text`, `Number/Gauge`, `Plot` (live telemetry), `Video`, `Log`, `Image`, `Row/Column/Tabs` layout, `KeyboardControls`.
- Programming model: callbacks, no HTML/CSS knowledge:

```python
from movebot import Bot
from movebot.ui import App, Video, Joystick, Button, Text

bot = Bot()
app = App("Drive me")
app.add(Video(bot.camera))
app.add(Joystick(on_move=lambda x, y: bot.drive(x, y)))
app.add(Button("Lights", on_click=bot.lights.toggle))
app.add(Text(lambda: f"x={bot.pose.x:.2f}"))     # callables = live-updating
app.run()
```
- Runs standalone in a normal browser tab **and** embedded in Studio's Apps mode (same code).
- **Every shipped example has a built-in GUI** built with this kit, so teachers/students can use it with zero code: buttons to start/stop, sliders for parameters, video, live values, plots, and a log/output panel. Examples without bespoke UI still get a **default control panel** via `movebot.ui.panel(bot)` (drive pad, camera, telemetry, lights, e-stop).
- **Decorator style for the absolute beginner** – turn ordinary functions into buttons/outputs, no layout code:

```python
from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Draw a square")

@app.button("Draw square")            # a function becomes a button
def square():
    for _ in range(4):
        bot.forward(0.3)
        bot.turn(90)

@app.slider("Speed", 10, 100, 50)     # a parameter becomes a slider
def set_speed(percent):
    bot.speed = percent

@app.output("Position")               # a function becomes a live output
def position():
    return f"x={bot.pose.x:.2f}  y={bot.pose.y:.2f}"

app.run()
```
- **Source mapping ("how the UI is connected to the code")**: every widget records the file and line that created it (and its handler). The Apps-mode *inspector* toggle highlights a widget and opens that line in Code mode, and lessons use the same mapping to draw annotated screenshots (§10.1).
- **Tuning tools built in**: e.g. a clickable video widget that samples the colour under the cursor and shows HSV values – the blue-ball lesson depends on it.
- Apps declare what they need (`requires = ["vision"]`, `needs_bot = false`, `webcam = true`) so the gallery can say "works in simulator" or "needs a webcam".
- Initial demo set (all need only rev-1 hardware – camera + encoders):
  1. Drive with joystick/keyboard + live video
  2. Draw a square / polygon (odometry accuracy)
  3. Lights & status LED show
  4. Live encoder / speed plot
  5. Colour follower (OpenCV)
  6. Line follower (camera)
  7. Odometry map (path trace)
  8. "Record and replay a path"
  9. **Route planner**: click waypoints on a 2D map (or type commands) → see the predicted path → *Send route* → watch the bot's actual path appear over it, with the drift per step. Also a drag-and-order list of steps with delays; save/load routes as JSON. Teaches planning, units, dead-reckoning error, and why robots need feedback.
- Accessibility: keyboard operable, high-contrast theme, large-touch targets (tablet use).

---

## 9. Workstream F – ROS 2 node (`movebot_ros`)

Pure `rclpy` package using the `movebot` library (no firmware changes, no compile step), starts after the library API is stable. **On a ROS setup the node is the hub**: it owns the connection to the bot (so Studio's relay is not involved) and exposes everything as topics/services; code that wants the bot uses ROS. A `relay:=true` parameter optionally lets plain `movebot` scripts connect through the node too.

| Direction | Topic / interface | Notes |
|---|---|---|
| out | `image_raw/compressed` (+ `camera_info`) | MJPEG forwarded as-is, almost no CPU. Optional decoded `image_raw`. |
| out | `odom` (nav_msgs/Odometry), `tf` odom→base_link | Pose from the bot; covariance configurable. |
| out | `joint_states` | Wheel positions/velocities. |
| out | `battery_state`, `diagnostics` | |
| in | `cmd_vel` (Twist) | → `drive.velocity`, with timeout. |
| in/srv | `lights`, `status_led`, `reset_odom`, `stop` | Services/Topics. |
| action | `follow_route` (goal = list of steps, feedback = step done + pose, result = per-step poses) | Wraps the plan engine (§4.5). A custom action type needs a compiled interface package; until then use a JSON-string goal or ship `movebot_msgs` as a second, small package. |
| params | `bot_url`, `namespace` (default empty), frame ids, publish rates | Single bot per node; the namespace parameter keeps multi-bot possible later. |

Extras: URDF + RViz config, launch files, Docker image, example `teleop_twist_keyboard` walkthrough. Target the current ROS 2 LTS (Jazzy at time of writing; verify and add the newest LTS when it is stable). On Windows, document WSL2/Docker; native support is limited.

---

## 10. Workstream G – Lessons, examples and documentation

### 10.1 Example packs: code + GUI + lesson in one folder (teachers + us write them)
The unit of content is an **example pack** – a folder, so a teacher needs only a text editor and a template. It is simultaneously a runnable app (Apps mode), editable source (Code mode) and a lesson page (Learn mode):
```
content/examples/05-follow-the-ball/
  example.toml    # id, title, level, minutes, concepts, requires=["vision"], needs_bot/webcam, world="ball_arena",
                  # lesson_style="walkthrough"|"overview", author, language, licence
  app.py          # the finished working example, with its built-in GUI (what the Apps card runs)
  starter.py      # optional exercise version with TODOs (for lesson-style teaching)
  lesson.md       # pre-baked lesson page: images, explanation, code snippets pulled from app.py
  check.py        # optional automated check, run against the simulator (and optionally the real bot)
  assets/         # images, annotated screenshots, small models
```
Concept pages with no code (e.g. "Connect your bot", "Two Wi-Fi networks", "What is odometry?") are plain Markdown under `content/guides/`.

**Rule: no example ships without a lesson page and a GUI.** CI fails otherwise.

**How a lesson explains the UI ↔ code link** (the "walkthrough" style):
- A **screenshot of the real UI with numbered callouts** ("① Start button, ② HSV sliders, ③ camera view").
- Each callout maps to a **named snippet in `app.py`** marked with anchor comments (`# --8<-- [start:start-button]` … `[end:start-button]`, the standard pymdown snippets syntax), which the page embeds live: *"① The Start button calls `follow()`:"* followed by the actual 5 lines.
- Screenshots are **generated, not hand-made**: CI launches the app against the simulator in a headless browser (Playwright) and captures them; callout positions come from the widget ids recorded by the UI kit's source mapping (§8). So images never go stale when the UI changes. (Hand-made images are still allowed for concept pages. Auto-annotation is an enhancement – the first lessons may use plain screenshots.)
- The "overview" style is a broad explanation: what it does, the idea behind it (e.g. colour thresholding, proportional control), what to try changing.

- **Authoring path for teachers**: `movebot example new` (also a "New example" button in Code mode) creates the folder from a template, with the GUI skeleton and a lesson template; `movebot example check` validates metadata, **runs `app.py` + `check.py` in the simulator**, and renders the lesson page so a broken one is caught before class. Studio also reads packs from the workspace `my-lessons/` folder, so a teacher can write and use one without any contribution step. A lesson-only page (no code) is just a `lesson.md` they drop in.
- **Sharing**: pull request to the public repo (review checklist: correct, age-appropriate, runs in sim, offline-safe, licensed). Lessons are CC BY-SA 4.0 (code in them Apache/MIT) so teachers can adapt each other's work.
- **Progression** (so lessons form a course, not a pile): 0 *Meet MoveBot* (connect, drive, lights) → 1 *Move* (distance, turn, square, encoders, odometry) → 2 *See* (camera, colour, image basics) → 3 *React* (follow the ball, hit the ball, line follow) → 4 *Learn* (ML gestures, own model) → 5 *Robotics* (ROS).
- CI runs every example's `app.py` + `check.py` in the simulator, renders every lesson page, and regenerates screenshots on each change. Hardware-in-the-loop runs happen in Phase 7.

### 10.2 Flagship examples (build these first – they drive the requirements)
1. **Follow the blue ball** (PC reads the bot's video stream, finds the ball with OpenCV colour thresholding, steers and sets speed from the ball's position and size). Variant: **hit the ball** (drive at it until it fills the view, then stop/back off). Teaches: colour spaces (HSV), contours, proportional control, latency.
2. **Gesture-controlled bot** (ML model on the **laptop webcam**; MediaPipe hand/gesture recognition → open palm = stop, fist = forward, pointing left/right = turn). Teaches: ML inference, mapping predictions to actions, debouncing/safety. Runs with a bundled model file, offline.
3. **Line follower** (bot camera, threshold + centroid steering).
4. **Draw a square / polygon** with odometry, and measure the drift.
5. **Teach your own gesture/object** (stretch lesson: collect images → small classifier → drive). Needs an offline-capable training path (e.g. scikit-learn / a small ONNX model); scoped after 1.0 if heavy.
All run **unchanged against the simulator and the real bot** (just `Bot()` resolves differently), which is why the sim camera world matters (§6).

### 10.3 Documentation
**One source, two outputs.** The Markdown in `content/` and `docs/` is rendered (a) inside the app's **Learn mode**, offline, and (b) as the public website (mkdocs-material + mkdocstrings, versioned with `mike`, GitHub Pages). Both use the same Python-Markdown + pymdown-extensions set (admonitions, tabs, snippets, syntax highlighting), so there is no second renderer to keep in sync. The app ships the docs of its own version, so documentation always matches the installed software.

Four audiences, four tracks:
1. **Students**: "First 15 minutes", "Your first program", then the lesson course above.
2. **Teachers**: classroom setup (one bot per device, direct vs network mode, resetting bots, school IT checklist), printable quick-start cards, lesson plans, **how to write a lesson**, FAQ.
3. **Developers/contributors**: architecture, **protocol spec** (generated from schemas), library API reference, writing a UI-kit component or demo, contributing a lesson.
4. **ROS users**: install, topics, launch, calibration.

Rules: every code block in the docs is embedded from an example file executed in CI against the simulator, and every example's app and check run in CI (docs cannot rot); contribution guide, code of conduct, issue/PR templates, troubleshooting page generated from the `doctor` checks. (Studio docs are user-facing only, since Studio is closed.)

---

## 11. Engineering process

- **Version control**: four repos (public `movebot` and `movebot-releases`; private `movebot-studio` and `movebot-firmware`, §3.1), trunk-based with short-lived branches, Conventional Commits, PR review required, CODEOWNERS per workstream. Public repo needs a CLA or DCO policy for contributions (decide with licence).
- **CI (GitHub Actions)**: lint (ruff), types (pyright), unit + sim-integration tests on Windows/macOS/Linux (+ ARM64 for RPi), frontend lint/tests/Playwright e2e on the simulator, ROS job in `ros:<distro>` container, docs build + example execution, conformance suite.
- **Versioning**: SemVer for each package; **protocol version separate** (`MAJOR.MINOR`); a compatibility table (lib ↔ Studio ↔ firmware ↔ protocol) lives in the docs and in the hello negotiation.
- **Releases (GitHub as the release system)**: release-please (or towncrier) for changelogs. Tag in the public `movebot` repo → CI builds wheels, publishes `movebot` / `movebot-ros` to PyPI via trusted publishing, deploys the docs site, builds the ROS Docker image, and produces the **content bundle** (examples + lessons + docs). Tag in the private `movebot-studio` repo → CI pulls a pinned `movebot` version and that content bundle, builds **signed** installers (Windows per-user installer + portable zip, macOS, Linux/RPi) and the **offline bundle** (Python runtime, wheels, ML models, firmware, docs), and publishes them to the public **`movebot-releases`** repo with `latest.json`. Firmware tags in `movebot-firmware` publish signed images to the same releases repo. Stable vs. beta via GitHub pre-releases for classroom pilots.
- **Quality gates**: no merge if the conformance suite regresses; ADR for any protocol-breaking change.
- **Telemetry/privacy**: none by default; opt-in anonymous crash reports only if we want them later.
- **Security basics**: the relay binds to localhost by default; bot AP password printed on the device; optional pairing token in the protocol (reserve the field now); OTA images must be signed (firmware plan, but the update tool lives here).

---

## 12. Phased roadmap

Durations are *relative effort*. The software team is just us, so phases run mostly one after another; "parallel" below means "can be interleaved". Firmware (Phase 7) is also ours and starts when the hardware arrives.

| Phase | Name | Contents | Exit criteria |
|---|---|---|---|
| **0** | Foundations (1–2 wk) | ADRs for §2, repo + CI skeleton, naming/PyPI reservation, units & frames, protocol v0.1 draft, glossary | Repo builds in CI; ADRs merged; protocol v0.1 reviewed by firmware owner |
| **1** | Spine: protocol + sim + core lib (4–5 wk) | Schemas, codec, transport, `Bot` API incl. abstracted moves, **plan/route protocol (§4.5) with its simulator engine and conformance tests**, simulator (kinematics + synthetic camera), CLI (`discover/sim/shell`), conformance suite v1 | `python square.py` drives a square in the sim within tolerance; **protocol v0.1 frozen → firmware team can start** |
| **1b** | Relay + camera + modules (2–3 wk, in/after Phase 1) | Library `Relay` mode (honouring plan `on_disconnect` policy), camera presets + MJPEG stream with frame timestamps/pose, latest-frame camera API, simulated first-person camera, module framework (§4.6) with simulated distance sensor and IMU | Two processes share one (simulated) bot; killing the controller stops the bot; a script sees the sim camera and a sim module |
| **2** | Studio core + connection UX (4 wk) | Backend using the lib's relay, discovery, setup wizard (against sim), status panel, live video + telemetry dock, e-stop | A fresh install connects to the sim, shows video/telemetry, survives disconnects |
| **3** | Code mode (4 wk) | Workspace + **content seeding/restore/update manifest** (§7.2b), Monaco editor, runner, console, REPL, managed Python env (offline bundle), templates, friendly errors | A beginner writes + runs + stops a script; installing seeds `examples/`; an edited example survives an update and can be restored |
| **4a** | UI kit + Apps mode (3 wk) | Components + decorator API, NiceGUI backend, Apps gallery, source-mapping inspector, "Run as app", default control panel, "Show code" bridge | Every demo has a GUI and runs in sim; usable on a tablet |
| **4b** | Vision/ML + example packs (4 wk, parallel to 4a) | Sim perspective camera + `ball_arena`/`line_track` worlds, `movebot.vision`, example-pack format + `movebot example` CLI, flagship examples (blue ball follow/hit, gesture control, line follow, square), ML offline pack | Flagship examples pass their `check.py` in sim in CI; a teacher can create + run a new pack without help |
| **4c** | Learn mode + lesson content (4 wk, starts when 4a/4b have first examples) | Markdown renderer (shared with docs site), snippet embedding, split view, search, generated screenshots (+ callouts), lesson templates, a lesson page for **every** shipped example, getting-started and teacher guides | CI fails on any example without a lesson/GUI; a new teacher completes the first lesson using only Learn mode |
| **5** | ROS 2 bridge (3 wk, can start after Phase 1) | Node, launch, URDF, Docker, docs | `ros2 launch` + RViz shows image/odom from the sim; `cmd_vel` drives it |
| **6** | Packaging, release system, hardening (ongoing, 4 wk final) | Installers + offline bundle, code signing, `movebot-releases` pipeline + `latest.json` updater, firmware flashing UI, clean-VM and non-admin install tests, usability tests with real teachers/students | Tagged `v1.0.0-rc` published through GitHub releases; beta with a pilot class |
| **7** | **Hardware integration** (when firmware alpha exists) | Run conformance suite on the real bot, fix divergences, calibrate sim noise to real data, field-test Wi-Fi provisioning | Conformance green on hardware; rev-1 release |

**Critical path:** Phase 0 → 1 (protocol freeze) → 1b → 2 → 3 → 6. Phases 4a/4b/4c and 5 branch off Phase 1b/2; 4b/4c (examples + their GUIs + lessons) are the biggest content risk and the main reason the product exists, so start the simulator's camera world early and keep writing lessons continuously rather than at the end. Phase 7 is gated by firmware, not by us.

---

## 13. Additions and cuts vs. your original list

**Added** (and why):
- Protocol spec + conformance suite (firmware hand-off, prevents drift)
- Simulator (unblocks everything; classroom value)
- Library-level relay / connection-owner model (replaces a separate hub; one bot, many local consumers; safe stop)
- Example packs (app + GUI + lesson in one folder, authoring CLI, CI-checked in sim) and flagship vision/ML examples
- Three app modes (Code / Apps / Learn) and a workspace that is seeded with examples but never loses user edits (restore/compare)
- Learn mode: Markdown lessons as the offline documentation, with code embedded from the real files and generated screenshots
- GitHub-only release system: private source repos + public `movebot-releases` (signed installers, offline bundle, firmware, `latest.json`)
- Streaming-control API and frame timestamps (needed for closed-loop vision lessons)
- Planned routes: numbered, queued, exactly-once, resumable moves with delays (§4.5) + abstracted moves (`left/right/u_turn/arc`) and a `Route` builder; Route planner app
- Idempotent wire commands (set, never toggle) and request-id de-duplication
- Open/closed split: public protocol + library + lessons, private Studio + firmware, signed firmware via Studio
- Motor watchdog, e-stop, heartbeat (safety)
- Hello/capabilities/version negotiation (compat across revisions – you already plan multiple revisions)
- Logical peripherals instead of pins (works across rev 2+, safe)
- Record/replay, diagnostics (`doctor`), calibration wizard (wheel diameter / track width)
- OTA / flashing tool in Studio (hook now, implement later)
- Direct (AP) mode as a first-class, offline classroom workflow
- Privacy indicator (LED while the camera streams)
- Managed Python environment (the real beginner-experience risk)

**Changed / clarified:**
- "set: speed" → speed *limit*; raw `motor.write` vs closed-loop velocity vs goal moves are three distinct control modes with defined precedence.
- "x / Δx" absolute → defined relative to odom origin; `go_to(x,y)` composed on host.
- "scan by MAC" → mDNS primary, MAC/ARP scan fallback.

**Deferred / cut for rev 1:**
- Generic pin set/value – **dropped entirely** (no GPIO access).
- Multi-bot control – out of scope for rev 1 (one bot at a time).
- Gazebo simulation, native ROS on Windows, ros2_control hardware interface, BLE provisioning, cloud/classroom management, block-based coding (decided: text only), a standalone hub service.

---

## 14. Open questions (need your input)

*Resolved so far:* audience (high-school students + teachers), one bot at a time, no GPIO, name `movebot`, Python-on-host, library-as-hub (ROS node is the hub on ROS setups), free-to-tinker text editor, three modes (Code / Apps / Learn), seeded examples with built-in GUIs and pre-written lessons, open/closed split as in §3.1, GitHub as the release system, team = us (firmware too, once hardware arrives), ESP32-S3 + camera, extensible modules (§4.6), camera presets (§4.7), lessons declare their supported OS/hardware, teachers author in the installed workspace + a community examples repo, offline operation (§2.5).

Still open:
1. **Target date?** The roadmap is relative effort.
2. **Licences** for the open repos: suggestion Apache-2.0 for code, CC BY-SA 4.0 for lessons.
3. **Disconnect default for routes**: `continue` (current default) or `finish_step`?
4. **Hardware details** from the hardware designer: wheel diameter, track width, encoder resolution, motor driver, top speed, which status LEDs exist, battery chemistry. The simulator uses placeholders until then.
5. **First add-on modules**: which sensors are likely first (distance? IMU? line sensor?), so their descriptors and simulated versions exist before lessons need them.

---

## 15. Immediate next steps (first 2 weeks)

**Progress (2026-10-12):** items 3 and 4 are done in this repo: protocol v0.1 draft (`protocol/SPEC.md`, JSON Schema, test vectors, conformance suite), ADRs 0001–0004 (`docs/adr/`), and the Phase 1 spine of the `movebot` library (connection with reconnect, `Bot` API with abstracted moves, `Route` builder, resumable plans, simulator with plan engine and fault injection, `movebot` CLI). Phase 1b is done too: camera (presets, MJPEG with timestamp/pose per frame, simulated first-person camera, `bot.camera`), the module framework (§4.6: descriptors in `protocol/modules/`, `bot.modules`, simulated distance sensor and IMU, hot-plug), and the relay (`movebot relay`; the conformance suite also passes through it). The UI kit is done as well (`movebot.ui`: components, decorator API, live values, video with colour picking, code inspector, `movebot panel`; ADR 0005), together with the first two example packs in `content/examples/` (drive-with-buttons, follow-the-ball with its lesson), which CI runs against the simulator. Since then the simulator and the UI kit moved into the private app repository (ADR 0006); their public API is unchanged and documented in `docs/ui.md`. Not yet: mDNS discovery, the app (Studio, being started in `movebot-studio`), Learn-mode rendering, ROS node, more lessons.

1. Answer the open questions above (at least 1, 2, 3, 4).
2. Create the repos (public `movebot` + `movebot-releases`, private `movebot-studio` + `movebot-firmware`) with CI, and reserve PyPI names.
3. Write ADRs for §2.1–2.6.
4. Draft protocol v0.1 (hello, motor.write, drive.velocity, plans, encoder/odom topics, light/status, watchdog) with JSON Schemas and a handful of test vectors.
5. Spike (2–3 days each, throw-away): (a) managed-Python env on a clean, non-admin Windows account, (b) NiceGUI live video + joystick, (b2) end-to-end "follow the blue ball" prototype on a webcam/recorded video + the sim stub, and MediaPipe gesture recognition speed on a typical school laptop, to validate the dependency choices and latency budget, (b3) one full vertical slice of an example pack – `follow-the-ball` as `app.py` with a NiceGUI interface, snippet anchors, a rendered `lesson.md` with a Playwright-generated screenshot – to prove the "code + GUI + lesson" pipeline and the Python-Markdown renderer inside the app, (c) direct-mode (AP) connection and network-mode provisioning against a plain ESP32 dev board if one is available.
