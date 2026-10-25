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
| MUF-002 | Perforated liner | 304 tube 32 OD x 2 wall (seamless pref.) | 1 | Cut 250 +/-0.5; 112x DIA 9 radial per drilling spec, using JIG-001; deburr ID+OD | AliExpress 32x2 304 tube, 300 mm (cut to 250) or uxcell 32x2 on Amazon. Fallback rolled 2 mm sheet = 7 holes/row + W4 seam variant (not generated here) |
| MUF-003 | End cap (inlet/outlet port) | 304, 3 sheet | 2 | Laser/plasma+turn: OD 45.8, bore 32.2; port = liner bore | 3 mm 304 plate; laser-cut service (SendCutSend, OSH Cut, local shop) from MUF-003/004 DXF |
| MUF-004 | Baffle | 304, 3 sheet | 4 | Same blank as MUF-003 | 3 mm 304 plate; laser-cut service (SendCutSend, OSH Cut, local shop) from MUF-003/004 DXF |
| MUF-005 | Packing (optional) | Stainless wool + basalt/E-glass muffler packing | 1 | ~30 g; core fill | Motorcycle muffler repack kit |
| MUF-006 | TIG filler rod | ER308L 1/16 in (1.6 mm); ER316L if 316 | 1 | ~0.25 kg tube | Welding supply |
| JIG-001 | Drill jig | 0.5 mm shim + 38 OD tube + steel block + M6 nut | 1 | See jig_build.md | Shim stock + scrap |

## 3. Drilling spec - liner MUF-002

- Hole DIA 9 thru, radial; pilot DIA 4 then step drill
- 14 rows x 8 = **112 holes**
- In-row pitch 45 deg = 12.57 c-c on OD (11.00 on ID)
- Row pitch 12 within each chamber; rows centred between cap/baffle faces (3/3/2/3/3 per chamber)
- Per-row rotation offset 22.5 deg = half the 45 deg pitch (rows alternate 0 / 22.5)
- Webs: 2.00 in-row @ ID, 3.57 @ OD, 3.00 axial, 4.20 diagonal
- Open area 28.4% on OD basis (32.4% on ID flow-path basis)

| Row | z from inlet | Rotation offset (deg) |
|---|---|---|
| 1 | 13.75 | 0.0 |
| 2 | 25.75 | 22.5 |
| 3 | 37.75 | 0.0 |
| 4 | 63 | 22.5 |
| 5 | 75 | 0.0 |
| 6 | 87 | 22.5 |
| 7 | 119 | 0.0 |
| 8 | 131 | 22.5 |
| 9 | 163 | 0.0 |
| 10 | 175 | 22.5 |
| 11 | 187 | 0.0 |
| 12 | 212.25 | 22.5 |
| 13 | 224.25 | 0.0 |
| 14 | 236.25 | 22.5 |

## 4. Weld map (GTAW, argon)

| ID | Joint | Qty | Type / extent | Size |
|---|---|---|---|---|
| W1 | End cap OD to can rim | 2 | Flush corner (butt-style), full 360, outside | 2 (= can wall) |
| W2 | End cap bore to liner OD (port) | 2 | Fillet, full 360, outside face | 2 leg |
| W3 | Baffle ID to liner OD | 4 | Fillet, full 360, upstream face | 2 leg |

No W4: liner is purchased tube, no shop seam. No plug welds: baffles are held by W3 only.

## 5. TIG parameters

| ID | Joint | DC (DCEN) | Pulse (recommended) | Argon | Back-purge | Filler |
|---|---|---|---|---|---|---|
| W1 | End cap OD to can rim | 65-85 A | base 40-60 A, peak 100 A, 30-50 Hz | 8-10 L/min (gas lens 10-12) | 4-6 L/min | ER308L 1/16 in |
| W2 | End cap bore to liner OD (port) | 80-100 A | base 60-80 A, peak 100 A, 30-50 Hz | 8-10 L/min (gas lens 10-12) | 4-6 L/min | ER308L 1/16 in |
| W3 | Baffle ID to liner OD | 80-100 A | base 60-80 A, peak 100 A, 30-50 Hz | 8-10 L/min (gas lens 10-12) | 4-6 L/min | ER308L 1/16 in |

Machine: 220 V, 110 A max, DC/pulse. DCEN, 2% lanthanated 1/16 in tungsten, #7 cup or gas lens. Tack first, then continuous. Back-purge every hollow joint (can, caps). No preheat. Interpass < 150 C.

## 6. Fab sequence

See build_book.md.
