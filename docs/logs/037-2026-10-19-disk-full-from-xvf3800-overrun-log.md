# 037 — Gerdoo went deaf again: the disk filled with 900 GB of USB warnings

| | |
|---|---|
| **Date** | 2026-10-19 |
| **Type** | Incident: root cause and fix |
| **Status** | ✅ Disk freed (100 % → 4 %) · ✅ XVF3800 fully power-cycled: clean audio, overrun flood stopped · ✅ Wake word listening · ✅ Speaker checked · ⏳ rsyslog filter (safety net) waiting for the user's sudo |
| **Severity** | High. The disk was 100 % full, so every service that writes to disk was at risk. |

---

Follows [022](022-2026-09-19-the-robot-went-deaf-silently.md) and [021](021-2026-09-19-kiosk-page-took-the-robot-down.md).

## Symptom

The user reported that "gerdoo is not detecting my voice and does not go to LiveKit mode".

## Evidence, in order

1. **The mic array was gone.** `lsusb` had no `2886:001e`; every other USB device was there. The wake-word service was stuck restarting, and PulseAudio's default source had fallen back to the Brio.
2. **The user re-plugged the XVF3800.** It came back, `gerdoo_mic` was rebuilt and became the default source. The wake word still failed.
3. **Running the wake word's own command by hand** gave `OSError: [Errno 28] No space left on device`.
4. **The disk:** `/` was 916 GB, **100 % used**.
   - `/var/log/syslog` was **456 GB** and `/var/log/kern.log` **453 GB**.
   - Both were one line repeated:
     ```
     tegra-xusb 3610000.usb: WARN: buffer overrun event for slot 5 ep 2 on endpoint
     ```
5. **After the user truncated both logs,** `kern.log` grew again at **~1 MB/s (81 GB/day)**. That's about 11 days to fill the disk, which matches the timeline below.
6. **Which device:**
   - `retire_capture_urb: ~40000 callbacks suppressed` every 5 s points to a USB **audio capture** stream.
   - `/proc/asound/C16K6Ch/stream0` shows the XVF3800 capture running on **endpoint 0x81 IN** at a 125 µs interval: 8000 packets/s, matching the warning rate.
   - In xHCI messages "ep 2" is the endpoint index, and index 2 is EP1 IN, which is 0x81.
   - The driver allows **36 bytes** per packet (6 ch × 16 kHz × 2 B), but the endpoint declares **wMaxPacketSize 192**. Every packet overruns.

## Timeline

| When | What |
|---|---|
| since ≥ 2026-09-19 | The overrun flood exists (log 022, "Still open"). |
| log 021 | `ReadKMsg=no` stops the **journal** from recording kernel messages. **rsyslog still wrote them to `/var/log/kern.log` and `/var/log/syslog`.** Nothing rotated them fast enough. |
| ~2026-10-07 | About when the current logs started filling (900 GB at ~1 MB/s). |
| 2026-10-17 20:28 | Last time the audio-repair watchdog rebuilt `gerdoo_mic` successfully. |
| 2026-10-18 ~08:44 | Disk full. The watchdog's log ends mid-line at 08:56. From here the wake word cannot start at all. |
| 2026-10-18 → 19 | At some point the XVF3800 also dropped off USB. |
| 2026-10-19 09:33 | The user re-plugged the XVF3800. |
| 2026-10-19 09:36 | The user truncated `syslog` and `kern.log`: 847 GB free. The wake word started at 09:37:27, listening on `gerdoo_mic`. |

## Still deaf after the disk was freed: the board was in a bad state

**Symptom:** with the disk freed and the wake word running on `gerdoo_mic`, it still never fired.

**Measured on the raw 6-channel capture:**
- **Every third frame was all zero:** exactly 33.0 %, pattern `xx0xx0xx0…`.
- **A 48-frame dropout about every 12 ms.**
- **Exact peaks:** channel 0's peak was 4096 and channel 1's was 2047. In a quiet room channel 0 read 454 RMS, against **12** in log 018.
- **Effect:** the wake word was hearing speech stretched by 1.5× and chopped up.

**This was new.** The wake word's saved recordings from 2026-10-13 (`hits/*.wav`) have about 1 % zeros and no pattern.

**Fix: a full power cycle of the XVF3800** (USB and any other supply off for 10 s).
- The earlier USB re-plug alone did not reset its chip.

**Afterwards:**
- 0.0 % zero frames, at the full 16 kHz rate.
- Channel 0 at 87 RMS in the room, channels 2–5 at 13–22, in line with log 018.
- **`kern.log` growth dropped from ~1 MB/s to 0.** The "buffer overrun" flood *is* this bad state; it isn't a permanent property of the board or its port. Log 022's flood was probably the same thing.

**Follow-ups:**
- **The audio-repair watchdog should check the stream, not only that the source exists.** For example: blank frames in a 1 s capture, or `kern.log` growing over 100 KB/s, should raise an alert.
- **Automatic power cycle:** if the dev kit's onboard hub supports per-port power switching (`uhubctl`), the watchdog could power-cycle port `1-2.3` itself. Untested.

## Fix

**Done:**
- Truncated `/var/log/syslog` and `/var/log/kern.log`. The user ran this, since sudo needs a password.
- Re-plugged the XVF3800.
- Played `bing.wav` on the XVF3800's output; the user heard it, so the speaker path works.

**Waiting for the user (sudo):** an rsyslog rule that drops just these two messages before they reach the disk.

```bash
ssh -t jarvis@<robot-ip> 'printf "%s\n" "# XVF3800 mic endpoint warns ~8000x/s (logs 022, 037): keep it off the disk" ":msg, contains, \"buffer overrun event for slot\" stop" ":msg, contains, \"retire_capture_urb\" stop" | sudo tee /etc/rsyslog.d/05-drop-xvf3800-overrun.conf && sudo systemctl restart rsyslog'
```

## Still open

- **The overrun itself.** The board works and the wake word hears through it. But the kernel still formats about 8000 warnings a second, which costs CPU, and log 022 suspects the same fault is behind the board's re-enumerations.
  - **Topology:** the board is on one of the dev kit's own Type-A ports (`1-2.3`, behind the onboard Realtek hub). The only port not behind that hub is the Type-C, `1-1`, where the Brio is.
  - **Leads:** a snd-usb-audio quirk for `2886:001e` (kernel 5.15.148-tegra), the XVF3800's 2-channel firmware, or the Brio and XVF3800 swapping ports.
- **A disk-space alarm.** Nothing warned while 900 GB filled over 11 days. The panel should show free disk space, and the watchdog should log loudly below 10 %.

## Takeaways

- **Silencing one logger is not silencing the message.** journald and rsyslog both read the kernel log. Check every consumer, and check the disk, when a flood is "handled".
- **"Deaf" had two causes stacked:** the board was missing *and* the disk was full. Re-plugging fixed the first and revealed the second. Run the service's own command by hand: the error was right there.
