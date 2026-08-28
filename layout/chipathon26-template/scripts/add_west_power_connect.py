#!/usr/bin/env python3
"""Connect the west-edge power pins of A09_BV to the macro's PDN core ring.

Run as a librelane odbpy script:
  openroad -exit -no_splash -python <this> \
      --input-lef <tlef> --input-lef <lef> \
      --template-def <template.def> --output-odb <out.odb> <in.odb>
PYTHONPATH must include librelane/scripts/odbpy so "reader" resolves.

CRITICAL: run this with LibreLane's own OpenROAD build, not the one on PATH.
The IIC-OSIC-TOOLS image ships two:

    /foss/tools/openroad-librelane/bin/openroad   26Q1-1024  <- LibreLane uses this
    /foss/tools/openroad/bin/openroad             26Q2-254   <- what /foss/tools/bin resolves to

The newer build writes odb schema revision 0.129; LibreLane's reader.py calls
design.readDb(), which caps at 0.126. Patch the odb with the newer binary and
the next step dies with "incompatible database schema revision 0.129 > 0.126",
while every standalone read you do to debug it succeeds -- because those also
use the newer build. Use the openroad-librelane path explicitly.

Why this exists
---------------
A09_BV.def places VDD/VSS pins as Metal2 stubs at the extreme west edge
(x 0..1um). The macro's PDN core ring sits further in: two concentric Metal2
bars, the outer one at x~10.06um and the inner at x~13.36um, both spanning the
full block height. Copying the template's power pins without adding metal
leaves them electrically floating, and OpenROAD fails with
"[PSM-0069] Check connectivity failed on VDD".

The two nets are not symmetric:

  * The net owning the OUTER ring reaches its stubs with a plain Metal2 bar --
    nothing is in the way.
  * The net owning the INNER ring cannot: a Metal2 bar from the die edge would
    cross the outer ring and short the two supplies. It needs to hop the outer
    ring on Metal3 and drop back to Metal2 on the far side.

This script emits exactly that, as special wires on the existing power nets.
Run it on a FRESH post-PDN odb; it does not de-duplicate its own output.
"""
import re
import sys

import odb
from reader import click_odb, click

# Wire type for the swire container; shape type tags the individual boxes.
WIRE_TYPE = "ROUTED"
SHAPE_TYPE = "STRIPE"
JUMPER_LAYER = "Metal3"
PIN_LAYER = "Metal2"
# Metal2<->Metal3 via the PDN core ring already uses, so it is known good here.
JUMPER_VIA = "via2_3_3200_3200_3_3_1040_1040"
# Clearance kept between a Metal2 stub and the ring bar it must not touch.
CLEARANCE_UM = 0.8


def parse_template_pins(def_path, want=("VDD", "VSS")):
    """Return {net: [(x0,y0,x1,y1), ...]} in microns from a template DEF."""
    text = open(def_path, encoding="utf-8", errors="replace").read()
    units = int(re.search(r"^UNITS\s+DISTANCE\s+MICRONS\s+(\d+)", text, re.M).group(1))
    start, end = text.find("\nPINS "), text.find("END PINS")
    out = {}
    current = None
    for line in text[start:end].splitlines():
        head = re.match(r"\s*-\s+(\S+)\s+\+\s+NET", line)
        if head:
            current = head.group(1) if head.group(1) in want else None
            continue
        if current is None:
            continue
        m = re.search(
            r"\+\s+LAYER\s+(\S+)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)",
            line,
        )
        if m:
            x0, y0, x1, y1 = (int(m.group(i)) / units for i in range(2, 6))
            out.setdefault(current, []).append(
                (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            )
    return out


def west_ring_x(net, layer_name):
    """Centre x (dbu) of the westmost vertical RING bar on this net."""
    best = None
    for swire in net.getSWires():
        for box in swire.getWires():
            if box.isVia():
                continue
            if box.getTechLayer().getName() != layer_name:
                continue
            if box.getWireShapeType() != "RING":
                continue
            w, h = box.getDX(), box.getDY()
            if h <= w:  # want vertical bars only
                continue
            cx = (box.xMin() + box.xMax()) // 2
            if best is None or cx < best[0]:
                best = (cx, w)
    return best

@click.command()
@click.option("--template-def", required=True, help="Template DEF with the power pins")
@click.option("--power-net", default="VDD", help="Power net name")
@click.option("--ground-net", default="VSS", help="Ground net name")
@click_odb
def cli(reader, template_def, power_net, ground_net):
    block = reader.block
    tech = reader.db.getTech()
    dbu = tech.getDbUnitsPerMicron()

    m_pin = tech.findLayer(PIN_LAYER)
    m_jump = tech.findLayer(JUMPER_LAYER)
    if m_pin is None or m_jump is None:
        sys.exit(f"missing layer {PIN_LAYER}/{JUMPER_LAYER}")

    pins = parse_template_pins(template_def, (power_net, ground_net))
    if not pins:
        sys.exit("no VDD/VSS pins found in template DEF")

    rings = {}
    for name in (power_net, ground_net):
        net = block.findNet(name)
        if net is None:
            sys.exit(f"net {name} not in design")
        r = west_ring_x(net, PIN_LAYER)
        if r is None:
            sys.exit(f"no west {PIN_LAYER} ring bar found on {name}")
        rings[name] = r
        print(f"{name}: west ring centre x = {r[0]/dbu:.3f}um width {r[1]/dbu:.3f}um")

    # Outer = smaller x. That net connects straight out; the other must hop it.
    order = sorted(rings, key=lambda n: rings[n][0])
    outer_net_name, inner_net_name = order[0], order[1]
    print(f"outer (direct): {outer_net_name}   inner (needs jumper): {inner_net_name}")

    outer_cx, outer_w = rings[outer_net_name]
    clearance = int(CLEARANCE_UM * dbu)

    via = block.findVia(JUMPER_VIA)
    if via is None:
        sys.exit(f"via master {JUMPER_VIA} not in block")
    via_w = max(b.getDX() for b in via.getBoxes()) // 2 or int(0.8 * dbu)

    total = 0
    for name in (outer_net_name, inner_net_name):
        net = block.findNet(name)
        # odb exposes no dbWireType constructor; the SWIG typemap takes the
        # string. Note "STRIPE" is a *shape* type and is rejected here.
        swire = odb.dbSWire.create(net, WIRE_TYPE)
        cx, w = rings[name]
        ring_east = cx + w // 2

        for (x0, y0, x1, y1) in pins.get(name, []):
            ylo, yhi = int(y0 * dbu), int(y1 * dbu)
            if name == outer_net_name:
                # Straight Metal2 bar from the die edge into the ring.
                odb.dbSBox.create(swire, m_pin, 0, ylo, ring_east, yhi, SHAPE_TYPE)
                total += 1
            else:
                # Stop the Metal2 short of the outer ring, hop it on Metal3.
                # Overlapping shapes on different layers are NOT connected --
                # each end of the jumper needs a real via cut.
                stub_end = outer_cx - outer_w // 2 - clearance
                ycen = (ylo + yhi) // 2
                odb.dbSBox.create(swire, m_pin, 0, ylo, stub_end, yhi, SHAPE_TYPE)
                odb.dbSBox.create(
                    swire, m_jump, stub_end - 2 * via_w, ylo, ring_east, yhi, SHAPE_TYPE
                )
                odb.dbSBox.create(swire, via, stub_end - via_w, ycen, SHAPE_TYPE)
                odb.dbSBox.create(swire, via, cx, ycen, SHAPE_TYPE)
                total += 4
        print(f"{name}: wrote shapes for {len(pins.get(name, []))} template stub(s)")

    print(f"total shapes added: {total}")


if __name__ == "__main__":
    cli()
