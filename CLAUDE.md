# CLAUDE.md — Bukapilot (KommuAssist) Development Guide

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
- **Hardware:** KommuAssist2 dongle running a stripped-down Linux OS
- **Target vehicle:** Proton X50 FL
- **App version:** KommuApp 1.0.14 (Build 89)
- **Bukapilot version on device:** 10.0.5-release
- **OS on device:** 11.3.2

## Device Details

- **Dongle ID:** `9fcbe17abd7b08d8`
- **Device Wi-Fi IP:** `192.168.0.64`
- **Hotspot IP:** `192.168.69.1`
- **Network:** Wi-Fi (SSID: Lara)
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
ssh kommu@192.168.0.64
# or if using a specific key file:
ssh kommu@192.168.0.64 -i ~/.ssh/id_ed25519
```

Device and development machine must be on the same Wi-Fi network.

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