# Baffle Muffler 50x250 - Fabrication Spec (TIG revision)

Can wall 2 mm, liner 32x2 purchased tube, 4 baffles, disc OD 45.8 (can ID 46.00 - 0.2).

## 1. Drawings (out/handoff/)

- `MUF-000_assembly.dxf`
- `MUF-001_outer_can.dxf`
- `MUF-002_liner_wrap_layout.dxf`
- `MUF-003_end_cap.dxf`
- `MUF-004_baffle.dxf`
- `drill_jig.dxf`

## 2. BOM

| Part no. | Name | Material | Qty | Notes | Source |
|---|---|---|---|---|---|
| MUF-000 | Muffler assembly | - | 1 | Weldment; MUF-000 DXF, weld map, build book | - |
| MUF-001 | Outer can | 304 tube 50 OD x 2 wall | 1 | Cut 250 +/-0.5, square ends, deburr. Measure ID x4. | Online Metals 50x2 304, 60 in length (MTR available) or Amazon 50x2x400 mm (cut to 250) |
| MUF-002 | Perforated liner | 304 tube 32 OD x 2 wall (seamless pref.) | 1 | Cut 244 +/-0.3; 480x DIA 4 radial per drilling spec, using JIG-001; deburr ID+OD | AliExpress 32x2 304 tube, 300 mm (cut to 250) or uxcell 32x2 on Amazon. Fallback rolled 2 mm sheet = 7 holes/row + W4 seam variant (not generated here) |
| MUF-003 | End cap | 304, 3 sheet | 2 | Laser: OD 45.8, port bore 26.9 for the nipple | 3 mm 304 plate; laser-cut service (SendCutSend, OSH Cut, local shop) from MUF-003/004 DXF |
| MUF-004 | Baffle | 304, 3 sheet | 4 | Laser: OD 45.8, bore 32.2 | 3 mm 304 plate; laser-cut service (SendCutSend, OSH Cut, local shop) from MUF-003/004 DXF |
| MUF-005 | Port nipple 3/4"-14 NPT | 304 sch40 pipe nipple, thread one end (TOE), 2 in long | 2 | Cut plain end to 28 overall (14 thread + 6 relief + 3 cap + 5 spigot); deburr | McMaster-Carr / plumbing or industrial supply (304 TOE nipple) |
| MUF-006 | TIG filler rod | ER308L 1/16 in (1.6 mm); ER316L if 316 | 1 | ~0.25 kg tube | Welding supply |
| JIG-001 | Drill jig | 0.5 mm shim + 38 OD tube + steel block + M6 nut | 1 | See jig_build.md | Shim stock + scrap |

## 3. Drilling spec - liner MUF-002

- Hole DIA 4 thru, radial, drilled straight through the sleeve guide (no step drill)
- Liner 244 long (z = 3-247); z below is measured from the can's inlet end
- 30 rows x 16 = **480 holes**
- In-row pitch 22.5 deg = 6.28 c-c on OD (5.50 on ID)
- Row pitch 7 within each chamber; rows centred between cap/baffle faces (6/6/6/6/6 per chamber)
- Per-row rotation offset 11.25 deg = half the 22.5 deg pitch (rows alternate 0 / 11.25)
- Webs: 1.50 in-row @ ID, 2.28 @ OD, 3.00 axial, 3.52 diagonal
- Open area 24.6% on OD basis (28.1% on ID flow-path basis)

| Row | z from inlet | Rotation offset (deg) |
|---|---|---|
| 1 | 8.25 | 0.0 |
| 2 | 15.25 | 11.25 |
| 3 | 22.25 | 0.0 |
| 4 | 29.25 | 11.25 |
| 5 | 36.25 | 0.0 |
| 6 | 43.25 | 11.25 |
| 7 | 57.5 | 0.0 |
| 8 | 64.5 | 11.25 |
| 9 | 71.5 | 0.0 |
| 10 | 78.5 | 11.25 |
| 11 | 85.5 | 0.0 |
| 12 | 92.5 | 11.25 |
| 13 | 107.5 | 0.0 |
| 14 | 114.5 | 11.25 |
| 15 | 121.5 | 0.0 |
| 16 | 128.5 | 11.25 |
| 17 | 135.5 | 0.0 |
| 18 | 142.5 | 11.25 |
| 19 | 157.5 | 0.0 |
| 20 | 164.5 | 11.25 |
| 21 | 171.5 | 0.0 |
| 22 | 178.5 | 11.25 |
| 23 | 185.5 | 0.0 |
| 24 | 192.5 | 11.25 |
| 25 | 206.75 | 0.0 |
| 26 | 213.75 | 11.25 |
| 27 | 220.75 | 0.0 |
| 28 | 227.75 | 11.25 |
| 29 | 234.75 | 0.0 |
| 30 | 241.75 | 11.25 |

## 4. Weld map (GTAW, argon)

| ID | Joint | Qty | Type / extent | Size |
|---|---|---|---|---|
| W1 | End cap OD to can rim | 2 | Flush corner (butt-style), full 360, outside | 2 (= can wall) |
| W2 | Port nipple (3/4"-14 NPT) to end cap | 2 | Fillet, full 360, outside face | 2 leg |
| W3 | Baffle ID to liner OD | 4 | Fillet, full 360, upstream face | 2 leg |

No W4: liner is purchased tube, no shop seam. No plug welds: baffles are held by W3 only.
Liner is not welded to the caps: it is captured between them and centred by the nipple spigots.

## 4a. Port

- 3/4"-14 NPT male, both ends: 304 sch40 TOE nipple, OD 26.67, ID 20.93, cut to 28
- External thread 14 (L2 13.86, hand-tight L1 8.61); 6 plain relief before the cap; 5 spigot into the liner bore
- Thread sealant: nickel anti-seize (PTFE tape/paste breaks down at exhaust temperature)

## 5. TIG parameters

| ID | Joint | DC (DCEN) | Pulse (recommended) | Argon | Back-purge | Filler |
|---|---|---|---|---|---|---|
| W1 | End cap OD to can rim | 65-85 A | base 40-60 A, peak 100 A, 30-50 Hz | 8-10 L/min (gas lens 10-12) | 4-6 L/min | ER308L 1/16 in |
| W2 | Port nipple (3/4"-14 NPT) to end cap | 80-100 A | base 60-80 A, peak 100 A, 30-50 Hz | 8-10 L/min (gas lens 10-12) | 4-6 L/min | ER308L 1/16 in |
| W3 | Baffle ID to liner OD | 80-100 A | base 60-80 A, peak 100 A, 30-50 Hz | 8-10 L/min (gas lens 10-12) | 4-6 L/min | ER308L 1/16 in |

Machine: 220 V, 110 A max, DC/pulse. DCEN, 2% lanthanated 1/16 in tungsten, #7 cup or gas lens. Tack first, then continuous. Back-purge every hollow joint (can, caps). No preheat. Interpass < 150 C.

## 6. Fab sequence

See build_book.md.
