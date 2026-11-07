# 041 — Front cover: the display plug, colour inlays, and printing it standing without supports

| | |
|---|---|
| **Date** | 2026-10-20 |
| **Type** | Design changes + print setup |
| **Status** | ✅ `front-cover-v1` v7 · ✅ `gerdoo_covers_A1.3mf` (front + back covers, display retainer, LDR cradle v7): 8 h 49 min, PLA only, 0 swaps · ⚠️ `back-cover-v1` read-only: gussets unsaved · ✅ Gold-ring and silk-pad inlay plates · ⏳ Not printed |
| **Severity** | Medium: the display cable couldn't be plugged in, and the first slice had 252 swaps |

---

Follows [030](030-2026-10-16-front-and-back-covers-and-the-cable-plan.md) (cover design), [039](039-2026-10-20-3rd-floor-cable-slot-and-extension-grid.md) (sensors moved to the 3rd floor) and [033](033-2026-10-17-printing-the-1st-layer-on-the-a1.md) (print rules).

## Changes to `front-cover-v1`

| Change | Why |
|---|---|
| **LDR hole + sleeve suppressed** | The light sensor now sits on the 3rd floor (log 039). |
| **Retainer cable notch:** the display retainer's 19.5 × 25 window now runs down to the plate's bottom edge, 12.8 wide | The user doubted the screen could be plugged in, and was right. Waveshare's drawing shows a **side-entry GH1.25** about 6.6–17.4 mm above the board's bottom edge, with the plug entering parallel to the board from below. The plug and wires sat under the retainer's bottom band, where the plate would hit them by about 0.8 mm. The two lower screw holes keep 4.6 mm of wall. |
| **Coil pads → inlays** (the user's colour request) | The 12 raised pads (1.0 proud) become **0.8 mm pockets** in the bowl floor, with 3.2 mm of plastic left in front of the mics. Separate **pads 1.8 thick, 0.1 mm smaller all round**, print in the user's tri-colour silk and sit 1.0 proud, as before. |
| **Reactor ring → gold inlay** | The ring lip (r 38.6–43.5) is cut down to z 128, and the 1.4 mm step at the inner edge locates the ring. **Gold ring: ID 77.5, OD 86, 3 thick**, face at z 131 as before. |
| **Mic cup: 45° roof** | The cup (Ø74, its axis horizontal when the cover stands) had a round top that needed support on about 80 layers. A 45° roof from ±45° up to the 3rd-floor band (already open) makes it self-supporting. Hidden; the ring seat is untouched. |
| **Cup shelf: 45° underside** | The 6 mm shelf over the 2nd-floor band, behind the ring, is cut at 45°. |
| **KA009 cradle: 45° gusset** | Its flat underside stuck out 6.5 mm from the shell. A triangular gusset now runs back to the shell. |

**Why inlays instead of printing the colours in place:** the cover prints standing, so the pads and ring would cross many layers, each needing extra colour swaps. As separate flat parts they print in one colour each.

## Printing: standing as mounted, PLA only, no supports

**Slices that didn't work:**

| Supports | Time | Swaps |
|---|---|---|
| Auto, from the bed, PETG interface | 17 h 43 min | 252 |
| Threshold 30° / 20° / 15° | 15 h 29 / 13 h 4 / 12 h 16 | 190 / 100 / 72 |
| Manual enforcers on the cup, pocket and notch | 19 h 43 min | 312 |
| From the bed after the cup roof, threshold 40° / 25° | — | 244 / 138 |

**Why they failed:** the raised details on the curved face, and the cup's round top, have sloped or curved undersides. A PETG interface on those puts swaps on almost every layer. Supports were the wrong tool for this part.

**What worked:** finding the regions that really float, using a voxel check (`sim/web/tools/check_floating.py`: no material within 45° below), and fixing them in the geometry, as above.

**What's left, measured on the faces (the user asked whether the cover needs support):**
- **Display pocket ceiling:** a flat **20.8 mm bridge** between r 5.5 rounded corners, hidden behind the display.
- **Visible window top edge:** a **45° bevel** plus a 0.6 mm flat lip, so self-supporting.
- **KA009 slot ceiling:** 12 mm bridge, hidden.
- **Face ledges:** 2 mm or less.

Bambu still prints a "floating regions" warning for these; they print fine. **No support needed.**

**Test:** supporting only the window and pocket region (manual enforcer, PETG interface) gave **120 swaps**, 12 h 40 min. The pocket's rounded corners and the window bevel are curved and sloped, which again puts the interface on many layers. Rejected.

**Plate (`plate_front_cover.json`):**
- **Parts:**
  - the cover, standing, its arc running along the bed's moving axis so the bed's motion doesn't rock the thin wall;
  - the display retainer, flat;
  - the DHT22 holder v3.
- **Brim:** 6 mm outer brim, because the cover stands on only 225 mm².
- **Slice:** **6 h 28 min, 108.4 g PLA, 0 filament changes**.

**Inlay plates:** load the right filament before printing.
- `gerdoo_gold_ring_A1.3mf`: 16 min, 3.6 g.
- `gerdoo_coil_pads_A1.3mf`: 12 pads, 11 min, 0.8 g.

## DHT22 holder v3 (the v2 failed on the 3rd-floor plate)

**Why v2 failed:** its rails were 4 × 6 mm with about 2 mm lips, 22 mm tall, in a corner of the bed.

**v3 (`sensor-mounts-v1` v3):**
- posts 4 × 8, so 3 mm lips;
- 16 mm tall, with a lead-in notch at the top of each groove;
- 2 mm root fillets;
- the board sits 1 mm further out (x 41) to clear the speaker cap. The pin row is still inside the Ø11 pass-through.
- No collisions in the preview.

## Assembly: the display stack, back to front

1. **Plug the GH1.25 cable into the display first**, outside the robot.
2. Drop the display, glass first, into its pocket from behind.
3. Fit the retainer over the back:
   - the cable runs out through the new notch;
   - 4 × M2×4 into the display's standoffs;
   - 2 × M2×6 into the posts.
4. Fit the mic ring into the cup around it:
   - 3 × M3 self-tapping screws;
   - the ring's FPC goes out through the bottom notch.

   The display cable goes straight back through the ring's centre.
5. Press the gold ring and the 12 silk pads into their pockets, with a drop of CA glue if they're loose.

**The cover's 6 counterbored holes:** M3 button heads into the radial inserts in the floors.

| Floor | Height | Angle either side of the front |
|---|---|---|
| Deck | y −5 | ±18° |
| 2nd floor | y 82 | ±30° |
| 3rd floor | y 166 | ±23° |

## Fusion: why saves didn't stick (logs 039, 041)

**The cause:** a copy that a linked assembly (the preview) loads is **not a top-level document**. `isUpToDate` raises "should be used in a top-level document". Edits to that copy can't be saved on their own; the save call still reports success.

**The rules now:**
- Open the file itself (`documents.open(file, True)`) and edit that copy.
- Check `dataFile.versionNumber` after every save.
- Point the preview at the new version afterwards.

**What it cost:** the first round of cover edits was made on a linked copy and had to be replayed on a top-level one.

## Correction: the LDR cradle failed, not the DHT22 holder

**What happened:** on the 3rd-floor plate, the part that printed badly was the **LDR cradle v6**. The DHT22 holder v2 printed fine, so v3 isn't needed, although the CAD now shows v3.

**LDR cradle v7 (`sensor-mounts-v1` v4):**
- Both side walls are now **2.0 mm**. v6's wall on the speaker-cap side was 1.2 mm.
- The board moved 0.8 mm outward, to x −41.3, so the gap to the cap is unchanged. The bent pins are still inside the Ø11 pass-through.
- **Collisions:** none in the preview (v38).

**Front-cover plate:**
- The DHT22 holder is replaced by the LDR cradle, printed **mid-bed**: retainer at (160, 70), cradle at (160, 140). v6 had sat in a bed corner.
- **Slice:** 6 h 23 min, 108.6 g, 0 changes.

## The back cover joins the plate (the user asked)

**`back-cover-v1` is still current:**
- 175 × 96 × 39 mm, 43.5 cm³.
- Dock contact area with the pogo sleeves at x ±20, the DC jack between them, gill vents, and a decorative dial boss (the potentiometer was dropped in log 032).
- It clears the moved hub and the antenna bracket, as checked in log 038.

**Printing it standing:**
- **The real problem:** the two **pogo sleeves** (Ø9.6 tubes, axis horizontal, 10 mm into the cover) started in mid-air.
- **Fix:** a **3 mm wide 45° gusset** under each sleeve, from the sleeve's end down to the shell, at x ±19.9.
- **What remains:** small bridges (DC-jack hole top 7.5 mm, the sleeves' inner tops 5.6 mm) and the dock area's 2.5–3 mm outer ledges. Bambu no longer flags the back cover.

**Plate `gerdoo_covers_A1.3mf`** (replaces `gerdoo_front_cover_A1.3mf`):
- **Parts:** front cover standing at X 60, back cover standing at X 125, retainer at (200, 70), LDR cradle v7 at (200, 150).
- **Spacing:** at least 25 mm between parts.
- **Slice:** **8 h 49 min, 159.9 g PLA, 0 changes**. Only the front cover's expected "floating regions" warning.

**⚠️ `back-cover-v1` is read-only in Fusion**, so the gussets can't be saved yet.
- **Status:** the document was flagged read-only from the start of the session. It's locked, or open for editing on another device.
- **What's waiting:** the gussets are in the open copy and in the print file.
- **To save them:** unlock the file (Data panel → Unlock, or close it elsewhere), then save. Or replay the two gussets: triangle (y 17.4, z −125) / (17.4, −115) / (7.4, −125) on planes at x 18.42 and −21.42, extruded 3 mm and joined.

## Back cover on hold: the pogo pin sleeves (2026-10-21)

**The user's catch:** the pogo pins aren't as big as the holes suggest, and an adapter looked necessary.

**Why:**
- The sleeves were sized from the listing's "Ø5.5": a plain **Ø5.6 hole** through the face, plus a 10 mm tube behind it.
- Only the length (19.9) and the plunger tip (Ø3.4) were ever measured.
- No datasheet exists online for GF55-17770-3533.
- **There is also no axial stop:** docking would push the pins back into the robot.

**Plan, waiting for the user's caliper numbers** (barrel Ø, any collar, plunger stick-out, tail end):
- face hole for the plunger only, about Ø3.8;
- sleeve snug on the barrel, so the barrel bears on the face;
- a stop behind each pin.

**Meanwhile:**
- `gerdoo_covers_A1.3mf` is withdrawn.
- `gerdoo_front_cover_A1.3mf` is back: front cover, retainer and LDR cradle. 6 h 23 min, 108.6 g, 0 changes.

**The real pin (vendor drawing, RTLECS H214 5A):**
- Plunger Ø2.5, about 7.5 mm long.
- Body Ø3.5 × 10.2, up to a **Ø5.5 collar at the tail end**; "5.5 mm" was the collar.
- Tail Ø3.5 × about 2.5, grooved.
- Free length 21. The user's 19.9 had the spring squeezed by the caliper, so it travels at least 1.1 mm.

**How it mounts:** from inside. The body goes through a **Ø3.7 bore**, and the collar stops against the back of the sleeve (with a seat). The sleeve length sets how far it sticks out.

**Space behind the pins:**
- The shell is r 125.6–128; the dock floor is r 127.2, so z −125.63 at x ±19.92.
- The 3S2P holder (listing size, model) starts at **z −109.8**, about 14 mm behind the cover's inner face.
- At 4.9 mm protrusion the tail ends at z −109.5, which hits the holder, with no room for the wire.

**Options:**
- **A.** About 8.5 mm protrusion, with the dock's plate pockets moved 3 mm deeper; leaves ~3.3 mm for wires.
- **B.** Measure the real holder gap; ≥ 18.5 mm from the deck's back edge at x ±20 needs no change.
- **C.** Raise the dock interface above the holder.

**Status:** waiting on the user's measurement, and on whether the dock is printed.

**Fusion:** the user unlocked `back-cover-v1`. The read-only copy that held the unsaved gussets was closed; replay them together with the new sleeves.

## Pogo pins fixed: back cover v7, dock stop pads moved (2026-10-21)

**Decision:** the battery holders haven't arrived yet, but they'll sit behind the pins, and the dock isn't printed. So option A.

**`back-cover-v1` v7:**
- Old pogo holes, sleeves and gussets suppressed.
- **New:**
  - sleeves OD 9.6 from z −124.69 to **−116.13**;
  - a **Ø3.7 bore** through face and sleeve;
  - a **Ø5.9 × 0.8 collar seat** at the back of each sleeve;
  - **45° gussets** under the sleeves, from y 17.4 down to the shell.
- **Pin position:** tip at z −134.63, **9.0 mm past the dock floor**. The collar sits at −116.93. The tail ends at **−113.63, 3.8 mm in front of the battery holder** (listing size, z −109.8).
- **Floating check:** only small bridges and the dock area's ledges.

**`charging-dock-v1` (saved as v9 once the user unlocked it):**
- Deepening the plate pockets would have left 0.5 mm of wall: the pocket floor is at z −131.35, and the hollow with the bolt spot-faces is at −135.35.
- **Instead:**
  - the **stop pads' contact faces move 2.74 mm** inward (r 128.6 → **125.86**). At their ±38° that's the robot parking **3.48 mm further out**, and the robot's shell keeps the same 0.6 mm to the pads.
  - the **presence-switch pocket floor comes up 3.48 mm** (z −138.5 → −135.02), so the KW11's lever still reaches the robot.
- **Result:** the plates stay put, and the pins compress them **about 1.3 mm**.
- **To replay the changes:**
  1. Offset the two r 128.6 cylinder faces by +2.74 mm.
  2. Join a box x ±10.5, y ±5.5, z −138.5 to −135.02.

**Print files:**
- `gerdoo_covers_A1.3mf`: both covers, retainer and LDR cradle. 8 h 50 min, 160.0 g, 0 changes.
- `gerdoo_back_cover_A1.3mf`: back cover alone. 2 h 53 min, 51.4 g.
- `gerdoo_front_cover_A1.3mf`: kept, in case the front is printed first.

## Mic ports enlarged (the user asked)

**The problem:**
- The 4 ports were **Ø1.6 × 4 mm**.
- Printed standing, they're horizontal, so they'd come out about Ø1.2–1.3, possibly partly closed. That means lower sensitivity and **unequal mics**, which hurts the XVF3800's direction-finding and beamforming.

**`front-cover-v1` v8:**
- Ports now **Ø2.2**, z 125.4–128.9.
- **0.5 mm chamfer** at the outer bowl floor, to Ø3.2.
- They stay clear of the pad pockets (15°, about 5 mm), the ring screw pilots (about 24 mm) and the gold ring.
- The 4 mm tube's resonance stays near 21 kHz, above the XVF3800's 8 kHz band.

**Plates re-sliced:**
- `gerdoo_covers_A1.3mf`: 8 h 50 min, 159.9 g, 0 changes.
- `gerdoo_front_cover_A1.3mf`: 6 h 23 min, 108.6 g, 0 changes.

**`charging-dock-v1` v9 saved** after the user unlocked it: stop pads and switch pocket as above.

## The DC jack blocked the dock: a pocket for it (2026-10-23)

**The user's catch:** with a half-printed back cover fitted, the uncompressed pogo tips stick out about as far as the DC-022B jack's face, or less. So the pins can't reach the dock.

**Checked in the preview** (with the dock moved to the real parking position, −3.48 mm, log 042):
- The dock face in front of the jack was **flat, 8.9 mm** from the cover's dock area.
- The jack sticks out about 9 mm, so it would touch the dock before the pins compressed their 1.3 mm.

**Options:**
- **A:** a pocket in the dock for the jack.
- **B:** pins out 4 mm further, with the stop pads and the presence switch moved to match.

**The user chose A.**

**`charging-dock-v1` v10:**
- **The pocket:** Ø16 × 6 mm, with a 1.5 mm chamfer at the mouth to guide the jack in, centred on the jack (x 0, y 22) in the cradle face (dock frame z −131.05).
- **What it cut:** 1220 mm³ of solid material, so no wire channel or plate pocket was opened. There are walls to the copper-plate pockets on both sides.
- **Docked, the jack now has 14.9 mm of room** past the cover's dock area, about 6 mm more than it needs.
- **Unchanged:** pins, plates, stop pads and covers.
- **If the dock is already printed:** a Ø16 step drill, 6 mm deep, at the same spot does the same job.
- **Preview:** saved, now pointing at the dock v10.
