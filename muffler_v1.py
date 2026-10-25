#!/usr/bin/env python3
"""Baffle-style inline exhaust muffler: DXF drawings, BOM, drilling spec, weld map, fab sequence.

Run:  .venv/bin/python muffler.py [out_dir]     (needs: pip install ezdxf)
"""
import csv
import math
import sys
from pathlib import Path

import ezdxf

# ---------------- fixed geometry (mm) ----------------
L = 250.0                     # can + liner length
CAN_OD, CAN_T = 50.0, 1.5
LINER_OD, LINER_T = 32.0, 1.0
HOLE_D = 3.5
DISC_T = 3.0                  # end caps + baffles, 3 mm sheet
N_BAFFLES = 4                 # 3..5
MATERIAL = "AISI 304 (316 for corrosive/salt service)"
FILLER = "ER308L (ER316L if 316)"

# ---------------- derived / tunable ----------------
CAN_ID = CAN_OD - 2 * CAN_T
DISC_OD = CAN_ID - 0.2        # calibration knob: measure real can ID, set to ID - 0.2
DISC_ID = LINER_OD + 0.2      # slip fit on liner
ROW_PITCH = 5.0               # axial
HOLES_PER_ROW = 16
STAGGER_DEG = 360 / HOLES_PER_ROW / 2   # alternate rows rotated half a pitch
BASE_DEG = STAGGER_DEG / 2              # keeps every hole off the 0/360 datum line
FACE_CLEAR = HOLE_D / 2 + 3.0  # min hole-centre distance to any cap/baffle face
PLUG_D, PLUGS_PER_BAFFLE = 5.0, 3

BAFFLE_Z = [L * (k + 1) / (N_BAFFLES + 1) for k in range(N_BAFFLES)]
FACES = [DISC_T, L - DISC_T] + [z + s * DISC_T / 2 for z in BAFFLE_Z for s in (-1, 1)]


def rows():
    """(row_no, z, rotation_offset_deg) for every perforated row."""
    out, n = [], 0
    for i in range(1, int(L / ROW_PITCH)):
        z = i * ROW_PITCH
        if min(abs(z - f) for f in FACES) >= FACE_CLEAR:
            n += 1
            out.append((n, z, (i % 2) * STAGGER_DEG))
    return out


def holes():
    """(z, theta_deg) of every liner hole."""
    return [(z, (BASE_DEG + off + j * 360 / HOLES_PER_ROW) % 360)
            for _, z, off in rows() for j in range(HOLES_PER_ROW)]


def plug_holes():
    """(z, theta_deg) of can plug-weld holes; adjacent baffles clocked 60 deg."""
    return [(z, (k * 60 + j * 360 / PLUGS_PER_BAFFLE) % 360)
            for k, z in enumerate(BAFFLE_Z) for j in range(PLUGS_PER_BAFFLE)]


def stats():
    r = rows()
    hole_a = math.pi * HOLE_D ** 2 / 4
    n = len(r) * HOLES_PER_ROW
    circ = math.pi * LINER_OD
    c_pitch = circ / HOLES_PER_ROW
    diag = math.hypot(ROW_PITCH, c_pitch / 2)
    return dict(
        rows=len(r), holes=n, circ_pitch=c_pitch, diag_pitch=diag,
        lig_circ=c_pitch - HOLE_D, lig_diag=diag - HOLE_D,
        open_band=hole_a * HOLES_PER_ROW / (ROW_PITCH * circ),
        open_total=n * hole_a / (circ * L),
    )


# ---------------- DXF helpers ----------------
def new_doc():
    doc = ezdxf.new("R2010", setup=True, units=4)  # mm
    for name, color in (("CUT", 7), ("HOLES", 1), ("DIM", 3), ("TEXT", 2), ("CENTER", 4), ("WELD", 6)):
        doc.layers.add(name, color=color)
    doc.layers.get("CENTER").dxf.linetype = "CENTER"
    return doc, doc.modelspace()


DIM = {"dimtxt": 3.0, "dimasz": 2.5, "dimexe": 1.5, "dimexo": 1.0, "dimgap": 1.0, "dimdec": 2, "dimzin": 8, "dimlfac": 1.0}


def text(msp, s, x, y, h=3.0):
    msp.add_text(s, height=h, dxfattribs={"layer": "TEXT"}).set_placement((x, y))


def hdim(msp, x1, x2, y, base_y):
    msp.add_linear_dim(base=(x1, base_y), p1=(x1, y), p2=(x2, y), override=DIM, dxfattribs={"layer": "DIM"}).render()


def vdim(msp, y1, y2, x, base_x):
    msp.add_linear_dim(base=(base_x, y1), p1=(x, y1), p2=(x, y2), angle=90, override=DIM, dxfattribs={"layer": "DIM"}).render()


def rect(msp, x0, y0, x1, y1, layer="CUT"):
    msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={"layer": layer})


def title(msp, pn, name, x, y, extra=()):
    for i, s in enumerate((f"{pn}  {name}", f"MATL: {MATERIAL}", "UNITS: mm   TOL: +/-0.2 unless noted",
                           "LAYERS: CUT/HOLES = laser; DIM/TEXT/CENTER = do not cut", *extra)):
        text(msp, s, x, y - i * 5, 3.5 if i == 0 else 2.5)


# ---------------- drawings ----------------
def draw_disc(out, pn, name, extra):
    doc, msp = new_doc()
    msp.add_circle((0, 0), DISC_OD / 2, dxfattribs={"layer": "CUT"})
    msp.add_circle((0, 0), DISC_ID / 2, dxfattribs={"layer": "CUT"})
    r = DISC_OD / 2 + 4
    msp.add_line((-r, 0), (r, 0), dxfattribs={"layer": "CENTER"})
    msp.add_line((0, -r), (0, r), dxfattribs={"layer": "CENTER"})
    msp.add_diameter_dim((0, 0), radius=DISC_OD / 2, angle=45, override=DIM, dxfattribs={"layer": "DIM"}).render()
    msp.add_diameter_dim((0, 0), radius=DISC_ID / 2, angle=135, override=DIM, dxfattribs={"layer": "DIM"}).render()
    title(msp, pn, name, -30, -35, (f"THK {DISC_T} sheet", *extra))
    doc.saveas(out / f"{pn}_{name.lower().replace(' ', '_')}.dxf")


def draw_liner(out):
    """Flat wrap template (OD circumference) — print 1:1 to wrap the tube, or feed tube-laser CAM."""
    doc, msp = new_doc()
    W = math.pi * LINER_OD
    rect(msp, 0, 0, L, W)
    for z, th in holes():
        msp.add_circle((z, th / 360 * W), HOLE_D / 2, dxfattribs={"layer": "HOLES"})
    r = rows()
    hdim(msp, 0, L, 0, -15)
    vdim(msp, 0, W, 0, -12)
    hdim(msp, 0, r[0][1], W, W + 8)
    hdim(msp, r[0][1], r[1][1], W, W + 16)
    z0 = r[0][1]
    y0 = BASE_DEG / 360 * W
    vdim(msp, y0, y0 + W / HOLES_PER_ROW, z0, z0 - 6)
    s = stats()
    title(msp, "MUF-002", "PERFORATED LINER - FLAT WRAP TEMPLATE", 0, -30, (
        f"TUBE {LINER_OD} OD x {LINER_T} WALL x {L} LG, SEAMLESS (no seam - stagger puts holes on any seam line)",
        f"{s['holes']} HOLES DIA {HOLE_D} THRU, {s['rows']} ROWS @ {ROW_PITCH} AXIAL, {HOLES_PER_ROW}/ROW @ {360/HOLES_PER_ROW} deg",
        f"ODD/EVEN GRID ROWS ROTATED {STAGGER_DEG} deg (STAGGER). Y = arc on OD, 0 = datum line",
        f"OPEN AREA {s['open_band']:.1%} IN PERF BANDS, {s['open_total']:.1%} OVERALL. DEBURR BORE.",
    ))
    doc.saveas(out / "MUF-002_liner_flat_template.dxf")


def draw_can(out):
    doc, msp = new_doc()
    # elevation
    rect(msp, 0, -CAN_OD / 2, L, CAN_OD / 2)
    msp.add_line((-5, 0), (L + 5, 0), dxfattribs={"layer": "CENTER"})
    hdim(msp, 0, L, -CAN_OD / 2, -CAN_OD / 2 - 12)
    vdim(msp, -CAN_OD / 2, CAN_OD / 2, L, L + 12)
    prev = 0
    for i, z in enumerate(BAFFLE_Z):
        msp.add_line((z, -CAN_OD / 2 - 3), (z, CAN_OD / 2 + 3), dxfattribs={"layer": "CENTER"})
        hdim(msp, prev, z, CAN_OD / 2, CAN_OD / 2 + 8 + 8 * i)
        prev = z
    # flat wrap template for plug holes
    W, y0 = math.pi * CAN_OD, -CAN_OD / 2 - 40 - math.pi * CAN_OD
    rect(msp, 0, y0, L, y0 + W)
    for z, th in plug_holes():
        msp.add_circle((z, y0 + th / 360 * W), PLUG_D / 2, dxfattribs={"layer": "HOLES"})
    vdim(msp, y0, y0 + W, 0, -12)
    vdim(msp, y0, y0 + W / PLUGS_PER_BAFFLE, BAFFLE_Z[0], BAFFLE_Z[0] - 8)
    text(msp, "FLAT WRAP TEMPLATE (OD) - PLUG-WELD HOLES", 0, y0 + W + 4)
    title(msp, "MUF-001", "OUTER CAN", 0, y0 - 25, (
        f"TUBE {CAN_OD} OD x {CAN_T} WALL x {L} LG, ENDS SQUARE WITHIN 0.3",
        f"{len(plug_holes())} x DIA {PLUG_D} PLUG-WELD HOLES, {PLUGS_PER_BAFFLE} @ 120 deg PER BAFFLE STATION,",
        "ADJACENT STATIONS CLOCKED 60 deg. HOLE CENTRES ON BAFFLE MID-PLANE +/-0.3",
    ))
    doc.saveas(out / "MUF-001_outer_can.dxf")


def draw_assembly(out):
    """Half-section along axis with weld callouts."""
    doc, msp = new_doc()
    ro, ri = CAN_OD / 2, CAN_ID / 2
    lo, li = LINER_OD / 2, LINER_OD / 2 - LINER_T
    for s in (1, -1):
        rect(msp, 0, s * ri, L, s * ro)                         # can wall
        rect(msp, 0, s * li, L, s * lo)                         # liner wall
        for z0 in (0, L - DISC_T):                               # caps, flush with ends
            rect(msp, z0, s * DISC_ID / 2, z0 + DISC_T, s * DISC_OD / 2)
        for z in BAFFLE_Z:
            rect(msp, z - DISC_T / 2, s * DISC_ID / 2, z + DISC_T / 2, s * DISC_OD / 2)
    for _, z, _ in rows():
        msp.add_line((z, lo), (z, li), dxfattribs={"layer": "HOLES"})
    msp.add_line((-10, 0), (L + 10, 0), dxfattribs={"layer": "CENTER"})
    prev = 0
    for i, z in enumerate(BAFFLE_Z + [L]):
        hdim(msp, prev, z, -ro, -ro - 10 - 8 * i)
        prev = z
    vdim(msp, -ro, ro, L, L + 12)
    vdim(msp, -lo, lo, 0, -12)
    callouts = [("W1", L, ro), ("W2", L, lo), ("W3", BAFFLE_Z[1] - DISC_T / 2, lo), ("W4", BAFFLE_Z[2], ro)]
    for tag, x, y in callouts:
        msp.add_line((x, y), (x + 8, y + 15), dxfattribs={"layer": "WELD"})
        text(msp, tag, x + 9, y + 15)
    text(msp, "INLET", -20, 2)
    text(msp, "OUTLET", L + 4, 2)
    title(msp, "MUF-000", "ASSEMBLY HALF-SECTION", 0, -ro - 60, (
        "W1 cap-can rim | W2 cap-liner port | W3 baffle-liner | W4 can-baffle plug  (see weld map)",
    ))
    doc.saveas(out / "MUF-000_assembly.dxf")


# ---------------- documents ----------------
BOM = [
    ("MUF-000", "Muffler assembly", "-", 1, "Weldment; see MUF-000 DXF, weld map, fab sequence"),
    ("MUF-001", "Outer can", f"{MATERIAL}, tube {CAN_OD}x{CAN_T}", 1,
     f"Saw/laser to {L} +/-0.5, face square; {len(plug_holes())}x DIA {PLUG_D} plug holes; deburr"),
    ("MUF-002", "Perforated liner", f"{MATERIAL}, seamless tube {LINER_OD}x{LINER_T}", 1,
     f"Cut to {L} +/-0.5; {len(holes())}x DIA {HOLE_D} per drilling spec (tube laser or drill w/ template); deburr bore"),
    ("MUF-003", "End cap (inlet/outlet port)", f"{MATERIAL}, {DISC_T} sheet", 2,
     f"Laser: OD {DISC_OD:.1f}, port bore {DISC_ID:.1f}; port = liner bore DIA {LINER_OD - 2*LINER_T:.0f}"),
    ("MUF-004", "Baffle / spacer", f"{MATERIAL}, {DISC_T} sheet", N_BAFFLES,
     f"Laser: OD {DISC_OD:.1f}, ID {DISC_ID:.1f} (same blank as MUF-003); edge clean for plug weld"),
    ("MUF-005", "TIG filler rod", f"{FILLER}, DIA 1.0-1.6", 1, "As required"),
]

WELDS = [
    ("W1", "End cap OD to can rim", 2, "Full 360 corner/fillet, outside", f"{CAN_T} leg (= can wall)", "Purge argon via port before welding"),
    ("W2", "End cap bore to liner OD (port)", 2, "Full 360 fillet, outside face", f"{LINER_T} leg (= liner wall)", "Low amps; liner is thin"),
    ("W3", "Baffle ID to liner OD", N_BAFFLES, "Full 360 fillet, upstream face; tack 3x first", f"{LINER_T} leg", "Before liner goes into can"),
    ("W4", "Can to baffle edge (plug)", N_BAFFLES * PLUGS_PER_BAFFLE, f"Plug weld through DIA {PLUG_D} hole", "Fill flush, fuse baffle edge", "Alternate stations to limit distortion"),
]

FAB = [
    ("CUT", f"Cut can tube and liner tube to {L} +/-0.5, face ends square within 0.3. Laser {2 + N_BAFFLES} discs "
            f"(MUF-003 x2, MUF-004 x{N_BAFFLES}) from {DISC_T} sheet. Measure can ID first; DISC_OD = ID - 0.2."),
    ("DRILL", f"Liner: {len(holes())} holes DIA {HOLE_D} per drilling spec (tube laser, or wrap MUF-002 template 1:1 "
              f"and drill). Can: {len(plug_holes())} plug holes DIA {PLUG_D}. Deburr; brush out bore swarf."),
    ("CLEAN", "Degrease all parts with acetone. Stainless-only brushes/tools (no carbon-steel contamination)."),
    ("WELD (sub-assy)", f"Slide baffles onto liner at z = {', '.join(f'{z:g}' for z in BAFFLE_Z)} (spacer blocks), "
                        "square to axis. Tack 3x, then W3 full-round on upstream faces."),
    ("WELD (can)", "Slide liner/baffle sub-assy into can; align each baffle mid-plane under its plug holes. "
                   "W4 plug welds, alternating stations."),
    ("CAP", "Press end caps in flush with can/liner ends. Argon purge through port. W2 (cap-liner) then W1 (cap-can) both ends."),
    ("FINISH", "Pickle/passivate welds (paste or citric). Leak test 0.3 bar air + soap on all welds. Inspect bore clear."),
]


def write_docs(out):
    s = stats()
    with open(out / "bom.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["part_no", "name", "material", "qty", "machining_notes"])
        w.writerows(BOM)

    md = ["# Baffle Muffler 50x250 - Fabrication Spec", "", "## 1. Drawings (DXF, mm)", ""]
    md += [f"- `{p.name}`" for p in sorted(out.glob("*.dxf"))]
    md += ["", "## 2. BOM", "", "| Part no. | Name | Material | Qty | Machining notes |", "|---|---|---|---|---|"]
    md += [f"| {' | '.join(map(str, r))} |" for r in BOM]
    md += ["", "## 3. Drilling spec - liner MUF-002", "",
           f"- Hole: DIA {HOLE_D} thru, {LINER_T} wall, burr-free bore side",
           f"- Pattern: {s['rows']} rows x {HOLES_PER_ROW} holes = **{s['holes']} holes**, staggered",
           f"- Axial pitch: {ROW_PITCH} on a {ROW_PITCH} grid from the inlet end; rows within {FACE_CLEAR} of a cap/baffle face omitted",
           f"- Angular pitch: {360/HOLES_PER_ROW} deg = {s['circ_pitch']:.2f} c-c on OD",
           f"- Per-row rotation offset: {STAGGER_DEG} deg on odd grid rows (z/{ROW_PITCH} odd), 0 on even; first hole at {BASE_DEG} deg from datum",
           f"- Diagonal c-c: {s['diag_pitch']:.2f}; min ligament {min(s['lig_circ'], s['lig_diag']):.2f} (>= wall)",
           f"- Open area: {s['open_band']:.1%} in perforated bands, {s['open_total']:.1%} of full liner surface",
           "", "| Row | z from inlet | Rotation offset (deg) |", "|---|---|---|"]
    md += [f"| {n} | {z:g} | {off:g} |" for n, z, off in rows()]
    md += ["", "Can MUF-001 plug holes:", "", "| Baffle z | Angles (deg) |", "|---|---|"]
    md += [f"| {z:g} | {', '.join(f'{t:g}' for zz, t in plug_holes() if zz == z)} |" for z in BAFFLE_Z]
    md += ["", f"## 4. Weld map (GTAW/TIG, filler {FILLER}, argon)", "",
           "| ID | Joint | Qty | Type / extent | Size | Note |", "|---|---|---|---|---|---|"]
    md += [f"| {' | '.join(map(str, r))} |" for r in WELDS]
    md += ["", "## 5. Fab sequence", ""]
    md += [f"{i}. **{step}** - {t}" for i, (step, t) in enumerate(FAB, 1)]
    (out / "muffler_spec.md").write_text("\n".join(md) + "\n")


def check():
    s = stats()
    assert 3 <= N_BAFFLES <= 5
    assert min(s["lig_circ"], s["lig_diag"]) >= LINER_T, "ligament thinner than wall"
    assert 0.27 <= s["open_band"] <= 0.33, s["open_band"]
    assert all(min(abs(z - f) for f in FACES) >= FACE_CLEAR for z, _ in holes())
    assert DISC_ID < DISC_OD < CAN_ID
    assert len(set(holes())) == s["holes"]


if __name__ == "__main__":
    check()
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "out")
    out.mkdir(parents=True, exist_ok=True)
    draw_assembly(out)
    draw_can(out)
    draw_liner(out)
    draw_disc(out, "MUF-003", "END CAP", ("QTY 2. Bore = inlet/outlet port, slip fit on liner", "Fits flush inside can ends"))
    draw_disc(out, "MUF-004", "BAFFLE", (f"QTY {N_BAFFLES}. Full annular baffle/spacer",
                                         f"Stations z = {', '.join(f'{z:g}' for z in BAFFLE_Z)}"))
    write_docs(out)
    print(f"wrote {out}: {', '.join(sorted(p.name for p in out.iterdir()))}")
    print(stats())
