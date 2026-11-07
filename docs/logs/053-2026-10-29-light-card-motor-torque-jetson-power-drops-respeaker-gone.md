# 053 — Light card, motor torque, two Jetson power drops, the reSpeaker vanishes

| | |
|---|---|
| **Date** | 2026-10-29 (plus the evening of 2026-10-28) |
| **Type** | Feature + Q&A + problems |
| **Status** | ✅ Panel "Light" card deployed, 202 tests · ✅ Torque margin 4–10× · ⚠️ Jetson hard power-offs, cause unknown · ⚠️ reSpeaker gone from USB (back on 10-30, log 054) · ✅ Dock sign re-sliced with normal supports |
| **Severity** | Medium |

---

Written on 2026-11-07 from the session transcript. The same day's dock stop pads (log 045), display retainer (log 042) and reactor screen (log 047) are logged already; the extras are at the end.

## 1. The "Light" card on the control panel

**Request:** "give me an option on the panel to test the light as well, with the light sensor and without it".

**Firmware** (`teensy_microros.ino`, flashed with `make upload`):
- `sendLight()` now ends with `level=<manual level 0..1, or -1 in auto>`.
- `FW_VERSION` wasn't bumped.
- Check line: `LIGHT raw=1105 norm=0.661 cal_dark=529 cal_bright=1400 duty=361/4095 (cap of 4095) mode=auto level=-1.00`.

**`robot-face/teensy.py`:**
- `parse_light()`, which accepts older firmware without `level=`;
- `light_state()`;
- `light_set(level)`, sending `STRIP auto` or `STRIP <0-100>`;
- `light_calibrate(which)`, sending `CAL dark|bright`.

**`robot-face/app.py`:** `GET /api/light`, `POST /api/light` (`{"mode":"auto"}` or `{"level":0-100}`, otherwise 400) and `POST /api/light/calibrate` (`{"which":"dark"|"bright"}`). Session tier, no password: a light is harmless.

**`templates/control.html`:** a "Light" card under Audio:
- Follow sensor;
- brightness slider 0–100 %, Off, Full;
- live bars for the sensor and the strip duty;
- Set dark / Set bright (held until the Teensy restarts);
- polls once a second.

**Verified:**
- `tests/test_light_routes.py` is new; **202 passed** on the Jetson.
- Deployed.
- `/api/light` returned `{"cal_bright":1400,"cal_dark":529,"duty":0,"level":null,"mode":"auto","sensor":1.0,"sensor_raw":2252}`.
- **Open:** no feedback from the user yet.

## 2. "Are the motors strong enough to handle the weight of the robot?"

From `sim/web/tools/physics.py`: about 5.7 kg robot, 65 mm wheels, 2 driven.

| Case | Force | Torque per wheel |
|---|---|---|
| 0.5 m/s² on the flat | 4.5 N | **0.8 kg·cm** |
| 0.5 m/s² up 5° | 9.3 N | **1.6 kg·cm** |
| 0.3 m/s² up 10° | 12.9 N | **2.2 kg·cm** |

**Supply:**
- The 36GP-555 (12 V, 160 rpm) listing gives **8 kg·cm at rated load, ~125 rpm (~0.43 m/s)**. Stall torque isn't published.
- That's a **4–10× margin**. Grip is the limit, not torque (log 040).

**Before driving on the floor:**
- Raise the 30 % test cap. 15 % (about 1.8 V) is below the gearbox friction, so real driving needs 30–60 %.
- **Loose end:** the listing's 1:50 gearbox means ~3,400 encoder counts per wheel turn. The hand turns gave 366 and 480. Either those weren't full turns or the gearbox is different. Still open.

## 3. The Jetson lost power twice

| Time | What happened |
|---|---|
| 09:36 | ssh: `Host is down`; the USB link at 192.168.55.1 timed out |
| 09:39 | Back: `up 0 min`, clock stale (`21:44:12`) |
| ~09:42 | Gone again right after `deploy.sh` printed "Done" (`Operation timed out`) |
| 09:48 | Back after ~260 s: `09:41:16 up 0 min` while the Mac said ~09:48 |

- `last -x` showed two "reboot … still running" entries and **no shutdown records**: **hard power-offs**.
- **The boot time is unreliable:** the Jetson has no RTC battery, so a boot after power loss is stamped with the last saved clock. The "Oct 28 21:43" boot entry was really 09:39.
- **The battery file at 09:48:**
  - `main_battery 0.0 V / 0 %`: the sensor wasn't wired to the pack yet;
  - `jetson_battery 12.28 V / 91 %`.
- **Again on 2026-10-30 at 13:58:** found freshly booted (`up 0 min`). The user didn't say whether they'd restarted it.
- **Cause unknown.** On 2026-11-06 the 45 W supply was found to switch off under the combined charge load (log 056). Nobody checked whether that was behind these drops.

**The evening before (2026-10-28, 21:25–21:38):**
- **The user:** "i feel like jetson is not recognizing the cable charging connected to it and only works with batteries".
- **The UPS INA219** (bus 7, 0x41) read **12.272 V, shunt 0.00 mV, 0 mA**, flat for 10 minutes. `VDD_IN` was 4992 mV and the Teensy read `main_v=0.000`.
- The plug/unplug test wasn't done, so it stayed unanswered. **Nothing in the software watches for a charger.**
- `battery_bridge.py` reads only INA219 register 0x02. Its docstring says reading other registers on bus 7 "caused a system reboot in testing". Reading 0x01 (the shunt) on 2026-11-06 and 11-07 caused no reboot.

## 4. The reSpeaker disappeared from USB

**Request:** "record for 5 seconds and play it back … like 4 times with a beep in between".

**`lsusb` showed only:**
- the internal Realtek hubs;
- Bluetooth;
- the Teensy (`16c0:048b`).

**Not there:**
- the reSpeaker (`2886:001e`);
- the lidar;
- the arm cameras.

PulseAudio had only the Tegra APE and HDMI.

**The user tried:**
1. reconnecting it, with the light green;
2. connecting it directly, not via the hub;
3. a different USB-A port.

Nothing enumerated. `dmesg` needs root (`Operation not permitted`).

**Hypotheses:**
- a charge-only cable;
- the XIAO's USB-C instead of the core board's;
- the powered hub being unplugged, since the lidar and cameras were missing too.

It came back the next day (log 054). The cause wasn't recorded.

## 5. Extras to earlier logs

- **Dock stop pads (log 045):**
  - The assistant first took "blocks" to mean the inner rails and told the user to cut both strips off. Corrected 11 minutes later: "If you haven't cut the strips yet, leave them for now".
  - The user's question, "what was the point of adding them in first place…", became a standing rule: minimal, self-supporting prints.
- **Dock sign: normal supports.** The user switched the dock sign's supports from tree to **normal** in Bambu Studio "for stability". The plate was re-sliced: **12 h 25 min, 368 g PLA + 1.6 g PETG, 8 swaps** (log 045 had 12 h 37 min with trees). `make_print_3mf.py` now defaults to `normal(manual)` because trees toppled at the first PETG layer.
- **Display retainer v13 (log 042):** `plate_covers.json` and `plate_back_cover.json` now point at v13. The two cover 3MFs were not regenerated, so they still carry v10; `print/README.md` says to delete it and print plate 11.
