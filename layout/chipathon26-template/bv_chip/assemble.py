# KLayout script: assemble the full-chip GDS by dropping the hardened A09_BV macro
# into the Chipathon-supplied pad ring, using A09_BV_padring.def for placement.
#
#   run:  klayout -b -r assemble.py
#         (inside the project nix-shell; needs $PDK_ROOT / $PDK or the defaults below)
#
# Output: bv_chip/out/A09_BV_chip.gds   (top cell: A09_BV_chip)
#
# The pad ring's 552 IO cells are instantiated from the PDK GDS libraries at the
# exact coordinates in A09_BV_padring.def; A09_BV.gds is placed at the cavity
# origin (350, 1475) um, orientation N, from A09_BV_interface.yaml. The IO cells'
# own Metal2 pins already run to their inward edge, so everything connects by
# abutment - no stubs, no routing.

import os
import re
import glob
import pya

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.normpath(os.path.join(HERE, ".."))
PROJECT_DEFS = os.path.normpath(os.path.join(TEMPLATE, "..", "project_defs", "BV"))

PDK_ROOT = os.environ.get("PDK_ROOT", os.path.join(TEMPLATE, "gf180mcu"))
PDK = os.environ.get("PDK", "gf180mcuD")
PDK_REF = os.path.join(PDK_ROOT, PDK, "libs.ref")

PADRING_DEF = os.path.join(PROJECT_DEFS, "A09_BV_padring.def")
MACRO_GDS = os.path.join(TEMPLATE, "macros", "A09_BV", "final", "gds", "A09_BV.gds")
IO_LEF_DIR = os.path.join(PDK_REF, "gf180mcu_fd_io", "lef")
IO_GDS = [
    os.path.join(PDK_REF, "gf180mcu_fd_io", "gds", "gf180mcu_fd_io.gds"),
    os.path.join(PDK_REF, "gf180mcu_fd_io", "gds", "gf180mcu_ws_io.gds"),
]

OUT_DIR = os.path.join(HERE, "out")
OUT_GDS = os.path.join(OUT_DIR, "A09_BV_chip.gds")

TOP_NAME = "A09_BV_chip"
DEF_UNITS_PER_UM = 200.0
CORE_X_UM, CORE_Y_UM, CORE_ORIENT = 350.0, 1475.0, "N"

# DEF orientation -> (klayout rotation code, mirror). Pad ring uses only N/S/E/W.
ORIENT = {
    "N": (0, False), "W": (1, False), "S": (2, False), "E": (3, False),
    "FN": (0, True), "FW": (1, True), "FS": (2, True), "FE": (3, True),
}

COMP_RX = re.compile(
    r"-\s+(\S+)\s+(\S+)"                                     # - inst master
    r"[^;]*?"
    r"PLACED\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+([A-Z]{1,2})",  # PLACED ( x y ) ORIENT
    re.S,
)


def lef_frames(lef_dir):
    """master -> (w_um, h_um) from the LEF SIZE (the clean placement frame the
    DEF coordinates were computed against; ORIGIN is 0 0 for every IO cell)."""
    out = {}
    for path in glob.glob(os.path.join(lef_dir, "*.lef")):
        name = None
        for line in open(path):
            m = re.match(r"\s*MACRO\s+(\S+)", line)
            if m:
                name = m.group(1)
            m = re.match(r"\s*SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", line)
            if m and name:
                out[name] = (float(m.group(1)), float(m.group(2)))
    return out


def parse_components(def_path):
    text = open(def_path).read()
    m = re.search(r"UNITS\s+DISTANCE\s+MICRONS\s+(\d+)", text)
    units = float(m.group(1)) if m else DEF_UNITS_PER_UM
    block = re.search(r"^COMPONENTS\b.*?^END COMPONENTS", text, re.S | re.M)
    if not block:
        raise RuntimeError("no COMPONENTS section in " + def_path)
    out = []
    for inst, master, x, y, orient in COMP_RX.findall(block.group(0)):
        out.append((inst, master, int(x) / units, int(y) / units, orient))
    return out


# GF180MCU GDS layer/datatype for Metal5 (from libs.tech/klayout/tech/gf180mcu.lyp)
METAL5_LAYER = (81, 0)

_PIN_HDR_RX = re.compile(r"^-\s+(\S+)\s+\+\s+NET\s+(\S+)", re.M)
_PIN_M5_RX = re.compile(
    r"\+\s+LAYER\s+Metal5\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)")


def parse_ball_pins(def_path):
    """The 88 perimeter balls: NET name + its Metal5 landing rect (DEF dbu).
    Core-side stub pins (Metal2 only, e.g. W14_PU) are internal and skipped."""
    text = open(def_path).read()
    m = re.search(r"UNITS\s+DISTANCE\s+MICRONS\s+(\d+)", text)
    units = float(m.group(1)) if m else DEF_UNITS_PER_UM
    block = re.search(r"^PINS\b.*?^END PINS", text, re.S | re.M)
    body = block.group(0)
    starts = list(_PIN_HDR_RX.finditer(body))
    out = []
    for k, mh in enumerate(starts):
        seg = body[mh.end(): starts[k + 1].start() if k + 1 < len(starts) else len(body)]
        m5 = _PIN_M5_RX.search(seg)
        if m5:
            x1, y1, x2, y2 = (int(v) / units for v in m5.groups())
            out.append((mh.group(2), (x1 + x2) * 0.5, (y1 + y2) * 0.5))
    return out


def main():
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    layout = pya.Layout()
    layout.read(MACRO_GDS)
    for g in IO_GDS:
        layout.read(g)

    dbu = layout.dbu  # um per dbu
    top = layout.create_cell(TOP_NAME)
    frames = lef_frames(IO_LEF_DIR)

    def place(master, x_um, y_um, orient, anchor="frame"):
        cell = layout.cell(master)
        if cell is None:
            raise RuntimeError("cell not found in GDS libs: " + master)
        rot, mir = ORIENT[orient]
        xd, yd = int(round(x_um / dbu)), int(round(y_um / dbu))
        if anchor == "frame":
            # DEF PLACED point = post-orientation lower-left of the LEF SIZE frame
            # (NOT the GDS geometry bbox - that carries fill/dummy overhang that
            #  would shift the cell by a fraction of a micron).
            if master not in frames:
                raise RuntimeError("no LEF SIZE for " + master)
            w, h = frames[master]
            fr = pya.Box(0, 0, int(round(w / dbu)), int(round(h / dbu)))
            rb = fr.transformed(pya.Trans(rot, mir, 0, 0))
            tr = pya.Trans(rot, mir, xd - rb.left, yd - rb.bottom)
        else:  # "origin": point is the cell origin (0,0) - used for A09_BV
            tr = pya.Trans(rot, mir, xd, yd)
        top.insert(pya.CellInstArray(cell.cell_index(), tr))

    comps = parse_components(PADRING_DEF)
    for inst, master, x, y, orient in comps:
        place(master, x, y, orient, anchor="frame")

    place("A09_BV", CORE_X_UM, CORE_Y_UM, CORE_ORIENT, anchor="origin")

    # Text-only labels (no geometry) on the 88 perimeter balls, so Magic extracts
    # A09_BV_chip with a real port list for LVS. Placed on Metal5 (where the ball
    # bond metal already is) at each ball's centre from A09_BV_padring.def.
    m5 = layout.layer(*METAL5_LAYER)
    balls = parse_ball_pins(PADRING_DEF)
    for net, cx_um, cy_um in balls:
        top.shapes(m5).insert(
            pya.Text(net, pya.Trans(int(round(cx_um / dbu)), int(round(cy_um / dbu)))))

    layout.write(OUT_GDS)
    print("placed %d pad-ring cells + A09_BV, labelled %d perimeter balls"
          % (len(comps), len(balls)))
    print("wrote " + OUT_GDS + "  (dbu=%g, top=%s)" % (dbu, TOP_NAME))


main()
