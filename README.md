# Baffle Muffler 50 x 250

Inline baffle-style exhaust muffler for small 4-stroke engines: 304 stainless, home TIG build (110 A max).

- 50 x 2 mm can, 32 x 2 mm liner, 112 x Ø9 holes (8/row, 14 rows, 22.5° stagger), 4 baffles + 2 caps (3 mm)
- **Build book (everything in one file):** [`out/handoff/build_book.pdf`](out/handoff/build_book.pdf)
- DXF drawings, drill jig, BOM, checklist: [`out/handoff/`](out/handoff/)

## Regenerate

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python build_pdf.py --can-id 46.0 --liner-od 32.0   # use measured tube sizes
```

`muffler.py` makes the drawings and docs and runs the design checks; `build_pdf.py` runs it, then builds the PDF.
`muffler_v1.py` is the original 1.5 mm-wall version, kept for reference.
