#!/usr/bin/env python3
"""Compare the pin placement of a hardened DEF against the supplied template DEF.

The block/padring interface is an abutment contract: Mitch's padring metal stops
at the block boundary and expects the block's metal to meet it exactly. There is
no top-level routing step to bridge a gap, so a pin that lands even slightly off
is a broken connection, not a routing inconvenience.

Two DEF styles must both be handled, and they differ in where the origin lives:

  Template (A09_BV.def) -- several LAYER rects in absolute coordinates sharing
  a single trailing origin:
      - VSS + NET VSS + DIRECTION INOUT + USE GROUND
        + LAYER Metal2 ( 0 13828 ) ( 200 15728 )
        + LAYER Metal2 ( 0 11198 ) ( 200 13248 )
        + FIXED ( 0 0 ) N ;

  LibreLane output -- one PORT per shape, each with its own port-relative LAYER
  rect and its own origin:
      - VSS + NET VSS + SPECIAL + DIRECTION INOUT + USE GROUND
        + PORT
          + LAYER Metal2 ( -500 -5125 ) ( 500 5125 )
          + PLACED ( 500 11110 ) N
        + PORT
          ...

Applying the first origin to every LAYER (the obvious parse) silently collapses
the second style into N copies of one rectangle, which looks like a mismatch
that is not real. Ports are therefore parsed individually.

Usage:
    python3 check_pin_abutment.py <template.def> <hardened.def>

Exits non-zero if any pin is missing, extra, or displaced.
"""
import re
import sys
from collections import namedtuple

Pin = namedtuple("Pin", "name layer shapes use")  # shapes: sorted [(x0,y0,x1,y1)]

PIN_START = re.compile(r"^\s*-\s+(\S+)\s")
LAYER = re.compile(
    r"\+\s+LAYER\s+(\S+)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)"
)
ORIGIN = re.compile(r"\+\s+(?:FIXED|PLACED|COVER)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)")
USE = re.compile(r"\+\s+USE\s+(\S+)")
UNITS = re.compile(r"^UNITS\s+DISTANCE\s+MICRONS\s+(\d+)", re.M)


def _shapes_from_chunk(chunk):
    """Absolute rects from one PORT chunk (or a whole origin-sharing pin)."""
    origin = ORIGIN.search(chunk)
    ox, oy = (int(origin.group(1)), int(origin.group(2))) if origin else (0, 0)
    out = []
    for lname, a, b, c, d in LAYER.findall(chunk):
        x0, y0, x1, y1 = int(a), int(b), int(c), int(d)
        out.append(
            (
                lname,
                ox + min(x0, x1),
                oy + min(y0, y1),
                ox + max(x0, x1),
                oy + max(y0, y1),
            )
        )
    return out


def parse(path):
    """Return (units_per_micron, {name: Pin}) with coordinates made absolute."""
    text = open(path, encoding="utf-8", errors="replace").read()
    units_match = UNITS.search(text)
    units = int(units_match.group(1)) if units_match else 1000

    start = text.find("\nPINS ")
    if start < 0:
        sys.exit(f"{path}: no PINS section")
    end = text.find("END PINS", start)
    body = text[start:end]

    pins, current, buf = {}, None, []

    def flush():
        if current is None:
            return
        blob = "\n".join(buf)
        # Each "+ PORT" carries its own origin; without them the pin shares one.
        chunks = re.split(r"\+\s+PORT\b", blob)
        chunks = chunks[1:] if len(chunks) > 1 else [blob]
        collected = []
        for chunk in chunks:
            collected.extend(_shapes_from_chunk(chunk))
        if not collected:
            return  # pin with no physical shape; nothing to abut
        use = USE.search(blob)
        pins[current] = Pin(
            current,
            collected[0][0],
            sorted(r[1:] for r in collected),
            use.group(1) if use else "SIGNAL",
        )

    for line in body.splitlines()[1:]:
        m = PIN_START.match(line)
        if m and "+ NET" in line:
            flush()
            current, buf = m.group(1), [line]
        elif current:
            buf.append(line)
    flush()
    return units, pins


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    tmpl_units, template = parse(sys.argv[1])
    run_units, hardened = parse(sys.argv[2])

    print(f"template: {len(template):3d} pins @ {tmpl_units} units/um  {sys.argv[1]}")
    print(f"hardened: {len(hardened):3d} pins @ {run_units} units/um  {sys.argv[2]}")

    missing = sorted(set(template) - set(hardened))
    extra = sorted(set(hardened) - set(template))
    displaced, layer_diff = [], []

    for name in sorted(set(template) & set(hardened)):
        t, h = template[name], hardened[name]
        # Normalise to microns so a units mismatch does not raise false alarms.
        tc = sorted(tuple(round(v / tmpl_units, 3) for v in r) for r in t.shapes)
        hc = sorted(tuple(round(v / run_units, 3) for v in r) for r in h.shapes)
        if len(tc) != len(hc) or any(
            abs(a - b) > 0.001 for ra, rb in zip(tc, hc) for a, b in zip(ra, rb)
        ):
            displaced.append((name, tc, hc))
        if t.layer != h.layer:
            layer_diff.append((name, t.layer, h.layer))

    if missing:
        print(f"\nMISSING from hardened DEF ({len(missing)}):")
        for n in missing:
            print(f"  {n}  (template has it at {template[n].layer})")
    if extra:
        print(f"\nEXTRA in hardened DEF ({len(extra)}):")
        for n in extra:
            print(f"  {n}")
    if layer_diff:
        print(f"\nLAYER MISMATCH ({len(layer_diff)}):")
        for n, tl, hl in layer_diff:
            print(f"  {n}: template {tl}, hardened {hl}")
    if displaced:
        print(f"\nDISPLACED ({len(displaced)}) -- microns:")
        for n, tc, hc in displaced:
            print(f"  {n}: {len(tc)} template shape(s) vs {len(hc)} hardened")
            for r in tc:
                if r not in hc:
                    print(f"    only in template : ({r[0]:.3f},{r[1]:.3f})-({r[2]:.3f},{r[3]:.3f})")
            for r in hc:
                if r not in tc:
                    print(f"    only in hardened : ({r[0]:.3f},{r[1]:.3f})-({r[2]:.3f},{r[3]:.3f})")

    # A pin can be both displaced and on the wrong layer; count it once.
    faulty = {n for n, *_ in displaced} | {n for n, *_ in layer_diff}
    matched = len(set(template) & set(hardened)) - len(faulty)
    print(f"\n{matched} pin(s) abut exactly, {len(faulty)} faulty.")
    bad = bool(missing or extra or displaced or layer_diff)
    print("RESULT: " + ("MISMATCH" if bad else "OK - placement matches the template"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
