#!/usr/bin/env python3
"""Build out/handoff/build_book.pdf: regenerates the package via muffler.py, then renders
drawings + 3D views and lays out one self-contained PDF.

Run:  .venv/bin/python build_pdf.py [same args as muffler.py, e.g. --can-id 46.0 --liner-od 32.0]
Needs: pip install ezdxf matplotlib reportlab
"""
import html
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

import muffler as M

OUT = Path(M.ARGS.out) / "handoff"
IMG = OUT / "pdf_img"

# ---------------- drawings: DXF -> print-friendly PNG ----------------
DRAWINGS = [
    ("MUF-000_assembly.dxf", "MUF-000 Assembly half-section: can, liner, caps, 4 baffles; weld callouts W1-W3."),
    ("MUF-001_outer_can.dxf", "MUF-001 Outer can: 50 OD x 2 wall x 250 tube, ends square, measure ID x4."),
    ("MUF-002_liner_wrap_layout.dxf", "MUF-002 Liner wrap layout (OD): 112 x Ø9 holes, 8/row, 14 rows, 22.5° stagger."),
    ("MUF-003_end_cap.dxf", "MUF-003 End cap (x2): 3 mm disc, OD = can ID - 0.2, bore = liner OD + 0.2 (port)."),
    ("MUF-004_baffle.dxf", "MUF-004 Baffle (x4): same 3 mm blank as the cap, stations at 50/100/150/200."),
    ("drill_jig.dxf", "JIG-001 Drill jig: 0.5 mm wrap-around shim (112 pilots) + centring sleeve with Ø4 guide."),
]


def render_dxf(name):
    doc = ezdxf.readfile(OUT / name)
    fig = plt.figure(figsize=(10, 5.5))
    ax = fig.add_axes([0, 0, 1, 1])
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.BLACK)
    Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(doc.modelspace())
    png = IMG / (Path(name).stem + ".png")
    fig.savefig(png, dpi=130, facecolor="white")
    plt.close(fig)
    return png


# ---------------- 3D views: isometric painter's-algorithm renderer ----------------
# Axis of the muffler = x, z up. Faces are depth-sorted with back-face culling; tubes are finely
# tessellated so mean-depth sorting stays correct.
STEEL, STEEL_IN, DISC, PACK, HOLE = (0.74, 0.77, 0.80), (0.55, 0.58, 0.62), (0.45, 0.52, 0.60), (0.85, 0.68, 0.38), (0.12, 0.13, 0.15)
CAN_R, CAN_RI = M.CAN_OD / 2, M.CAN_ID / 2
LIN_R, LIN_RI = M.LINER_OD / 2, M.LINER_ID / 2
D_R, D_RI = M.DISC_OD / 2, M.DISC_ID / 2
TAU = 2 * math.pi


class Scene:
    def __init__(self, el=24, az=-62):
        el, az = math.radians(el), math.radians(az)
        self.e = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])   # toward eye
        self.r = np.array([-math.sin(az), math.cos(az), 0.0])
        self.u = np.cross(self.e, self.r)
        self.light = (self.e + np.array([0, 0.3, 0.8])) / np.linalg.norm(self.e + np.array([0, 0.3, 0.8]))
        self.faces = []        # (pts Nx3, rgb, normal or None)
        self.overlay = []      # drawn after the sorted faces (holes lie flush on the liner)

    def p2(self, p):
        p = np.asarray(p, float)
        return p @ self.r, p @ self.u

    def tube(self, x0, x1, ri, ro, rgb, t0=0.0, t1=TAU, off=(0, 0, 0), inner=True, nt=96, seg=8.0):
        off = np.asarray(off, float)
        ts = np.linspace(t0, t1, max(3, int(nt * (t1 - t0) / TAU)) + 1)
        xs = np.linspace(x0, x1, max(1, math.ceil((x1 - x0) / seg)) + 1)
        P = lambda x, r, t: off + (x, r * math.cos(t), r * math.sin(t))
        for ta, tb in zip(ts, ts[1:]):
            tm = (ta + tb) / 2
            n = np.array([0, math.cos(tm), math.sin(tm)])
            for xa, xb in zip(xs, xs[1:]):
                self.faces.append(([P(xa, ro, ta), P(xb, ro, ta), P(xb, ro, tb), P(xa, ro, tb)], rgb, n))
                if inner:
                    self.faces.append(([P(xa, ri, ta), P(xb, ri, ta), P(xb, ri, tb), P(xa, ri, tb)], STEEL_IN, -n))
            for x, nx in ((x0, -1), (x1, 1)):
                self.faces.append(([P(x, ri, ta), P(x, ro, ta), P(x, ro, tb), P(x, ri, tb)], rgb, np.array([nx, 0, 0])))
        if t1 - t0 < TAU - 1e-6:
            for t, s in ((t0, -1), (t1, 1)):
                n = s * np.array([0, -math.sin(t), math.cos(t)])
                for xa, xb in zip(xs, xs[1:]):
                    self.faces.append(([P(xa, ri, t), P(xb, ri, t), P(xb, ro, t), P(xa, ro, t)], rgb, n))

    def disk(self, x, r, rgb, nx, off=(0, 0, 0), nt=96):
        off = np.asarray(off, float)
        self.faces.append(([off + (x, r * math.cos(t), r * math.sin(t)) for t in np.linspace(0, TAU, nt)], rgb,
                           np.array([nx, 0, 0])))

    def holes(self, off=(0, 0, 0), t0=0.0, t1=TAU, dx=0.0):
        off = np.asarray(off, float)
        for z, th in M.holes():
            th = math.radians(th)
            th = th if t0 <= th <= t1 else th + TAU
            if not t0 <= th <= t1:
                continue
            d = (M.HOLE_D / 2) / LIN_R
            pts = [off + (dx + z + M.HOLE_D / 2 * math.cos(u), (LIN_R + 0.15) * math.cos(th + d * math.sin(u)),
                          (LIN_R + 0.15) * math.sin(th + d * math.sin(u))) for u in np.linspace(0, TAU, 16)]
            self.overlay.append((pts, HOLE, np.array([0, math.cos(th), math.sin(th)])))

    def draw(self, ax):
        polys, cols, depth = [], [], []
        for pts, rgb, n in self.faces:
            if n is not None and n @ self.e <= 0:
                continue
            P = np.asarray(pts)
            polys.append(np.c_[P @ self.r, P @ self.u])
            shade = 0.45 + 0.55 * max(0.0, float(n @ self.light)) if n is not None else 1
            cols.append(tuple(min(1, c * shade) for c in rgb))
            depth.append(float((P @ self.e).mean()))
        order = list(np.argsort(depth))
        for pts, rgb, n in self.overlay:   # ponytail: overlay assumes nothing sits in front of the liner (true for these views)
            if n @ self.e > 0:
                P = np.asarray(pts)
                polys.append(np.c_[P @ self.r, P @ self.u])
                cols.append(rgb)
                order.append(len(polys) - 1)
        from matplotlib.collections import PolyCollection
        ax.add_collection(PolyCollection([polys[i] for i in order], facecolors=[cols[i] for i in order],
                                         edgecolors=[cols[i] for i in order], linewidths=0.25))
        ax.autoscale_view()
        ax.set_aspect("equal")
        ax.set_axis_off()


def callout(ax, sc, p, text, dxy):
    x, y = sc.p2(p)
    ax.annotate(text, (x, y), (x + dxy[0], y + dxy[1]), fontsize=8, ha="center",
                arrowprops=dict(arrowstyle="-", lw=0.6, color="#333"),
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#999", lw=0.5))


def dim(ax, sc, p0, p1, text, off):
    (x0, y0), (x1, y1) = sc.p2(p0), sc.p2(p1)
    ax.annotate("", (x0 + off[0], y0 + off[1]), (x1 + off[0], y1 + off[1]),
                arrowprops=dict(arrowstyle="<->", lw=0.7, color="#1f3b57"))
    for x, y in ((x0, y0), (x1, y1)):
        ax.plot([x, x + off[0] * 1.1], [y, y + off[1] * 1.1], lw=0.4, color="#1f3b57")
    ax.text((x0 + x1) / 2 + off[0], (y0 + y1) / 2 + off[1] + 2, text, fontsize=8, ha="center", color="#1f3b57",
            bbox=dict(fc="white", ec="none", pad=0.5))


def save_view(fig, name):
    png = IMG / name
    fig.savefig(png, dpi=140, facecolor="white", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    return png


def caps_and_core(sc, t0=0.0, t1=TAU, packing=True):
    for a, b in M.CHAMBERS:
        if packing:
            sc.tube(a, b, LIN_R + 0.3, CAN_RI - 0.3, PACK, t0, t1, inner=False)
    for x in [0, M.L - M.DISC_T] + [z - M.DISC_T / 2 for z in M.BAFFLE_Z]:
        sc.tube(x, x + M.DISC_T, D_RI, D_R, DISC, t0, t1, inner=False)


def view_assembled():
    sc, L = Scene(), M.L
    sc.tube(0, L, CAN_RI, CAN_R, STEEL, inner=False)
    sc.tube(-0.01, L + 0.01, LIN_RI, LIN_R, STEEL)
    for x in (0, L):
        sc.tube(x - 0.02 if x else 0.02, x - 0.02 if x else 0.02, D_RI, D_R, DISC, inner=False)
    fig, ax = plt.subplots(figsize=(10, 3.6))
    sc.draw(ax)
    dim(ax, sc, (0, 0, -CAN_R), (L, 0, -CAN_R), f"{L:g}", (0, -18))
    callout(ax, sc, (L * 0.55, 0, CAN_R), f"MUF-001 can Ø{M.CAN_OD:g} x {M.CAN_T:g}, 304", (0, 22))
    callout(ax, sc, (L, 0, (D_R + CAN_R) / 2), "cap welds W1 (rim) + W2 (port)", (10, 30))
    callout(ax, sc, (L, 0, -LIN_RI * 0.4), f"outlet port Ø{M.LINER_ID:g} (liner bore)", (45, -22))
    return save_view(fig, "3d_assembled.png")


def view_cutaway():
    sc, L = Scene(el=28, az=-58), M.L
    tc = math.atan2(sc.e[2], sc.e[1])                     # angle facing the camera
    t0, t1 = tc + math.radians(55), tc + TAU - math.radians(55)
    sc.tube(0, L, CAN_RI, CAN_R, STEEL, t0, t1)
    caps_and_core(sc, t0, t1)
    sc.tube(0, L, LIN_RI, LIN_R, STEEL)
    sc.holes(t0=tc - math.radians(42), t1=tc + math.radians(42))   # only liner exposed by the open wedge
    fig, ax = plt.subplots(figsize=(10, 4.2))
    sc.draw(ax)
    up = lambda x, r: (x, r * math.cos(tc), r * math.sin(tc))
    callout(ax, sc, (M.BAFFLE_Z[0], 0, D_R), "baffle 3 mm (W3 to liner)", (-30, 26))
    callout(ax, sc, (M.BAFFLE_Z[2], 0, D_R), f"baffles @ {', '.join(f'{z:g}' for z in M.BAFFLE_Z)}", (20, 30))
    callout(ax, sc, (M.L - 2, 0, D_R - 2), "end cap 3 mm (W1 + W2)", (25, 22))
    callout(ax, sc, up((M.CHAMBERS[1][0] + M.CHAMBERS[1][1]) / 2, (LIN_R + CAN_RI) / 2),
            "core fill (packing)", (-10, -30))
    callout(ax, sc, up(M.rows()[9][1], LIN_R), f"liner Ø{M.LINER_OD:g} x {M.LINER_T:g}, {len(M.holes())} x Ø{M.HOLE_D:g}",
            (40, -30))
    dim(ax, sc, (0, 0, -CAN_R), (M.BAFFLE_Z[0], 0, -CAN_R), f"{M.BAFFLE_Z[0]:g}", (0, -16))
    return save_view(fig, "3d_cutaway.png")


def view_exploded():
    sc, L = Scene(el=20, az=-62), M.L
    lv, cv, pv, bv = 0, 120, 60, -62                      # vertical levels
    sc.tube(0, L, LIN_RI, LIN_R, STEEL, off=(0, 0, lv))
    sc.holes(off=(0, 0, lv))
    sc.tube(0, L, CAN_RI, CAN_R, STEEL, off=(0, 0, cv))
    for a, b in M.CHAMBERS:
        sc.tube(a + 1.5, b - 1.5, LIN_R + 0.5, CAN_RI - 0.5, PACK, off=(0, 0, pv), inner=False)
    for z in M.BAFFLE_Z:
        sc.tube(z - M.DISC_T / 2, z + M.DISC_T / 2, D_RI, D_R, DISC, off=(0, 0, bv), inner=False)
    caps = (-75, L + 75 - M.DISC_T)
    for x in caps:
        sc.tube(x, x + M.DISC_T, D_RI, D_R, DISC, off=(0, 0, lv), inner=False)
    fig, ax = plt.subplots(figsize=(10, 6))
    sc.draw(ax)
    seg = lambda p, q: ax.plot(*zip(sc.p2(p), sc.p2(q)), ls="--", lw=0.6, color="#666", zorder=0)
    for z in M.BAFFLE_Z:
        seg((z, 0, bv + D_R), (z, 0, lv - LIN_R))
    seg((-72, 0, lv), (0, 0, lv)), seg((L, 0, lv), (L + 72, 0, lv))
    seg((L / 2, 0, cv - CAN_R), (L / 2, 0, pv + CAN_RI))
    callout(ax, sc, (L * 0.6, 0, cv + CAN_R), f"MUF-001 can Ø{M.CAN_OD:g} x {M.CAN_T:g} x {L:g}", (0, 20))
    callout(ax, sc, (L * 0.75, 0, pv + CAN_RI), "MUF-005 core fill (5 bands)", (40, 14))
    callout(ax, sc, (L * 0.45, 0, lv + LIN_R), f"MUF-002 liner Ø{M.LINER_OD:g} x {M.LINER_T:g}, {len(M.holes())} holes",
            (0, 22))
    callout(ax, sc, (M.BAFFLE_Z[1], 0, bv - D_R), f"MUF-004 baffles x{M.N_BAFFLES} @ "
            f"{', '.join(f'{z:g}' for z in M.BAFFLE_Z)}", (20, -20))
    callout(ax, sc, (caps[0], 0, lv - D_R), "MUF-003 cap (inlet)", (-10, -22))
    callout(ax, sc, (caps[1], 0, lv - D_R), "MUF-003 cap (outlet)", (10, -22))
    return save_view(fig, "3d_exploded.png")


# ---------------- PDF ----------------
SS = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=SS["Heading1"], fontSize=16, spaceBefore=4, spaceAfter=8,
                    textColor=colors.HexColor("#1f3b57"))
H2 = ParagraphStyle("H2", parent=SS["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=4)
BODY = ParagraphStyle("B", parent=SS["BodyText"], fontSize=9.5, leading=12.5)
SMALL = ParagraphStyle("S", parent=BODY, fontSize=8, leading=10)
CAP = ParagraphStyle("C", parent=BODY, fontSize=8.5, textColor=colors.HexColor("#444"), spaceAfter=10)
FRAME_W = letter[0] - 36 * mm

TOOLS = {  # build-book step number -> exact tools
    1: "Calipers with ID jaws (0.01 mm), laptop with muffler.py",
    2: "Bandsaw or abrasive cut-off saw, machinist square, flat file, deburr tool, marker",
    3: "Drill press, V-block, Ø4 mm cobalt drill, TIG/MIG for tacking block + M6 nut, M6 thumb screw, file",
    4: "Drill press, V-block, centre punch + hammer, Ø4 mm pin, Ø4 mm cobalt drill, step drill to Ø9 (or Ø9 cobalt), "
       "cutting fluid, round file, deburr tool",
    5: "Acetone, lint-free rags, stainless-only wire brush, nitrile gloves",
    6: "Spacer blocks 48.5 mm and 47 mm, square, calipers",
    7: "TIG (DCEN/pulse), argon + purge line, foil tape, ER308L 1/16 in, stainless brush",
    8: "Stainless wool, basalt or E-glass packing, masking tape, gloves + dust mask (fibres)",
    9: "Rubber mallet, gloves",
    10: "TIG, argon purge, foil tape, clamps, ER308L 1/16 in",
    11: "Pickling paste (acid: gloves + eye protection), Schrader-valve plug, expansion plug, soapy water, brush",
}


def md_inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", s)
    return s


def section(md, start):
    lines = md.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith(start)) + 1
    out = []
    for ln in lines[i:]:
        if ln.startswith("## ") and not ln.startswith(start):
            break
        out.append(ln)
    return out


def build_steps():
    """Parse build_book.md section 3 -> numbered steps with sub-bullets + tools."""
    steps = []
    for ln in section((OUT / "build_book.md").read_text(), "## 3."):
        m = re.match(r"^(\d+)\. (.*)$", ln)
        if m:
            steps.append([int(m[1]), m[2], []])
        elif ln.strip().startswith("- ") and steps:
            steps[-1][2].append(ln.strip()[2:])
        elif ln.strip() and steps:   # continuation line
            if steps[-1][2]:
                steps[-1][2][-1] += " " + ln.strip()
            else:
                steps[-1][1] += " " + ln.strip()
    flow = []
    for n, head, subs in steps:
        block = [Paragraph(f"<b>Step {n}.</b> {md_inline(head)}", BODY)]
        block += [Paragraph(f"&bull; {md_inline(s)}", ParagraphStyle("li", parent=BODY, leftIndent=14)) for s in subs]
        block.append(Paragraph(f"<i>Tools:</i> {html.escape(TOOLS.get(n, '-'))}",
                               ParagraphStyle("t", parent=SMALL, leftIndent=14, textColor=colors.HexColor("#1f5f3a"))))
        block.append(Spacer(1, 6))
        flow.append(KeepTogether(block))
    return flow


def checklist():
    flow, items = [], []

    def flush():
        if items:
            t = Table([["[   ]", Paragraph(md_inline(x), BODY)] for x in items], colWidths=[12 * mm, FRAME_W - 12 * mm])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTNAME", (0, 0), (0, -1), "Courier"),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
            flow.append(t)
            items.clear()

    for ln in (OUT / "verification_checklist.md").read_text().splitlines()[1:]:
        if ln.startswith("## "):
            flush()
            flow.append(Paragraph(ln[3:], H2))
        elif ln.startswith("- [ ] "):
            items.append(ln[6:])
        elif ln.startswith("      ") and items:
            items[-1] += " " + ln.strip()
        elif ln.strip():
            flush()
            flow.append(Paragraph(md_inline(ln), BODY))
    flush()
    return flow


def table(head, rows, widths, font=8):
    data = [[Paragraph(f"<b>{html.escape(str(h))}</b>", SMALL) for h in head]] + \
           [[Paragraph(md_inline(str(c)), ParagraphStyle("c", parent=SMALL, fontSize=font)) for c in r] for r in rows]
    t = Table(data, colWidths=[w * FRAME_W for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfe6ee")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa5b1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
    ]))
    return t


def img(path, width=FRAME_W, max_h=None):
    from reportlab.lib.utils import ImageReader
    w, h = ImageReader(str(path)).getSize()
    if max_h and width * h / w > max_h:
        width = max_h * w / h
    return Image(str(path), width=width, height=width * h / w)


def footer(c, doc):
    c.saveState()
    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.HexColor("#666"))
    c.drawString(18 * mm, 10 * mm, "50 x 250 Baffle Muffler - Build Book (generated by muffler.py / build_pdf.py)")
    c.drawRightString(letter[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    c.restoreState()


def main():
    res = M.main()                # regenerate DXFs/docs so the PDF matches the script exactly
    IMG.mkdir(exist_ok=True)
    s = M.stats()
    drawings = [(render_dxf(n), cap) for n, cap in DRAWINGS]
    v_asm, v_cut, v_exp = view_assembled(), view_cutaway(), view_exploded()

    story = [Spacer(1, 20 * mm),
             Paragraph("50 x 250 mm Baffle Muffler", ParagraphStyle("T", parent=SS["Title"], fontSize=26)),
             Paragraph("Build Book - home TIG shop", ParagraphStyle("ST", parent=SS["Title"], fontSize=14,
                                                                    textColor=colors.HexColor("#555"))),
             Spacer(1, 8 * mm), img(v_asm), Spacer(1, 6 * mm)]
    summary = [
        ("Outer can", f"Ø{M.CAN_OD:g} x {M.CAN_T:g} mm wall x {M.L:g} mm, 304"),
        ("Liner", f"Ø{M.LINER_OD:g} x {M.LINER_T:g} mm wall x {M.L:g} mm, 304 tube (bought, no seam)"),
        ("Perforation", f"{s['holes']} x Ø{M.HOLE_D:g} mm, {M.HOLES_PER_ROW}/row, {s['rows']} rows @ {M.ROW_PITCH:g} mm, "
                        f"{M.ROW_OFFSET_DEG}° stagger; {s['open_total']:.1%} open (OD basis) / {s['open_id']:.1%} (ID basis)"),
        ("Caps / baffles", f"{M.DISC_T:g} mm 304 discs: 2 caps + {M.N_BAFFLES} baffles @ "
                           f"{', '.join(f'{z:g}' for z in M.BAFFLE_Z)} mm; OD = measured can ID - 0.2"),
        ("Welding", f"TIG DCEN / pulse, ER308L 1/16 in, max {s['max_amps']} A (machine 110 A, 220 V)"),
        ("Material", "AISI 304 throughout (316/316L + ER316L for salt/marine)"),
    ]
    story += [table(["Item", "Spec"], summary, [0.2, 0.8], 9), Spacer(1, 6 * mm),
              Paragraph("Contents: 1 How to Build - 2 Drawings - 3 3D Views - 4 TIG Parameters - 5 BOM + Sourcing - "
                        "6 Verification Checklist + Design Checks", SMALL), PageBreak()]

    story += [Paragraph("1. How to Build", H1),
              Paragraph("Work top to bottom. Each step lists the exact tools. Settings for every weld are in section 4.", BODY),
              Spacer(1, 4)] + build_steps() + [PageBreak()]

    story += [Paragraph("2. Drawings", H1),
              Paragraph("Full-size DXF files are in the package for laser/print; these are previews. Units: mm.", BODY)]
    for png, cap in drawings:
        story += [KeepTogether([img(png, max_h=100 * mm), Paragraph(cap, CAP)])]
    story += [PageBreak()]

    story += [Paragraph("3. 3D Views", H1),
              KeepTogether([img(v_exp), Paragraph("Exploded: liner with 112 holes in the middle, baffles below, "
                                                  "core fill and can above, caps on the ends. Dashed lines show where "
                                                  "each part goes.", CAP)]),
              KeepTogether([img(v_cut), Paragraph("Cut-away: quarter removed to show the 4 baffles, the core fill "
                                                  "between them and the perforated liner.", CAP)]),
              KeepTogether([img(v_asm), Paragraph("Assembled: caps flush with the can ends; the liner bore is the "
                                                  "inlet/outlet port.", CAP)]),
              PageBreak()]

    bb = (OUT / "build_book.md").read_text()
    tig_notes = [ln[2:] for ln in section(bb, "## 4.") if ln.startswith("- ")]
    story += [Paragraph("4. TIG Parameters", H1),
              Paragraph("Shop machine: 220 V input, 110 A max, AC/DC/pulse, back-purge available.", BODY), Spacer(1, 4),
              table(M.TIG_HEAD, M.tig_rows(), [0.06, 0.2, 0.11, 0.22, 0.16, 0.11, 0.14]), Spacer(1, 6)]
    story += [Paragraph(f"&bull; {md_inline(n)}", ParagraphStyle("li", parent=BODY, leftIndent=10)) for n in tig_notes]
    story += [Spacer(1, 6), Paragraph("Weld map", H2),
              table(["ID", "Joint", "Qty", "Type / extent", "Size"], [w[:5] for w in M.WELDS], [0.07, 0.3, 0.07, 0.38, 0.18]),
              Paragraph("No W4: the liner is bought tube, so there is no shop seam.", SMALL), PageBreak()]

    story += [Paragraph("5. BOM + Sourcing", H1),
              table(["Part", "Name", "Material", "Qty", "Notes", "Source"], M.bom(),
                    [0.09, 0.13, 0.17, 0.05, 0.28, 0.28], 7.5), Spacer(1, 6)]
    story += [Paragraph(f"&bull; {md_inline(ln.strip()[2:])}", ParagraphStyle("li", parent=BODY, leftIndent=10))
              for ln in section(bb, "## 1.") if ln.startswith("- ")]
    story += [PageBreak(), Paragraph("6. Verification Checklist", H1)] + checklist()
    story += [Spacer(1, 8), KeepTogether([Paragraph("Design checks (computed by muffler.py)", H2),
              table(["Check", "Value", "Result"], [(c, v, "PASS" if ok else "FAIL") for c, v, ok in res],
                    [0.38, 0.5, 0.12])])]

    pdf = OUT / "build_book.pdf"
    SimpleDocTemplate(str(pdf), pagesize=letter, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                      bottomMargin=18 * mm, title="50 x 250 Baffle Muffler - Build Book",
                      author="muffler.py").build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"{pdf}  {pdf.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
