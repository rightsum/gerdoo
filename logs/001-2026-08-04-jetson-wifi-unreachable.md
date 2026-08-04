# 001 — Jetson unreachable over wifi (`<robot-ip>`)

| | |
|---|---|
| **Date opened** | 2026-08-03 |
| **Date resolved** | 2026-08-04 |
| **Time to diagnose** | ~25 min |
| **Status** | ✅ Fixed — monitoring for recurrence |
| **Severity** | High — no remote access to the robot's brain |
| **Hardware** | Jetson Orin Nano (`jarvis`), Ubuntu, ROS 2 Humble |

---

## Symptom

SSH to the Jetson at its known wifi IP timed out:

```
ssh: connect to host <robot-ip> port 22: Operation timed out
```

The board was physically powered and running — the Teensy 4.1 hanging off its USB port was blinking, which meant USB 5V was present, which meant the Jetson had power. So this was never a dead board.

## What the evidence actually said

| Test | Result | Reading |
|---|---|---|
| `ping <robot-ip>` | 100% loss | unreachable |
| `arp -an \| grep .173` | `(incomplete)` | **no MAC resolved** — layer 2 failure |
| `ping <gateway>` (gateway) | 3ms, 0% loss | network itself healthy |
| Full sweep `.1–.254` | `.173` absent | not a DHCP move |
| `ssh-keygen -F <robot-ip>` | hit at `known_hosts:38` | had connected before, so IP + user were right |
| `ping jarvis.local` | resolved to `.173`, no reply | stale mDNS cache |

`(incomplete)` in ARP is the important one. It means the Mac broadcast *"who has <robot-ip>"* and nothing answered. That is a layer 2 silence, not a routing or auth problem.

### Wrong turn worth recording

A ping sweep found `<lan-ip>` and `.44` with MAC prefix `d8:3a:dd` and SSH open. I read that OUI as NVIDIA and guessed the Jetson had changed IP. **Wrong** — `d8:3a:dd` is Raspberry Pi Ltd, the banner was `SSH-2.0-OpenSSH_9.2p1 Debian-2+deb12u3`, and both IPs shared one host key. It was the `rspb` Pi already in `~/.ssh/config:11`. Two consecutive MACs on one board is a wired+wifi pair, not two devices.

**Lesson:** confirm an OUI against the SSH banner and host key before acting on it.

## Getting back in — the USB fallback

The Jetson Orin Nano's USB device-mode port exposes a virtual ethernet gadget. It was already live and completely independent of wifi:

| | |
|---|---|
| Mac side | `en21` = `192.168.55.100` |
| Jetson side | `l4tbr0` = `192.168.55.1` |
| Latency | 1.2 ms |
| Serial console | `/dev/cu.usbmodem14237250993873` |
| USB descriptor | `NVIDIA / Linux for Tegra` |

```bash
ssh user@192.168.55.1   # worked immediately, key auth intact
```

**This path does not depend on wifi, DHCP, or the router.** It is the permanent way back in when the network drops.

## Root cause

From inside the box, wifi was *fine*:

```
wlP1p1s0   UP   <robot-ip>/24
default via <gateway> dev wlP1p1s0 proto dhcp metric 600
nmcli: wlP1p1s0:wifi:connected:<your-ssid>
```

Connected, correct IP, correct route. Then the decisive test:

| Direction | Result |
|---|---|
| Jetson → gateway | 0% loss, 3.2 ms |
| Jetson → internet (`1.1.1.1`) | 0% loss, 16 ms |
| **Jetson → Mac (`.190`)** | **0% loss** |
| **Mac → Jetson (`.173`)** | **100% loss** |

Traffic flowed one way and not the other. A device that can reach you but that you cannot reach has not left the network — it has **stopped answering unsolicited packets**.

And the moment the Jetson pinged outward, the Mac's ARP entry populated (`<jetson-wifi-mac>`) and Mac→Jetson started working. Nothing was reconfigured in between. That is the signature of wifi power save.

Confirmed:

```
$ iw dev wlP1p1s0 get power_save
Power save: on

$ grep -rn powersave /etc/NetworkManager/
/etc/NetworkManager/conf.d/default-wifi-powersave-on.conf:2:wifi.powersave = 3
```

**Cause:** Ubuntu ships `wifi.powersave = 3` (enabled) by default. The wifi driver is **`rtl88x2ce`** (Realtek RTL8822CE) — known for aggressive power save where the card stops responding to ARP and inbound packets while idle, while anything the host itself initiates still works.

Supporting numbers:
- Signal `-54 dBm` — strong, so not a range problem
- Uptime 17 h with nothing talking to it — maximum idle, exactly when the card goes deaf
- Ping jitter 8 → 86 ms in a single 3-packet run — the radio waking up mid-run

## Fix

```bash
sudo sed -i 's/wifi.powersave = 3/wifi.powersave = 2/' \
  /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf
sudo systemctl restart NetworkManager
```

`2` = disabled, `3` = enabled.

## Verification

```
$ iw dev wlP1p1s0 get power_save
Power save: off

$ ping -c 20 -i 0.3 <robot-ip>
20 packets transmitted, 20 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 5.285/17.438/85.257/22.591 ms

$ ssh user@<robot-ip> 'hostname'
jarvis
```

Inbound SSH restored. **Caveat: 0% loss proves the fix on an active link, not on an idle one.** Power save only bites after minutes of silence, so the real test is item **A2** in the action plan — leave it idle 2 h, then connect cold.

Residual: stddev 22.6 ms with a 85 ms max is still high for a 5 ms floor. Not power save — it's 2.4 GHz congestion. See **A3**.

## Link state at time of fix

| | |
|---|---|
| SSID | `<your-ssid>` |
| BSSID | `<router-bssid>` (Fritz!Box; gateway MAC `<gateway-mac>`) |
| Channel / freq | 1 / 2412 MHz — **2.4 GHz** |
| Signal | −54 dBm |
| RX / TX bitrate | 78.0 / 156.0 Mbit/s, VHT-MCS 4/8, NSS 2 |
| Jetson wifi MAC | `<jetson-wifi-mac>` |
| Driver | `rtl88x2ce` |

## Takeaways

1. **`(incomplete)` in ARP = layer 2, not layer 3.** Don't debug routing or SSH keys until a MAC resolves.
2. **Asymmetric reachability points at the sleeping end**, not at the network. One-way ping is the single most useful test here.
3. **Keep the USB fallback wired.** `192.168.55.1` survives every wifi failure and cost nothing to have available.
4. **Verify an OUI against the SSH banner** before believing a MAC prefix.
5. Ubuntu's default `wifi.powersave = 3` is wrong for any always-reachable robot, doubly so on Realtek.

## Follow-ups

Tracked as **A1–A4** in [`../ACTION-PLAN.md`](../ACTION-PLAN.md).

## Related

- Found during the same session: Teensy 4.1 enumerating as `16c0:0486` (RawHID) with no `/dev/ttyACM*`. Separate issue → log `002`.
