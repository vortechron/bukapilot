# AGENTS.md — Bukapilot Codex Context

This is the Codex-facing version of `CLAUDE.md` for this repo.
Keep the technical guidance aligned when either file changes.

## Codex Operating Rules

- Keep scope tight. Prefer changes in `selfdrive/car/proton/`, then `selfdrive/controls/`, then `selfdrive/ui/`.
- Avoid `panda/`, `installer/`, `/system/`, and anything involving firmware or flashing unless the user explicitly asks.
- Prefer narrow validation. Run targeted `pytest`, `ruff`, or `mypy` commands that match the files touched.
- Treat the dongle tmux session as live process control. Do not send `Ctrl+C` or `exit`; detach with backtick then `d`.
- Cap debug output and check disk usage before adding logs on device.

# Bukapilot (KommuAssist) Development Guide

## Quick Reference (Build/Test/Lint)

```bash
# Build (on device or Linux ARM)
scons -j4                          # full build
scons -j4 selfdrive/car/           # build specific target

# Test
pytest --ignore=openpilot/ --ignore=opendbc/ --ignore=panda/ -n auto
pytest selfdrive/car/tests/        # car-specific tests
pytest -k "test_name" -x           # single test, stop on fail

# Lint
ruff check .                       # lint (line length: 160)
ruff format .                      # format
mypy selfdrive/                    # type check (strict, py3.11)

# CAN tools
python -m opendbc.can.parser       # CAN signal parser
python -m opendbc.can.packer       # CAN message packer
```

## Code Conventions

- **Python:** 3.11, ruff line-length=160, strict mypy
- **Serialization:** Cap'n Proto (cereal/) — NOT protobuf/JSON
- **IPC:** ZMQ pub/sub via cereal messaging layer
- **CAN:** DBC-driven — signals defined in `opendbc/proton_general_pt.dbc`
- **Imports:** Always use `openpilot.` prefix for internal modules
- **Tests:** pytest with `pytest-xdist` (`-n auto`), markers: `@pytest.mark.tici`, `@pytest.mark.ka2`, `@pytest.mark.slow`

### Import Order
```python
from cereal import car                                    # capnp messages
from openpilot.selfdrive.car.proton.values import CAR     # internal modules
from opendbc.can.parser import CANParser                  # CAN utilities
from openpilot.common.numpy_fast import clip, interp      # shared utils
```

### Car Interface Pattern
```
interface.py     → CarInterface(CarInterfaceBase)     — config, params, fingerprint
carstate.py      → CarState(CarStateBase)             — parse CAN → state
carcontroller.py → CarController(CarControllerBase)   — state → CAN commands
protoncan.py     → helper functions for building CAN messages
values.py        → CAR enum, DBC dict, CANBUS constants, platform configs
fingerprints.py  → CAN ID fingerprints per vehicle model
```

### Supported Proton Models
| Model | Enum | Mass | Wheelbase | Notes |
|-------|------|------|-----------|-------|
| X50 pre-FL | `CAR.X50` | 1370kg | 2.60m | Has front radar |
| X50 FL / S70 | `CAR.S70` | 1300kg | 2.627m | Camera-only, no radar |
| X70 | `CAR.X70` | 1610kg | 2.67m | |
| X90 | `CAR.X90` | 1705kg | 2.805m | |

## Project Overview

This is a fork of [kommuai/bukapilot](https://github.com/kommuai/bukapilot), which is itself a fork of [commaai/openpilot](https://github.com/commaai/openpilot). bukapilot is an open-source ADAS (Advanced Driver Assistance System) providing Adaptive Cruise Control (ACC), Lane Keep Assist (LKA), Forward Collision Warning (FCW), and Lane Departure Warning (LDW) for Malaysian vehicles (Proton, Perodua).

- **Base branch:** `release_ka2` (the stable release from kommuai)
- **Hardware:** KommuAssist2 dongle running Ubuntu 24.04 LTS (aarch64)
- **Target vehicle:** Proton X50 FL
- **App version:** KommuApp 1.0.14 (Build 89)
- **Bukapilot version on device:** 10.0.5-release
- **OS on device:** Ubuntu 24.04.3 LTS (Noble Numbat)

## Device Details

- **Dongle ID:** `9fcbe17abd7b08d8`
- **Tailscale IP:** `100.109.133.69` (preferred — works from any network)
- **Device Wi-Fi IP:** varies by network
- **Hotspot IP:** `192.168.69.1`
- **Code location on device:** `/data/openpilot`
- **Drive logs location:** `/data/media/0/realdata/`
- **SSH user:** `kommu`

## Architecture

bukapilot runs multiple processes that communicate with each other (like microservices):

| Process      | Role                                      |
|-------------|-------------------------------------------|
| `controlsd`  | Sends steering/gas/brake commands          |
| `plannerd`   | Decides the driving path                   |
| `camerad`    | Captures images from road camera           |
| `modeld`     | Runs neural network on camera input        |
| `ui`         | Touchscreen display                        |
| `boardd`     | Talks to panda hardware (CAN bus bridge)   |
| `athena`     | Communication with KommuApp                |
| `loggerd`    | Logger and uploader of driving data        |
| `locationd`  | Localization and vehicle parameter estimation |

## SSH Access

### Prerequisites
1. SSH key pair must exist on the development machine (`ssh-keygen -t ed25519`)
2. Public key must be uploaded to GitHub (Settings → SSH and GPG keys)
3. GitHub username must be set in KommuApp under Device Settings → SSH Keys
   - The dongle fetches your public key from `https://github.com/<USERNAME>.keys`
4. "Enable SSH" toggle must be ON in KommuApp Software Settings

### Connect
```bash
# Preferred: via Tailscale (works from any network)
ssh kommu@100.82.157.42

# Fallback: via local Wi-Fi (must be on same network)
ssh kommu@<device-wifi-ip>
```

Tailscale is installed on the dongle — SSH works from any network without port forwarding.

## tmux (Process Viewer)

bukapilot runs all processes inside a tmux session. The tmux config on this device uses **backtick (`)** as the prefix key, NOT `Ctrl+B`.

### Key Bindings
```
tmux a              → attach to the running session
`  then  d          → detach safely (ALWAYS use this to exit)
`  then  n          → next window (next process tab)
`  then  p          → previous window
`  then  0-9        → jump to window number
`  then  [          → scroll mode (arrow keys to scroll, q to quit)
```

### Critical Warnings
- **DO NOT** press `Ctrl+C` inside tmux — it kills the running bukapilot process
- **DO NOT** type `exit` inside tmux — it kills the running bukapilot process
- Always use `` ` `` then `d` to detach safely
- To type a literal backtick, press `` ` `` twice quickly, or `` ` `` then `e`

## Development Workflow

### Git Setup on Device
```bash
ssh kommu@192.168.0.64
cd /data/openpilot

# Check current remotes
git remote -v

# Add your fork
git remote add myfork https://github.com/<YOUR_USERNAME>/bukapilot.git

# Create your working branch from the release branch
git checkout -b my-custom-branch origin/release_ka2

# Push to your fork
git push myfork my-custom-branch
```

### Daily Development Cycle
```bash
# 1. Edit code locally on your machine and push
git add <files>
git commit -m "description of change"
git push myfork my-custom-branch

# 2. SSH into dongle (car should be off or ignition-only)
ssh kommu@192.168.0.64
cd /data/openpilot

# 3. Pull changes
git pull myfork my-custom-branch

# 4. Reboot to restart bukapilot
sudo reboot

# 5. SSH back in (~30 seconds) and watch logs
ssh kommu@192.168.0.64
tmux a
```

### Compilation Rules
- **`.py` files** → No compilation needed. Reboot and they run.
- **`.cc`, `.c`, `.h` files** → Must compile on device with `scons -j4`
- Most car-specific tweaks are Python only (in `selfdrive/`).

## Debugging / Logging

### Method 1: print() (simplest)
```python
print(">>> my debug message")
print(f">>> speed: {CS.vEgo}, steering: {CS.steeringAngleDeg}")
```
Shows up in the tmux window of the process that runs the code.

### Method 2: cloudlog (proper bukapilot logging)
```python
from common.logging_extra import cloudlog

cloudlog.info("informational message")
cloudlog.warning(f"warning: {value}")
cloudlog.error("something went wrong")
cloudlog.debug(f"detailed: {data}")
```

### Method 3: File logging (when tmux scrolls too fast)
```python
# IMPORTANT: Always cap file size to avoid filling disk
import os
log_path = "/tmp/my_debug.log"
if os.path.exists(log_path) and os.path.getsize(log_path) > 5_000_000:
    os.remove(log_path)
with open(log_path, "a") as f:
    f.write(f"speed: {CS.vEgo}\n")
```
Watch with: `tail -f /tmp/my_debug.log`

### Method 4: Existence check (did code path execute?)
```python
import os
os.system("touch /tmp/my_code_was_here")
```
Check with: `ls /tmp/my_code_was_here`

### Throttling Logs in Hot Loops
```python
self.log_counter = getattr(self, 'log_counter', 0) + 1
if self.log_counter % 100 == 0:  # ~once per second in 100Hz loop
    print(f">>> speed: {CS.vEgo}")
```

### Method 5: DebugLogger (structured JSONL for longitudinal tuning)
```python
from openpilot.common.debug_logger import DebugLogger

dbg = DebugLogger("my_module")  # writes to /tmp/bp_debug_my_module.jsonl
dbg.log({"vEgo": 27.8, "accel": 0.5})  # throttled to 10Hz, buffered
```
- **Files**: `/tmp/bp_debug_long_ctrl.jsonl`, `long_plan.jsonl`, `long_mpc.jsonl`
- **Fetch**: `./tools/fetch_debug_logs.sh [output_dir]`
- **Format**: One JSON object per line, auto-timestamped (`_t` = epoch, `_m` = monotonic)
- **Safety**: 5MB cap per file, 1 backup, buffered writes (50 entries), never crashes caller
- **Signals logged**: accel commands, stock ACC, rate limiter, lead data, t_follow, MPC source

## Safe Directories to Modify

```
selfdrive/car/proton/     ← car-specific code (interface, carcontroller, carstate)
selfdrive/controls/       ← driving control logic
selfdrive/ui/             ← touchscreen UI
```

## NEVER Modify (Unless You Know Exactly What You're Doing)

```
panda/                    ← CAN bus firmware — can mess up car communication
installer/                ← update/install system
/system/                  ← base OS files
anything with "flash" or "firmware" in the name
```

## Safety Practices

### Always Check Disk Space
```bash
df -h
# Watch the /data partition
```

### Emergency Rollback
```bash
cd /data/openpilot
git checkout release_ka2
git clean -fd
sudo reboot
```

### Before Starting Any Work
```bash
cd /data/openpilot
git log -1    # note the current commit hash somewhere safe
```

### Testing Safely
1. Make small, incremental changes — one thing at a time
2. Test with car in ignition-on, engine-off mode first (bukapilot will boot)
3. Watch logs via tmux for crashes or errors
4. Only test on the road on a quiet road after confirming clean boot
5. Keep a notes file of every change you make

### What Can Brick the Device
- **Filling the disk** → most common real danger. Always check `df -h`. Never write unbounded log files.
- **Corrupting system/boot files** → don't touch `/system/` or boot configs
- **Bad panda firmware** → stay out of `panda/` directory
- **Interrupted system update** → don't kill power during updates

### What WON'T Brick the Device
- Bad Python code → bukapilot crashes but device is fine, SSH still works
- Syntax errors → same, process crashes, fix and reboot

### Nuclear Recovery Option
In KommuApp → Device Settings → "Car Off to Format SD Card" → Format. This wipes everything and reinstalls bukapilot from scratch.

## Simulation / Testing Without Driving

### Option 1: Log Replay (recommended)
```bash
# Copy drive logs from dongle to laptop
scp -i ~/.ssh/id_ed25519 -r kommu@192.168.0.64:/data/media/0/realdata/<drive_folder> ~/drives/

# On laptop with bukapilot built locally (Ubuntu/Linux required)
cd ~/bukapilot
tools/replay/replay '<dongle_id>|<drive_timestamp>' --data_dir=~/drives/
```

### Option 2: Ignition-On, Engine-Off
Turn car key to ON without starting engine. bukapilot boots, you can SSH in and watch logs. No driving needed.

### Option 3: CARLA / MetaDrive Simulator
Full 3D simulation. Requires Ubuntu, GPU, CUDA. Overkill for car-specific parameter tuning since it simulates a generic car, not Proton X50 specifics.

## Useful Commands Reference

```bash
# Check what's running
tmux a

# See drive logs on device
ls /data/media/0/realdata/

# Check disk space
df -h

# View git state
cd /data/openpilot
git remote -v
git branch -a
git log --oneline -5

# Reboot device
sudo reboot

# Watch system logs
journalctl -f
```

## Longitudinal Control Pipeline

```
modeld (20Hz) → radarState (leads) → longitudinal_planner.py (20Hz)
                                              │
                                         MPC solver (long_mpc.py)
                                              │
                                       a_solution (m/s²)
                                              │
                                    longcontrol.py (100Hz, PID)
                                              │
                                       actuators.accel
                                              │
                                    carcontroller.py (50Hz)
                                     ├── scale: ×15 throttle / ×18 brake
                                     ├── 1-bar throttle ramp; planned brake onset/release pass through
                                     ├── 1 bar: custom close-follow stock blend
                                     └── 2/3 bar: original release stock blend
                                              │
                                    protoncan.create_acc_cmd() → CAN bus
```

### Tunable Longitudinal Parameters

**Accel Limits** (`longitudinal_planner.py`):
| Speed | A_CRUISE_MAX | A_CRUISE_MIN |
|-------|-------------|-------------|
| 0 km/h | 1.6 m/s² | -1.2 m/s² |
| 36 km/h | 1.2 | -1.2 |
| 90 km/h | 0.8 | -1.2 |
| 144 km/h | 0.6 | -1.2 |

**Follow Distance** (`long_mpc.py`):
| X50 FL / S70 bar | Personality | T_FOLLOW | Effective stop gap | Gap at 90 km/h |
|------------------|-------------|----------|--------------------|----------------|
| 1 | Aggressive | 0.90s | 4.0m | 26.5m |
| 2 | Standard | 1.02s | 4.5m | 30.0m |
| 3 | Relaxed (old 2-bar smoothing) | 1.25s | 5.5m | 36.75m |

Other platforms retain the stable 1.20s / 1.25s / 1.40s personality values and the 5.5m stop gap.

**Do not lower the one-bar values below 0.85s / 3.5m.** An earlier tune used
0.28s with a 2.5m stop gap, giving a 9.5m target and 0.38s of headway at
90 km/h. On the road it did not settle: the gap oscillated and ratcheted closed
until the driver had to intervene. The Proton configuration specifies
0.4–0.5s actuator delay. Camera delay and control response also affect the loop;
their combined effect has not been measured from this drive.
`test_one_bar_headway_keeps_minimum_candidate_margin` guards at least 1.0s of
headway from 30 to 110 km/h. That arithmetic check does not prove stability;
`test_proton_longitudinal.py` separately tests the real control code with an
approximate delayed car model. Road validation is still required.

**MPC Constants** (`long_mpc.py`):
| Param | Value | Effect |
|-------|-------|--------|
| `STOP_DISTANCE` | 5.5m | Generated-solver baseline; scoped obstacle offsets are 1.5m for bar 1 and 1.0m for bar 2, giving 4.0m / 4.5m effective stop targets |
| `COMFORT_BRAKE` | 2.5 m/s² | Comfortable decel for gap calc |
| `A_CHANGE_COST` | 200 | Smoothness (high = delays braking onset) |
| One-bar gap penalty | Factor 1.0, cost 10000 | Starts at the full target; other ACC profiles keep factor 0.75, cost 100. Still a soft constraint |
| `LEAD_PERSIST_FRAMES` | 60 | X50 FL ghost lead for 3s at the 20Hz planner rate |

**Rate Limiter** (`carcontroller.py`):
| Direction | Per frame (50Hz) | Per second |
|-----------|-----------------|-----------|
| Throttle | +0.25 at 0 m/s to +0.40 at 33 m/s | +12.5/s to +20/s |
| Planned slowdown / brake | Immediate requested decrease | No added controller delay |
| 1-bar stock brake blend | -0.45 to -0.85; urgent is immediate | Speed-dependent |

**Stock Blending** (`carcontroller.py`):
- X50 FL / S70 1 bar: mild stock gap-nagging does not suppress throttle; real braking blends below a speed-dependent -8 to -14 CAN threshold.
- X50 FL / S70 1 bar: urgent stock braking passes through immediately at the speed-dependent -16 to -22 CAN hard override.
- Bars 2/3 and other Proton platforms retain the original low-speed average and road-speed stock cap.
- X50 FL / S70 stop-and-go automatic RES delays are 0.5s / 1.5s / 3.1s for bars 1 / 2 / 3. Other platforms keep 3.1s.

**X50 FL / S70 stopping** (`interface.py`):
| Param | X50 FL / S70 | Other Proton platforms |
|-------|---------------|------------------------|
| `stopAccel` | -1.0 m/s² | -0.8 m/s² |
| `stoppingDecelRate` | 0.4 | 0.3 |
| `startAccel` | 1.2 m/s² | 1.2 m/s² |

**Stock ACC Blending** (`carcontroller.py`):
```python
mult = interp(vEgo, [0, 28.3], [1.0, 0.6])  # scale down at speed
stock_scaled = stock_acc_cmd × mult
if x50_fl_one_bar and stock_scaled <= hard_override:
    accel_cmd = min(stock_scaled, accel_cmd)    # immediate urgent stock brake
elif not x50_fl_one_bar:
    accel_cmd = original_release_blend(stock_scaled, accel_cmd)
```

### Branch Objectives (`release_ka2_x50_fl`)

| # | Objective | Status |
|---|-----------|--------|
| 1 | One-bar-only close follow | ⚠️ 0.28s + 2.5m was road-tested and rejected: the gap oscillated and ratcheted closed. Now 0.90s + 4.0m (26.5m at 90 km/h); device validation pending |
| 2 | Ordered bar targets | Bar 2: 30m at 90 km/h, 4.5m stop target, 1.5s resume; bar 3 takes old bar 2 settings. Local candidate; device validation pending |
| 3 | Responsive traffic-jam resume | ✅ 0.5s one-bar automatic RES; device validation pending |
| 4 | Stable camera lead | ✅ Relative-motion persistence for 60 frames / 3s; replay validation pending |
| 5 | Curve speed | ❌ Removed by user request |

### Tuning Lessons

1. **Avoid added delay on planned braking** — retain the throttle ramp and stock brake blend; the planned brake request controls both onset and release
2. **Change one parameter per test** — T_FOLLOW + accel + rate limiter are coupled
3. **Add instrumentation first** — debug logger should be commit 1, not commit 4
4. **Keep a stock brake safety layer** — ignore only mild one-bar gap nagging; blend real braking and retain the hard override
5. **Camera-only needs correctly timed lead persistence** — use relative motion and the real 20Hz planner interval
6. **Asymmetric rates** — bounded throttle and faster braking match human expectations
7. **Limit approach-target movement** — the boost responds to closing speed or lead braking. Its interpolation is continuous at the closing-speed threshold. The 0.20s cap reduces target movement, but has not been proved to resolve the reported road oscillation
8. **Custom stock blending stays one-bar-only** — the user changed X50 FL bar 2/3 gap and resume settings on 2026-09-10. Their stock blend stays original; other vehicle profiles stay unchanged
9. **Do not delay or prolong planned braking** — pass planned brake onset and release through. Return to zero before ramping positive throttle. Smooth stock brake release only while stock still requests braking below its threshold; urgent stock braking stays immediate
10. **User wants one bar close and responsive** — traffic-jam and moving follow use the same isolated custom profile
11. **Do not retune closer from gap maths alone** — the earlier 0.38s headway was associated with reported shrinking-gap oscillation. Keep the candidate margin until recorded-drive and delayed-loop evidence supports any further tuning; a numeric headway alone is not a stability guarantee
12. **Stock ACC opinion is a gap preference, not a hazard signal** — its command tracks closing speed, and `aLeadK` reads 0.00 on this camera-only car. Never let it gate throttle; use it only as a deep brake floor

### Local one-bar following fixes — 2026-09-05

- Reproduced in `CarController.blend_longitudinal_command`: a -18 CAN brake request after +12 CAN throttle kept positive throttle for 0.46s, with output still only -13 CAN after 1s.
- One bar now passes planned brake onset and release through. A one-frame planned brake no longer gains a 480ms release tail. Positive throttle resumes through zero and retains its ramp. Active stock braking still limits release, and urgent stock braking stays immediate. Bars 2/3 keep the release blend.
- Tiny negative commands such as -0.1 CAN encoded as zero but still selected brake mode. Moving one-bar commands now choose motion mode after matching CAN integer rounding; fractional throttle state and stop/resume flags remain unchanged. Native tests check all three encoded command signals around zero. Actual brake-light behavior remains unverified.
- The native delayed-loop test exposed a simulated collision when a lead stopped from 5 m/s at 1 m/s² with `aLeadK=0`. One-bar ACC now penalizes using the full target gap (factor 1.0, cost 10000), instead of starting at 75% of the target with cost 100. The same case now retains about 3.85m. Other profiles and acceleration/jerk smoothing costs are unchanged.
- Native validation runs in an isolated ARM Linux container on the Mac, using the existing generated MPC solver plus the real Proton PID and CAN packer/parser. All 88 focused tests pass, covering brake onset/release, stock-threshold crossings, packed motion-mode flags, steady follow, lead slowdown/stops, no-lead cruise and camera dropout. Unexpected solver resets fail the simulation.
- The stronger gap penalty can slow catch-up after a lead slowdown. The test checks convergence over 100s and braking during the slowdown. Broader stop cases retain as little as about 1.73m, so this is not a guarantee of holding the nominal 4m gap or avoiding every collision.
- The simulated car uses a linear CAN-to-acceleration mapping, 0.4/0.5s command delay, 0.15s response time and 0.1s lead-sensor delay. It assumes zero stock commands in the dynamic cases; separate controller tests cover stock blending. These assumptions have not been fitted to drive logs and do not prove brake-light behavior or road safety.
- The existing 0.90s / 4.0m one-bar gap changes remain a candidate awaiting device validation. The dongle is unreachable; no deployment was performed.

### Local bar 2/3 changes — 2026-09-10

- User requested bar 2 targets of 30m at 90 km/h, 4.5m at a stop, and 1.5s automatic resume. This uses `T_FOLLOW=1.02s`: `25 m/s × 1.02s + 4.5m = 30m` at equal lead/ego speeds.
- Bar 3 takes the old bar 2 settings: 1.25s follow time, 5.5m stop target, 36.75m at 90 km/h, 3.1s resume, and the old standard acceleration smoothing factor of 0.5.
- Scoped to X50 FL / S70. Bar 1, other vehicle profiles, stock braking/blending, and the one-bar-only stronger gap penalty are unchanged.
- One bar can temporarily ask for more space than bar 2 during an approach. Preserve that extra margin; do not lower the one-bar boost to force bar order. Steady-speed targets remain ordered.
- Regression checks cover native MPC follow-time and obstacle-offset inputs, smoothing costs, exact automatic-resume frames, and the Following Lab target display. The existing delayed one-bar tests still run. The simulator holds stock ACC at zero, so it cannot validate real bar 2/3 catch-up or resume behavior.
- Validation: 114 tests passed (90 controller/planner tests plus 24 Following Lab tests). Syntax and whitespace checks pass; lint reports only the four existing findings.
- No commit, push, or dongle deployment was performed. These are target settings, not guaranteed road gaps.

Run the focused native suites on a supported Linux runtime:

```bash
python -m pytest selfdrive/car/tests/test_proton_following.py selfdrive/controls/tests/test_following_distance.py selfdrive/controls/tests/test_proton_longitudinal.py -q -n0 -W ignore::ResourceWarning
```

## Project Structure (Key Directories)
```
├── cereal/              # Messaging spec and serialization libs
├── common/              # Shared library code
├── installer/updater/   # Auto-update manager
├── models/              # Neural network models
├── opendbc/             # CAN signal database (DBC files)
├── panda/               # CAN bus communication firmware (DO NOT TOUCH)
└── selfdrive/           # Main application code
    ├── assets/          # Fonts, images, sounds for UI
    ├── athena/          # App communication
    ├── boardd/          # Hardware daemon (panda bridge)
    ├── camerad/         # Camera capture
    ├── car/             # Car-specific code ← YOU WORK HERE
    │   └── proton/      # Proton X50 specific code
    ├── controls/        # Planning and control logic
    ├── locationd/       # Localization
    ├── loggerd/         # Data logging
    ├── modeld/          # Neural network inference
    └── ui/              # Touchscreen UI
```
