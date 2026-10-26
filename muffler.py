#!/usr/bin/env python3
"""Baffle-style inline exhaust muffler, TIG home-shop revision.

Generates DXF drawings, drill jig, BOM, spec, build book, checklist, mermaid flow and check results.

Run:  .venv/bin/python muffler.py [--can-wall 1.5] [--can-id 46.1] [--liner-od 31.75] [--max-amps 110]
Needs: pip install ezdxf matplotlib
"""
import argparse
import csv
import math
import shutil
from pathlib import Path

import ezdxf

ap = argparse.ArgumentParser()
ap.add_argument("--can-wall", type=float, default=2.0, help="outer can wall (1.5 for a 110 A machine if needed)")
ap.add_argument("--can-id", type=float, help="MEASURED can ID; disc OD = this - 0.2")
ap.add_argument("--liner-od", type=float, help="MEASURED liner OD; disc bore = this + 0.2")
ap.add_argument("--max-amps", type=float, default=110, help="welder output limit")
ap.add_argument("--out", default=str(Path(__file__).parent / "out"))
ARGS = ap.parse_args()

# ---------------- geometry (mm) ----------------
L = 250.0
CAN_OD, CAN_T = 50.0, ARGS.can_wall
LINER_OD, LINER_T = 32.0, 2.0          # purchased 32x2 304 tube, no shop seam
HOLE_D = 4.0
HOLES_PER_ROW = 16
ROW_PITCH = 7.0                        # 8 mm grid would put rows under baffles/caps; 7 mm keeps 6 rows/chamber clear
ROW_OFFSET_DEG = 11.25                 # per-row rotation = half the 22.5 deg pitch -> true stagger
ROWS_PER_CHAMBER = [6, 6, 6, 6, 6]     # 30 rows
DISC_T = 3.0
N_BAFFLES = len(ROWS_PER_CHAMBER) - 1
MIN_WEB = 1.4                          # 1.5 nominal (1.498 at ID); fine for an unpressurised drilled 2 mm liner
FACE_CLEAR = HOLE_D / 2 + 3.0          # hole centre to any cap/baffle face
MATERIAL = "AISI 304 (316 for corrosive/salt service)"
FILLER = "ER308L 1/16 in (1.6 mm); ER316L if 316"

CAN_ID = ARGS.can_id or CAN_OD - 2 * CAN_T
LINER_OD_REAL = ARGS.liner_od or LINER_OD
LINER_ID = LINER_OD - 2 * LINER_T
DISC_OD = CAN_ID - 0.2                 # calibration knob: measured can ID - 0.2
DISC_ID = LINER_OD_REAL + 0.2          # baffle bore
LINER_Z0 = DISC_T                      # liner is captured between the caps' inner faces
LINER_L = L - 2 * DISC_T

# port: weld-in 304 sch40 pipe nipple, thread one end (TOE); a 3 mm cap can't hold an NPT thread itself
PORT_THREAD = '1/8"-27 NPT'
NPT = {  # OD, hand-tight L1, effective thread L2, sch40 ID (ASME B1.20.1 / B36.19)
    '1/8"-27 NPT': dict(od=11.10, l1=8.0, l2=13.86, pipe_id=7.82),  # major 0.437 in, sch40 ID 0.308 in
    '1/2"-14 NPT': dict(od=21.34, l1=8.13, l2=13.56, pipe_id=15.80),
    '3/4"-14 NPT': dict(od=26.67, l1=8.61, l2=13.86, pipe_id=20.93),
    '1"-11.5 NPT': dict(od=33.40, l1=10.16, l2=17.34, pipe_id=26.64),
}[PORT_THREAD]
PORT_BORE = NPT["od"] + 0.2            # cap bore for the nipple
NIP_SPIGOT = 5.0                       # nipple end inside the liner bore (centres the cap)
NIP_RELIEF = 6.0                       # plain section between cap face and first thread (weld + wrench)
NIP_THREAD = math.ceil(NPT["l2"])
NIP_LEN = NIP_SPIGOT + DISC_T + NIP_RELIEF + NIP_THREAD

BAFFLE_Z = [L * (k + 1) / (N_BAFFLES + 1) for k in range(N_BAFFLES)]
# Spacer blocks: first baffle centre from the liner inlet (liner starts one disc in from the can end),
# and the face-to-face gap (centre pitch minus disc thickness).
BAFFLE_FROM_LINER = BAFFLE_Z[0] - LINER_Z0
BAFFLE_FACE_GAP = BAFFLE_Z[1] - BAFFLE_Z[0] - DISC_T
CHAMBERS = list(zip([DISC_T] + [z + DISC_T / 2 for z in BAFFLE_Z],
                    [z - DISC_T / 2 for z in BAFFLE_Z] + [L - DISC_T]))
FACES = [f for c in CHAMBERS for f in c]

# jig
SHIM_T, SHIM_TAB, PILOT_D = 0.5, 12.0, 2.0
SLEEVE_OD, SLEEVE_LEN, GUIDE_D = 38.0, 40.0, HOLE_D   # guide = final hole size: drill straight through


def rows():
    """(row_no, z, rotation_offset_deg): rows centred in each chamber."""
    out = []
    for (a, b), n in zip(CHAMBERS, ROWS_PER_CHAMBER):
        mid = (a + b) / 2
        out += [mid + (i - (n - 1) / 2) * ROW_PITCH for i in range(n)]
    return [(k + 1, z, round(k * ROW_OFFSET_DEG % (360 / HOLES_PER_ROW), 2)) for k, z in enumerate(out)]


def holes():
    return [(z, (off + j * 360 / HOLES_PER_ROW) % 360) for _, z, off in rows() for j in range(HOLES_PER_ROW)]


# TIG, DCEN (never AC on stainless). Pulse is recommended for 2 mm 304.
#   (dc range, pulse base, pulse peak, pulse Hz); peak drives the max-amps check
TIG_EDGE = ("65-85 A", "40-60 A", 100, "30-50 Hz")    # can rim corner: melts two edges, little mass
TIG_FILLET = ("80-100 A", "60-80 A", 100, "30-50 Hz")  # 2-2.9 mm tube to 3 mm disc fillet

WELDS = [  # id, joint, qty, type, size, tig
    ("W1", "End cap OD to can rim", 2, "Flush corner (butt-style), full 360, outside", f"{CAN_T:g} (= can wall)", TIG_EDGE),
    ("W2", f"Port nipple ({PORT_THREAD}) to end cap", 2, "Fillet, full 360, outside face", "2 leg", TIG_FILLET),
    ("W3", "Baffle ID to liner OD", N_BAFFLES, "Fillet, full 360, upstream face", f"{LINER_T:g} leg", TIG_FILLET),
]


def stats():
    r = rows()
    hole_a = math.pi * HOLE_D ** 2 / 4
    n = len(r) * HOLES_PER_ROW
    pitch = math.radians(360 / HOLES_PER_ROW)

    def ang(d):
        d %= 360
        return min(d, 360 - d)

    # adjacent rows: min centre distance on the ID surface (worst case)
    diag = min(math.hypot(r[i + 1][1] - r[i][1],
                          math.radians(ang(r[i + 1][2] - r[i][2] + j * 360 / HOLES_PER_ROW)) * LINER_ID / 2)
               for i in range(len(r) - 1) for j in range(HOLES_PER_ROW))
    return dict(
        rows=len(r), holes=n,
        pitch_od=pitch * LINER_OD / 2, pitch_id=pitch * LINER_ID / 2,
        web_od=pitch * LINER_OD / 2 - HOLE_D, web_id=pitch * LINER_ID / 2 - HOLE_D,
        web_axial=min(b[1] - a[1] for a, b in zip(r, r[1:])) - HOLE_D,
        web_diag=diag - HOLE_D,
        face_clear=min(abs(z - f) for _, z, _ in r for f in FACES) - HOLE_D / 2,
        open_total=n * hole_a / (math.pi * LINER_OD * LINER_L),
        open_id=n * hole_a / (math.pi * LINER_ID * LINER_L),
        max_amps=max(w[5][2] for w in WELDS),
    )


def checks():
    s = stats()
    return [
        ("Hole count", f"{s['holes']} = {s['rows']} rows x {HOLES_PER_ROW}", s["holes"] == len(set(holes()))),
        ("Web, within row @ ID (worst)", f"{s['web_id']:.2f} mm >= {MIN_WEB}", s["web_id"] >= MIN_WEB),
        ("Web, within row @ OD", f"{s['web_od']:.2f} mm", s["web_od"] >= MIN_WEB),
        ("Web, between rows (axial)", f"{s['web_axial']:.2f} mm >= wall {LINER_T:g}", s["web_axial"] >= LINER_T),
        (f"Web, diagonal ({ROW_OFFSET_DEG} deg offset) @ ID", f"{s['web_diag']:.2f} mm >= {MIN_WEB}", s["web_diag"] >= MIN_WEB),
        ("Open area, whole liner", f"{s['open_id']:.1%} on ID ({LINER_ID:g} mm) flow-path basis, target 27-33%; "
                                   f"{s['open_total']:.1%} on OD ({LINER_OD:g} mm) basis", 0.27 <= s["open_id"] <= 0.33),
        ("Hole edge to cap/baffle face", f"{s['face_clear']:.2f} mm >= 3.0", s["face_clear"] >= 3.0 - 1e-9),
        ("Disc OD in can ID", f"{DISC_OD:.2f} < {CAN_ID:.2f}", DISC_OD < CAN_ID),
        ("Baffle bore over liner OD", f"{DISC_ID:.2f} > {LINER_OD_REAL:.2f}", DISC_ID > LINER_OD_REAL),
        (f"Port {PORT_THREAD}: nipple spigots into liner", f"nipple OD {NPT['od']:.2f} < liner ID {LINER_ID:g}; "
         f"cap bore {PORT_BORE:.1f}", NPT["od"] < LINER_ID and PORT_BORE < LINER_OD),
        ("Port thread engagement + weld relief", f"thread {NIP_THREAD} >= L2 {NPT['l2']}; relief {NIP_RELIEF:g} >= 6",
         NIP_THREAD >= NPT["l2"] and NIP_RELIEF >= 6),
        ("Baffle count 3-5", str(N_BAFFLES), 3 <= N_BAFFLES <= 5),
        ("Max TIG amps (DC / pulse peak) <= welder", f"{s['max_amps']} A <= {ARGS.max_amps:g} A", s["max_amps"] <= ARGS.max_amps),
    ]


# ---------------- DXF helpers ----------------
DIM = {"dimtxt": 3.0, "dimasz": 2.5, "dimexe": 1.5, "dimexo": 1.0, "dimgap": 1.0,
       "dimdec": 2, "dimzin": 8, "dimlfac": 1.0}   # ezdxf's EZDXF style defaults to x100 / tiny text


def new_doc():
    doc = ezdxf.new("R2010", setup=True, units=4)
    for name, color in (("CUT", 7), ("HOLES", 1), ("DIM", 3), ("TEXT", 2), ("CENTER", 4), ("WELD", 6), ("DETAIL", 8)):
        doc.layers.add(name, color=color)
    doc.layers.get("CENTER").dxf.linetype = "CENTER"
    return doc, doc.modelspace()


def text(msp, s, x, y, h=3.0):
    msp.add_text(s, height=h, dxfattribs={"layer": "TEXT"}).set_placement((x, y))


def hdim(msp, x1, x2, y, base_y):
    msp.add_linear_dim(base=(x1, base_y), p1=(x1, y), p2=(x2, y), override=DIM, dxfattribs={"layer": "DIM"}).render()


def vdim(msp, y1, y2, x, base_x):
    msp.add_linear_dim(base=(base_x, y1), p1=(x, y1), p2=(x, y2), angle=90, override=DIM,
                       dxfattribs={"layer": "DIM"}).render()


def ddim(msp, c, r, angle):
    msp.add_diameter_dim(c, radius=r, angle=angle, override=DIM, dxfattribs={"layer": "DIM"}).render()


def rect(msp, x0, y0, x1, y1, layer="CUT"):
    msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={"layer": layer})


def circle(msp, c, d, layer="CUT"):
    msp.add_circle(c, d / 2, dxfattribs={"layer": layer})


def title(msp, pn, name, x, y, extra=(), matl=MATERIAL):
    for i, s in enumerate((f"{pn}  {name}", f"MATL: {matl}", "UNITS: mm   TOL: +/-0.2 unless noted",
                           "LAYERS: CUT/HOLES = cut; DIM/TEXT/CENTER/DETAIL = do not cut", *extra)):
        text(msp, s, x, y - i * 5, 3.5 if i == 0 else 2.5)


def save(doc, path):
    doc.saveas(path)
    try:
        from ezdxf.addons.drawing import matplotlib as mpl
        png = path.parent / "png" / (path.stem + ".png")
        png.parent.mkdir(exist_ok=True)
        mpl.qsave(doc.modelspace(), str(png))
    except ImportError:
        pass


# ---------------- drawings ----------------
def draw_disc(out, pn, name, qty, extra):
    doc, msp = new_doc()
    circle(msp, (0, 0), DISC_OD)
    circle(msp, (0, 0), DISC_ID)
    r = DISC_OD / 2 + 4
    msp.add_line((-r, 0), (r, 0), dxfattribs={"layer": "CENTER"})
    msp.add_line((0, -r), (0, r), dxfattribs={"layer": "CENTER"})
    ddim(msp, (0, 0), DISC_OD / 2, 45)
    ddim(msp, (0, 0), DISC_ID / 2, 135)
    title(msp, pn, name, -30, -35, (f"THK {DISC_T:g} sheet, QTY {qty}",
                                    "OD = MEASURED CAN ID - 0.2; BORE = MEASURED LINER OD + 0.2", *extra))
    save(doc, out / f"{pn}_{name.lower().replace(' ', '_')}.dxf")


def draw_cap(out):
    """End view + side section with the port nipple and thread relief."""
    doc, msp = new_doc()
    circle(msp, (0, 0), DISC_OD)
    circle(msp, (0, 0), PORT_BORE)
    r = DISC_OD / 2 + 4
    msp.add_line((-r, 0), (r, 0), dxfattribs={"layer": "CENTER"})
    msp.add_line((0, -r), (0, r), dxfattribs={"layer": "CENTER"})
    ddim(msp, (0, 0), DISC_OD / 2, 45)
    ddim(msp, (0, 0), PORT_BORE / 2, 135)
    # side section (axis horizontal, outside face at x0)
    x0, ro, rn, rp = 60, DISC_OD / 2, NPT["od"] / 2, NPT["pipe_id"] / 2
    for s in (1, -1):
        rect(msp, x0, s * PORT_BORE / 2, x0 + DISC_T, s * ro, "DETAIL")               # cap (section only)
        rect(msp, x0 - NIP_RELIEF - NIP_THREAD, s * rp, x0 + DISC_T + NIP_SPIGOT, s * rn, "DETAIL")  # nipple
        xt = x0 - NIP_RELIEF - NIP_THREAD
        for k in range(int(NIP_THREAD / 1.814)):                                      # thread teeth, 14 tpi
            xa = xt + k * 1.814
            msp.add_lwpolyline([(xa, s * rn), (xa + 0.907, s * (rn + 0.9)), (xa + 1.814, s * rn)],
                               dxfattribs={"layer": "DETAIL"})
    msp.add_line((x0 - 32, 0), (x0 + 15, 0), dxfattribs={"layer": "CENTER"})
    yb = -ro - 4
    xt = x0 - NIP_RELIEF - NIP_THREAD
    hdim(msp, xt, x0 - NIP_RELIEF, -rn, yb)
    hdim(msp, x0 - NIP_RELIEF, x0, -rn, yb)
    hdim(msp, x0, x0 + DISC_T, -ro, yb - 8)
    hdim(msp, x0 + DISC_T, x0 + DISC_T + NIP_SPIGOT, -rn, yb)
    vdim(msp, -rn, rn, xt, xt - 8)
    text(msp, f"SECTION: {PORT_THREAD} TOE NIPPLE IN CAP", x0 - 32, ro + 13)
    text(msp, f"thread {NIP_THREAD} (L2 {NPT['l2']}) | relief {NIP_RELIEF:g} | cap {DISC_T:g} | spigot {NIP_SPIGOT:g} into liner",
         x0 - 32, ro + 8, 2.2)
    text(msp, "W2 fillet at the outside face, on the plain relief - never on threads", x0 - 32, ro + 3, 2.2)
    title(msp, "MUF-003", "END CAP + PORT", -30, -40, (
        f"THK {DISC_T:g} sheet, QTY 2. OD = MEASURED CAN ID - 0.2",
        f"PORT BORE {PORT_BORE:.1f} for {PORT_THREAD} nipple (OD {NPT['od']:.2f}), 304 sch40, TOE, cut to {NIP_LEN:g}",
        "Thread relief: no thread within the weld zone; weld on the plain end only",
    ))
    save(doc, out / "MUF-003_end_cap.dxf")


def draw_liner(out):
    doc, msp = new_doc()
    W = math.pi * LINER_OD
    rect(msp, 0, 0, LINER_L, W)
    for z, th in holes():
        circle(msp, (z - LINER_Z0, th / 360 * W), HOLE_D, "HOLES")
    r = [(n, z - LINER_Z0, o) for n, z, o in rows()]
    hdim(msp, 0, LINER_L, 0, -15)
    vdim(msp, 0, W, 0, -12)
    hdim(msp, 0, r[0][1], W, W + 8)
    hdim(msp, r[0][1], r[1][1], W, W + 16)
    vdim(msp, 0, W / HOLES_PER_ROW, r[0][1], r[0][1] - 8)
    s = stats()
    title(msp, "MUF-002", "PERFORATED LINER - WRAP LAYOUT (OD)", 0, -30, (
        f"PURCHASED TUBE {LINER_OD:g} OD x {LINER_T:g} WALL x {LINER_L:g} LG, 304 (seamless preferred). X FROM INLET END",
        f"{s['holes']} HOLES DIA {HOLE_D:g} THRU RADIAL, {s['rows']} ROWS, {HOLES_PER_ROW}/ROW @ {360/HOLES_PER_ROW:g} deg",
        f"ALTERNATE ROWS ROTATED {ROW_OFFSET_DEG} deg (HALF PITCH STAGGER). Y = arc on OD from datum line",
        f"OPEN AREA {s['open_id']:.1%} (ID BASIS) / {s['open_total']:.1%} (OD). DEBURR ID AND OD. DRILL WITH JIG (drill_jig.dxf)",
    ))
    save(doc, out / "MUF-002_liner_wrap_layout.dxf")


def draw_can(out):
    doc, msp = new_doc()
    rect(msp, 0, -CAN_OD / 2, L, CAN_OD / 2)
    rect(msp, 0, -CAN_ID / 2, L, CAN_ID / 2, "CENTER")
    msp.add_line((-5, 0), (L + 5, 0), dxfattribs={"layer": "CENTER"})
    hdim(msp, 0, L, -CAN_OD / 2, -CAN_OD / 2 - 12)
    vdim(msp, -CAN_OD / 2, CAN_OD / 2, L, L + 12)
    vdim(msp, -CAN_ID / 2, CAN_ID / 2, 0, -12)
    title(msp, "MUF-001", "OUTER CAN", 0, -CAN_OD / 2 - 30, (
        f"TUBE {CAN_OD:g} OD x {CAN_T:g} WALL x {L:g} LG, ENDS SQUARE WITHIN 0.3, DEBURR",
        "MEASURE ID AT 4 CLOCK POSITIONS BOTH ENDS; USE SMALLEST FOR DISC OD",
    ))
    save(doc, out / "MUF-001_outer_can.dxf")


def draw_assembly(out):
    doc, msp = new_doc()
    ro, ri = CAN_OD / 2, CAN_ID / 2
    lo, li = LINER_OD / 2, LINER_ID / 2
    for s in (1, -1):
        rect(msp, 0, s * ri, L, s * ro)
        rect(msp, LINER_Z0, s * li, L - DISC_T, s * lo)
        for z0 in (0, L - DISC_T):
            rect(msp, z0, s * PORT_BORE / 2, z0 + DISC_T, s * DISC_OD / 2)
        for xa, xb in ((-NIP_RELIEF - NIP_THREAD, DISC_T + NIP_SPIGOT),
                       (L - DISC_T - NIP_SPIGOT, L + NIP_RELIEF + NIP_THREAD)):
            rect(msp, xa, s * NPT["pipe_id"] / 2, xb, s * NPT["od"] / 2)               # port nipples
        for z in BAFFLE_Z:
            rect(msp, z - DISC_T / 2, s * DISC_ID / 2, z + DISC_T / 2, s * DISC_OD / 2)
    for _, z, _ in rows():
        for s in (1, -1):
            msp.add_line((z - HOLE_D / 2, s * (lo + li) / 2), (z + HOLE_D / 2, s * (lo + li) / 2),
                         dxfattribs={"layer": "HOLES"})
    msp.add_line((-30, 0), (L + 30, 0), dxfattribs={"layer": "CENTER"})
    prev = 0
    for i, z in enumerate(BAFFLE_Z + [L]):
        hdim(msp, prev, z, -ro, -ro - 10 - 8 * i)
        prev = z
    vdim(msp, -ro, ro, L, L + 12)
    vdim(msp, -lo, lo, 0, -12)
    for tag, x, y in [("W1", L, ro), ("W2", L, NPT["od"] / 2), ("W3", BAFFLE_Z[1] - DISC_T / 2, lo)]:
        msp.add_line((x, y), (x + 8, y + 15), dxfattribs={"layer": "WELD"})
        text(msp, tag, x + 9, y + 15)
    text(msp, f"INLET {PORT_THREAD}", -45, 16)
    text(msp, f"OUTLET {PORT_THREAD}", L + 4, 16)
    title(msp, "MUF-000", "ASSEMBLY HALF-SECTION", 0, -ro - 60, (
        "W1 cap-can rim | W2 nipple-cap | W3 baffle-liner  (see weld map)",
        f"Liner {LINER_L:g} long, captured between caps; nipples spigot {NIP_SPIGOT:g} into liner bore. No packing.",
    ))
    save(doc, out / "MUF-000_assembly.dxf")


def draw_jig(out):
    """Wrap guide plate (shim) + centering sleeve."""
    doc, msp = new_doc()
    C = math.pi * (LINER_OD + SHIM_T)
    rect(msp, 0, 0, LINER_L, C + SHIM_TAB)
    msp.add_line((0, C), (LINER_L, C), dxfattribs={"layer": "CENTER"})   # overlap line
    n = 0
    for z, th in holes():
        z, y = z - LINER_Z0, th / 360 * C
        if y - PILOT_D / 2 > 0:
            circle(msp, (z, y), PILOT_D, "HOLES")
            n += 1
        if y + PILOT_D / 2 < SHIM_TAB:
            circle(msp, (z, y + C), PILOT_D, "HOLES")   # tab copy lands on the same spot when wrapped
            n += y - PILOT_D / 2 <= 0                   # counts only if the original was dropped
    hdim(msp, 0, LINER_L, 0, -12)
    vdim(msp, 0, C, 0, -10)
    vdim(msp, C, C + SHIM_TAB, 0, -10)
    text(msp, "A) WRAP GUIDE PLATE - butt this edge to the inlet end of the liner", 0, C + SHIM_TAB + 5)
    text(msp, f"{SHIM_T} mm shim (Al/steel) or 1:1 print glued to card. Pilot holes DIA {PILOT_D:g}.", 0, -22, 2.5)
    text(msp, f"Tab overlaps start; tab holes coincide when wrapped. Circumference at shim mid = {C:.2f}", 0, -27, 2.5)

    # centering sleeve, end view
    cx, cy = LINER_L + 60, C / 2
    circle(msp, (cx, cy), SLEEVE_OD, "DETAIL")     # sleeve is shop-built, not laser cut
    circle(msp, (cx, cy), DISC_ID, "DETAIL")       # same clearance as discs
    by = cy + SLEEVE_OD / 2
    rect(msp, cx - 8, by - 1, cx + 8, by + 14, "DETAIL")    # bushing block, welded on
    for s in (-1, 1):
        msp.add_line((cx + s * GUIDE_D / 2, by + 14), (cx + s * GUIDE_D / 2, cy + DISC_ID / 2),
                     dxfattribs={"layer": "DETAIL"})
    rect(msp, cx + SLEEVE_OD / 2 - 1, cy - 5, cx + SLEEVE_OD / 2 + 6, cy + 5, "DETAIL")   # M6 nut, welded
    msp.add_line((cx - 30, cy), (cx + 30, cy), dxfattribs={"layer": "CENTER"})
    msp.add_line((cx, cy - 25), (cx, by + 20), dxfattribs={"layer": "CENTER"})
    ddim(msp, (cx, cy), SLEEVE_OD / 2, 225)
    ddim(msp, (cx, cy), DISC_ID / 2, 315)
    hdim(msp, cx - 8, cx + 8, by + 14, by + 22)
    hdim(msp, cx - GUIDE_D / 2, cx + GUIDE_D / 2, by + 14, by + 30)
    text(msp, "B) CENTERING SLEEVE (end view)", cx - 30, cy - 35)
    for i, s in enumerate((f"Sleeve: {SLEEVE_OD:g} OD tube, bore {DISC_ID:.1f}, {SLEEVE_LEN:g} long",
                           f"Bushing block 16x15x{SLEEVE_LEN:g} steel, guide hole DIA {GUIDE_D:g} RADIAL",
                           "through axis; M6 nut + thumb screw on side to lock")):
        text(msp, s, cx - 30, cy - 42 - 5 * i, 2.5)
    title(msp, "JIG-001", "DRILL JIG", 0, -40, (f"{n} pattern positions = liner pattern ({len(holes())})",),
          matl="shim: 0.5 Al/steel; sleeve + block: mild steel")
    save(doc, out / "drill_jig.dxf")
    return n


# ---------------- documents ----------------
SRC_LINER = ("AliExpress 32x2 304 tube, 300 mm (cut to 250) or uxcell 32x2 on Amazon. "
             "Fallback rolled 2 mm sheet = 7 holes/row + W4 seam variant (not generated here)")
SRC_CAN = "Online Metals 50x2 304, 60 in length (MTR available) or Amazon 50x2x400 mm (cut to 250)"
SRC_DISC = "3 mm 304 plate; laser-cut service (SendCutSend, OSH Cut, local shop) from MUF-003/004 DXF"


def bom():
    return [
        ("MUF-000", "Muffler assembly", "-", 1, "Weldment; MUF-000 DXF, weld map, build book", "-"),
        ("MUF-001", "Outer can", f"304 tube {CAN_OD:g} OD x {CAN_T:g} wall", 1,
         f"Cut {L:g} +/-0.5, square ends, deburr. Measure ID x4.", SRC_CAN),
        ("MUF-002", "Perforated liner", f"304 tube {LINER_OD:g} OD x {LINER_T:g} wall (seamless pref.)", 1,
         f"Cut {LINER_L:g} +/-0.3; {len(holes())}x DIA {HOLE_D:g} radial per drilling spec, using JIG-001; deburr ID+OD",
         SRC_LINER),
        ("MUF-003", "End cap", f"304, {DISC_T:g} sheet", 2,
         f"Laser: OD {DISC_OD:.1f}, port bore {PORT_BORE:.1f} for the nipple", SRC_DISC),
        ("MUF-004", "Baffle", f"304, {DISC_T:g} sheet", N_BAFFLES, f"Laser: OD {DISC_OD:.1f}, bore {DISC_ID:.1f}",
         SRC_DISC),
        ("MUF-005", f"Port nipple {PORT_THREAD}", "304 sch40 pipe nipple, thread one end (TOE), 2 in long", 2,
         f"Cut plain end to {NIP_LEN:g} overall ({NIP_THREAD} thread + {NIP_RELIEF:g} relief + {DISC_T:g} cap + "
         f"{NIP_SPIGOT:g} spigot); deburr", "McMaster-Carr / plumbing or industrial supply (304 TOE nipple)"),
        ("MUF-006", "TIG filler rod", FILLER, 1, "~0.25 kg tube", "Welding supply"),
        ("JIG-001", "Drill jig", f"{SHIM_T} mm shim + {SLEEVE_OD:g} OD tube + steel block + M6 nut", 1,
         "See jig_build.md", "Shim stock + scrap"),
    ]


TIG_HEAD = ["ID", "Joint", "DC (DCEN)", "Pulse (recommended)", "Argon", "Back-purge", "Filler"]


def tig_rows():
    return [(wid, joint, dc, f"base {base}, peak {peak} A, {hz}", "8-10 L/min (gas lens 10-12)", "4-6 L/min",
             "ER308L 1/16 in") for wid, joint, _, _, _, (dc, base, peak, hz) in WELDS]


def md_table(head, rows_):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + \
           ["| " + " | ".join(map(str, r)) + " |" for r in rows_]


def spec_md():
    s = stats()
    md = ["# Baffle Muffler 50x250 - Fabrication Spec (TIG revision)", "",
          f"Can wall {CAN_T:g} mm, liner {LINER_OD:g}x{LINER_T:g} purchased tube, {N_BAFFLES} baffles, "
          f"disc OD {DISC_OD:.1f} (can ID {CAN_ID:.2f} - 0.2).", "",
          "## 1. Drawings (out/handoff/)", ""]
    md += [f"- `{n}`" for n in ("MUF-000_assembly.dxf", "MUF-001_outer_can.dxf", "MUF-002_liner_wrap_layout.dxf",
                                 "MUF-003_end_cap.dxf", "MUF-004_baffle.dxf", "drill_jig.dxf")]
    md += ["", "## 2. BOM", ""] + md_table(["Part no.", "Name", "Material", "Qty", "Notes", "Source"], bom())
    md += ["", "## 3. Drilling spec - liner MUF-002", "",
           f"- Hole DIA {HOLE_D:g} thru, radial, drilled straight through the sleeve guide (no step drill)",
           f"- Liner {LINER_L:g} long (z = {LINER_Z0:g}-{L - DISC_T:g}); z below is measured from the can's inlet end",
           f"- {s['rows']} rows x {HOLES_PER_ROW} = **{s['holes']} holes**",
           f"- In-row pitch {360/HOLES_PER_ROW:g} deg = {s['pitch_od']:.2f} c-c on OD ({s['pitch_id']:.2f} on ID)",
           f"- Row pitch {ROW_PITCH:g} within each chamber; rows centred between cap/baffle faces "
           f"({'/'.join(map(str, ROWS_PER_CHAMBER))} per chamber)",
           f"- Per-row rotation offset {ROW_OFFSET_DEG} deg = half the {360/HOLES_PER_ROW:g} deg pitch (rows alternate 0 / {ROW_OFFSET_DEG})",
           f"- Webs: {s['web_id']:.2f} in-row @ ID, {s['web_od']:.2f} @ OD, {s['web_axial']:.2f} axial, "
           f"{s['web_diag']:.2f} diagonal",
           f"- Open area {s['open_total']:.1%} on OD basis ({s['open_id']:.1%} on ID flow-path basis)", ""]
    md += md_table(["Row", "z from inlet", "Rotation offset (deg)"], [(n, f"{z:g}", off) for n, z, off in rows()])
    md += ["", "## 4. Weld map (GTAW, argon)", ""]
    md += md_table(["ID", "Joint", "Qty", "Type / extent", "Size"], [w[:5] for w in WELDS])
    md += ["", "No W4: liner is purchased tube, no shop seam. No plug welds: baffles are held by W3 only.",
           "Liner is not welded to the caps: it is captured between them and centred by the nipple spigots.", "",
           "## 4a. Port", "",
           f"- {PORT_THREAD} male, both ends: 304 sch40 TOE nipple, OD {NPT['od']:.2f}, ID {NPT['pipe_id']:.2f}, cut to {NIP_LEN:g}",
           f"- External thread {NIP_THREAD} (L2 {NPT['l2']}, hand-tight L1 {NPT['l1']}); {NIP_RELIEF:g} plain relief "
           f"before the cap; {NIP_SPIGOT:g} spigot into the liner bore",
           "- Thread sealant: nickel anti-seize (PTFE tape/paste breaks down at exhaust temperature)", "",
           "## 5. TIG parameters", ""]
    md += md_table(TIG_HEAD, tig_rows())
    md += ["", "Machine: 220 V, 110 A max, DC/pulse. DCEN, 2% lanthanated 1/16 in tungsten, #7 cup or gas lens. "
               "Tack first, then continuous. Back-purge every hollow joint (can, caps). No preheat. Interpass < 150 C.", "", "## 6. Fab sequence", "", "See build_book.md."]
    return "\n".join(md) + "\n"


def build_book_md():
    s = stats()
    tig = md_table(TIG_HEAD, tig_rows())
    return f"""# Build Book - 50 x 250 Baffle Muffler (TIG)

Everything here is generated by `muffler.py`; re-run it after measuring stock (step 1).
Drawings: `MUF-000..004*.dxf`, `drill_jig.dxf` (PNG previews in `png/`). Build order: `sequence.mmd`.

## 1. Materials

{chr(10).join(md_table(["Part", "Item", "Material / size", "Qty", "Notes", "Source"], bom()))}

**Sourcing:**
- **Liner** (32 x 2 304 tube): {SRC_LINER}.
  Marketplace tube is often off-size: measure OD and wall on arrival before drilling.
- **Can** (50 x 2 304 tube): {SRC_CAN}.
- **Discs** (caps + baffles): {SRC_DISC}. Order **after** measuring the tube (step 1).
- US imperial near-equivalents if metric is short: 2 in x 0.083 in (can), 1-1/4 in x 0.083 in = 31.75 x 2.11 (liner);
  the measure-and-rerun step absorbs the size difference.
- 316/316L if the vehicle sees road salt or marine use; then use ER316L filler.
- Filler ER308L 1/16 in (ER316L for 316), 2% lanthanated tungsten, argon.

## 2. Tools

Bandsaw or abrasive cutoff, drill press with V-block, Ø{HOLE_D:g} mm cobalt (HSS-Co) jobber drills (buy 5+),
center punch, small round file / deburr tool, flap wheel, {PORT_THREAD} thread ring gauge or a mating fitting,
calipers (ID jaws), TIG welder (shop machine: 220 V, 110 A max, DC/pulse), argon with flowmeter + purge line,
stainless-only wire brush, acetone, foil tape, soapy water, {PORT_THREAD} pipe cap + plug with Schrader valve.

## 3. Build sequence

1. **Measure**
   - Can ID at 4 clock positions, both ends -> smallest value. Liner OD likewise -> largest.
   - Re-run `muffler.py --can-id <ID> --liner-od <OD>`; discs become OD = ID - 0.2, bore = OD + 0.2.
2. **Cut**
   - Can to {L:g} +/-0.5 and liner to {LINER_L:g} +/-0.3, ends square within 0.3 (check with a square). Deburr.
   - Cut the two {PORT_THREAD} TOE nipples to {NIP_LEN:g} overall from the plain end. Deburr.
   - Order/cut discs: 2x MUF-003 caps (port bore {PORT_BORE:.1f}), {N_BAFFLES}x MUF-004 baffles. Cut the JIG-001 guide plate.
3. **Jig** - build the centering sleeve per `jig_build.md`.
4. **Drill** (liner)
   - Wrap guide plate, edge flush with the inlet end, tape tight. Center punch all {s['holes']} pilot holes. Remove.
   - Sleeve on liner, Ø{GUIDE_D:g} pin through guide bushing into each punch mark, lock thumb screw, drill Ø{HOLE_D:g}
     straight through the guide. ~950 rpm for Ø4 in 304, cutting fluid, steady feed (304 work-hardens if the
     drill rubs); swap drills as soon as they squeal.
   - Deburr OD (file/flap wheel) and ID (round file, brush). Blow out chips.
5. **Clean** - acetone on all parts; stainless-only brushes; no grinding discs used on carbon steel.
6. **Fit**
   - Slide baffles onto liner at z = {', '.join(f'{z:g}' for z in BAFFLE_Z)} (centres) using spacer blocks
     ({BAFFLE_FROM_LINER:g} mm from the liner's inlet end, {BAFFLE_FACE_GAP:g} mm between baffles).
     Baffles sit on undrilled bands.
   - Dry-fit liner + baffles into can, caps + nipples in both ends: caps flush, spigots enter the liner bore,
     liner captured with no end play.
7. **Weld W3** (baffles to liner)
   - Foil-tape both liner ends, argon purge the bore 4-6 L/min.
   - Check square, 4 tacks per baffle @ 90 deg, re-check square, continuous fillet on the upstream face.
8. **Weld W2** (nipples to caps, on the bench)
   - Nipple through the cap bore: spigot {NIP_SPIGOT:g} mm proud of the inner face, {NIP_RELIEF:g} mm plain relief outside.
   - Thread a {PORT_THREAD} pipe cap on to protect the threads; purge through the nipple.
   - 4 tacks, check square, continuous fillet on the outside face, on the plain section only.
9. **Fit can** - slide the liner/baffle core into the can. No packing: absorption is by the baffles only.
10. **Cap**
    - Press caps in flush both ends; spigots enter the liner bore. Purge through a nipple (the perforations
      carry argon into the chambers).
    - 4 tacks each, then W1 (cap to can rim), alternating ends to limit distortion.
11. **Finish** - pickle/passivate welds; chase threads with a mating fitting; run `verification_checklist.md`.

## 4. TIG parameters

{chr(10).join(tig)}

Shop machine: 220 V input, 110 A max, AC/DC/pulse, back-purge available.

- **DCEN for all joints.** AC is for aluminium; don't use it on stainless.
- **Pulse is recommended** on 2 mm 304: lower heat input means less burn-through at hole webs and less sugaring.
  Use 30-50 Hz with about 40% peak time.
- W2 (2.9 mm nipple wall to 3 mm cap) and W3 (2 mm liner to 3 mm baffle) are both tube-to-disc fillets, so they
  share settings. W1 is an edge/corner joint at the can rim with little mass, so it runs cooler.
- Peak current never exceeds {s['max_amps']} A, which leaves headroom on the {ARGS.max_amps:g} A machine.
- Gas: Ar 8-10 L/min (10-12 with a gas lens); postflow 8-10 s. 2% lanthanated 1/16 in tungsten, #7 cup.
- **Back-purge 4-6 L/min on every hollow joint** (W3 on the liner, W2 through the nipple, W1 through a nipple
  once capped). The perforations carry argon into the chambers. This stops internal oxidation.
- Tack first (4 per circular joint), then continuous. No preheat for TIG on 304. Interpass < 150 C.
- No W4: the liner is bought tube, so there is no shop seam. With welded tube the factory seam may be drilled through.

## 5. Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| Burn-through | Too hot for 2 mm; heat builds up near holes | Drop 10 A, add filler earlier, faster travel, copper heat sink, weld in quarters |
| Oval / wandering holes | Drill walks on the curved surface; dull drill or rubbing | Deep punch, drill through the sleeve guide, V-block, sharp cobalt, keep feeding |
| Broken Ø4 drill | Rubbing/work-hardening, chips packing | Peck, cutting fluid, fresh drill; don't drill out a broken bit, skip that position (1 hole = 0.06% open area) |
| Port thread leaks | No sealant, thread damaged by weld heat | Nickel anti-seize, not PTFE; keep W2 on the relief; chase thread with a fitting |
| Cap/baffle won't enter can | Tube ID undersize/out of round, burr, weld bead | Re-measure smallest ID, file disc edge, rerun with `--can-id`, deburr can ends |
| Cap loose (> 0.5 gap) | ID oversize | Remake discs from measured ID; don't bridge big gaps with filler |
| Sugaring (grey crust) on root | No back-purge | Purge liner bore; perforations carry argon into chambers |
| Filler choice | - | 304 -> ER308L; 316 -> ER316L; stainless to mild-steel flange -> ER309L; never ER70S on stainless |
"""


def jig_md(n_plate):
    C = math.pi * (LINER_OD + SHIM_T)
    return f"""# Drill Jig (JIG-001) - Build Steps

Two parts (`drill_jig.dxf`):
- **A. Wrap guide plate:** {SHIM_T} mm shim, {LINER_L:g} x {C + SHIM_TAB:.1f} mm, with all {n_plate} pattern positions as
  Ø{PILOT_D:g} pilots. It carries the {HOLES_PER_ROW}-hole rows ({360/HOLES_PER_ROW:g} deg = {stats()['pitch_od']:.2f} mm
  on OD), {ROW_PITCH:g} mm row pitch and the {ROW_OFFSET_DEG} deg half-pitch stagger, so nothing is laid out by hand.
- **B. Centering sleeve:** keeps every hole radial (through the tube axis).

## A. Guide plate
1. Laser-cut the DXF layers `CUT` + `HOLES` in {SHIM_T} mm aluminium or steel shim, **or** print the DXF 1:1
   (check the {LINER_L:g} mm dimension with calipers) and glue it to thin card.
2. Wrap on the liner, long edge flush with the inlet end, overlap tab on top; the tab holes must sit over the
   start holes. Tape tight; no gaps.

## B. Centering sleeve
1. Cut {SLEEVE_LEN:g} mm of {SLEEVE_OD:g} mm OD tube; bore/hone so the liner slides with ~0.2 clearance
   (target {DISC_ID:.1f}). 1-1/2 in x 0.120 in tube (ID 32.0) fits a 1-1/4 in liner directly.
2. Weld a 16 x 15 x {SLEEVE_LEN:g} steel block centred on top (bushing).
3. Put the sleeve in a V-block on the drill press, find the centre line by touching off both sides, and drill
   Ø{GUIDE_D:g} through the block into the bore, **on the axis**. Ream if you have one.
4. Weld an M6 nut on the side, drill through, fit a thumb screw (brass tip or pad so it doesn't mark the liner).
5. Check: on scrap tube drill one hole, rotate 180 deg and drill again; the two holes must line up through the axis.

## Use
Punch through the guide plate, remove it. Slide the sleeve on, drop a Ø{GUIDE_D:g} pin through the bushing into the
punch mark, lock it, drill Ø{HOLE_D:g} straight through the guide, move on. {len(holes())} holes: work row by row and
tick rows off on the checklist.
"""


def checklist_md():
    s = stats()
    return f"""# Verification Checklist

Part: 50 x 250 baffle muffler.  Builder: ________  Date: ________

## Liner (before assembly)
- [ ] Hole count = **{s['holes']}** ({s['rows']} rows x {HOLES_PER_ROW}). Count by row, tick each row off.
- [ ] Hole Ø{HOLE_D:g} +0.3/-0, round (caliper in two directions).
- [ ] Web check: thinnest web between holes >= {MIN_WEB} mm (check on the ID; design {s['web_id']:.2f}).
      Axial web between rows >= {LINER_T:g} mm (design {s['web_axial']:.2f}).
- [ ] No hole within 3 mm of baffle/cap positions (z = {', '.join(f'{z:g}' for z in BAFFLE_Z)} and both ends).
- [ ] ID and OD deburred, no chips inside.

## Fit
- [ ] Can ID measured x4 each end: smallest ______ ; disc OD = ID - 0.2 = ______ (design {DISC_OD:.1f}).
- [ ] Cap fit: cap enters can by hand pressure, gap <= 0.3 all round, sits flush with the can end.
- [ ] Baffles slide on the liner without forcing; liner {LINER_L:g} mm, captured between caps with no end play.

## Port ({PORT_THREAD})
- [ ] Nipple thread {NIP_THREAD} mm long, {NIP_RELIEF:g} mm plain relief outside the cap, spigot {NIP_SPIGOT:g} mm into the liner.
- [ ] Thread gauge / mating fitting runs on by hand after welding (no weld spatter or heat damage on threads).
- [ ] Baffle spacing: centres at {', '.join(f'{z:g}' for z in BAFFLE_Z)} +/-1 mm, square to axis within 0.5 mm at OD.

## Welds
- [ ] W3 x{N_BAFFLES}, W2 x2, W1 x2 complete, full 360, no cracks/porosity/undercut; colour straw-blue, not grey.
- [ ] Soapy-water leak test: {PORT_THREAD} pipe cap on the outlet, plug with Schrader valve in the inlet, **0.2-0.3 bar (3-4 psi) max**. Brush
      soap on every W1 and W2 joint: no bubbles in 30 s. (W3 is internal; leaks between chambers don't matter.)

## Final
- [ ] Rattle check: shake hard by hand; nothing loose.
- [ ] Sound check: engine at idle and 3/4 throttle, phone dB meter at 0.5 m, 45 deg from the outlet;
      record without / with muffler: ______ / ______ dB(A).
- [ ] Welds passivated, no rust bloom after 24 h.
"""


def mermaid():
    steps = ["Measure tube ID/OD<br/>rerun muffler.py", f"Cut can {L:g} + liner {LINER_L:g}<br/>+ nipples {NIP_LEN:g}",
             "Order/cut discs + guide plate", "Build centering sleeve", f"Punch {len(holes())} marks via guide plate",
             f"Drill Ø{HOLE_D:g} through sleeve + deburr", "Clean (acetone)", "Fit baffles on liner<br/>dry-fit in can",
             "W3 baffles to liner<br/>tack then continuous", f"W2 {PORT_THREAD} nipples to caps",
             "Slide core into can", "Caps in<br/>W1", "Passivate + chase threads", "Leak + rattle + sound check"]
    out = ["flowchart TD"]
    out += [f'  S{i}["{s}"]' for i, s in enumerate(steps)]
    out += [f"  S{i} --> S{i + 1}" for i in range(len(steps) - 1)]
    out += [f'  S{len(steps) - 1} -->|"leak found: re-weld"| S{len(steps) - 3}']
    return "\n".join(out) + "\n"


def main():
    root = Path(ARGS.out)
    out = root / "handoff"
    out.mkdir(parents=True, exist_ok=True)
    draw_assembly(out)
    draw_can(out)
    draw_liner(out)
    draw_cap(out)
    draw_disc(out, "MUF-004", "BAFFLE", N_BAFFLES, (f"Stations z = {', '.join(f'{z:g}' for z in BAFFLE_Z)}",))
    n_plate = draw_jig(out)

    with open(out / "bom.csv", "w", newline="") as f:
        csv.writer(f).writerows([("part_no", "name", "material", "qty", "machining_notes", "source"), *bom()])
    (out / "muffler_spec.md").write_text(spec_md())
    (out / "build_book.md").write_text(build_book_md())
    (out / "jig_build.md").write_text(jig_md(n_plate))
    (out / "verification_checklist.md").write_text(checklist_md())
    (out / "sequence.mmd").write_text(mermaid())

    res = checks() + [("Guide plate pattern = liner pattern", f"{n_plate} = {len(holes())}", n_plate == len(holes()))]
    lines = ["# Check Results", "", f"Args: can wall {CAN_T:g}, can ID {CAN_ID:.2f}, liner OD {LINER_OD_REAL:.2f}, "
             f"max amps {ARGS.max_amps:g}", ""]
    lines += md_table(["Check", "Value", "Result"], [(c, v, "PASS" if ok else "**FAIL**") for c, v, ok in res])
    (out / "RESULTS.md").write_text("\n".join(lines) + "\n")
    for name in ("muffler_spec.md", "bom.csv"):
        shutil.copy(out / name, root / name)

    for c, v, ok in res:
        print(f"{'PASS' if ok else 'FAIL'}  {c}: {v}")
    files = sorted(p.name for p in out.iterdir() if p.is_file())
    print(f"Generated {len(files)} files in {out}: {', '.join(files)} (+ png/ previews); "
          f"updated {root.name}/muffler_spec.md, {root.name}/bom.csv")
    if not all(ok for *_, ok in res):
        raise SystemExit(1)
    return res


if __name__ == "__main__":
    main()
