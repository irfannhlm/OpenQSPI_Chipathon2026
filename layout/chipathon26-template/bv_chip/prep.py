# Regenerate the pad-ring netlist for LVS (netgen) and gate-level simulation.
#
#   in :  layout/project_defs/BV/A09_BV_padring.v   (organizers' file, untouched)
#   out:  bv_chip/A09_BV_padring.prep.v
#
# Two transforms:
#
# 1. Unique instance names.  The supplied netlist names each pad instance the same
#    as its port (instance N01 vs port N01); Yosys and Icarus both reject that.
#    Every instance name is prefixed 'I_'.  Ports / nets are untouched.
#
# 2. Power-domain breaks.  The supplied netlist is LOGICAL - it ties every dummy
#    cell to .VSS/.DVSS(W12) and .VDD/.DVDD(FLOAT_VDD_1) regardless of the
#    gf180mcu_fd_io__brk5 cells that physically CUT the pad supply rails.  Per the
#    Chipathon spec the pad supply is broken for each project IO group.  The two
#    brk5 groups in A09_BV_padring.def (BRK_W11_* west edge, BRK_N02_* north edge)
#    split the ring:
#      Arc A = W12..W22 -> CORNER_4 (NW) -> N01, N02   (BV domain; already on
#              W13 / W12, left as-is)
#      Arc B = W01..W11, N03..N22, E01..E22, S01..S22, CORNER_1/2/3 + their fillers
#              (all dummy) -> re-railed onto isolated floating nets:
#                .DVSS(W12)          -> .DVSS(FLOAT_DVSS_2)   (.VSS stays continuous)
#                .VDD(FLOAT_VDD_1)   -> .VDD(FLOAT_VDD_2)
#                .DVDD(FLOAT_VDD_1)  -> .DVDD(FLOAT_DVDD_2)
#
#   run:  python3 prep.py

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "project_defs", "BV", "A09_BV_padring.v"))
OUT = os.path.join(HERE, "A09_BV_padring.prep.v")

INST_RX = re.compile(r"^(\s*)(gf180mcu_\S+)(\s+)(\S+)(\s*\()")

# FILL_<slot>_<n> slots that belong to Arc A (the BV domain span between the breaks)
ARC_A_FILL_SLOTS = {"N00", "N01"} | {"W%d" % n for n in range(12, 23)}


def arc_of(master, inst):
    if master == "gf180mcu_fd_io__brk5":
        return "A"                                   # only .VSS - never rewritten
    if master == "gf180mcu_fd_io__cor":
        return "A" if inst == "CORNER_4" else "B"    # CORNER_4 = NW, inside Arc A
    if master == "gf180mcu_fd_io__asig_5p0":
        return "B"                                   # every analog pad is Arc B
    if master.startswith("gf180mcu_fd_io__fill"):
        m = re.match(r"FILL_([A-Z]\d+)_\d+$", inst)
        return "A" if (m and m.group(1) in ARC_A_FILL_SLOTS) else "B"
    return "A"                                       # functional pads: bi_t/in_s/in_c/dvdd/dvss


def main():
    lines = open(SRC).read().splitlines()
    out = []
    n_pref = n_rail = 0
    for ln in lines:
        m = INST_RX.match(ln)
        if m:
            master, inst = m.group(2), m.group(4)
            if arc_of(master, inst) == "B":
                new = (ln.replace(".DVSS(W12)", ".DVSS(FLOAT_DVSS_2)")
                         .replace(".DVDD(FLOAT_VDD_1)", ".DVDD(FLOAT_DVDD_2)")
                         .replace(".VDD(FLOAT_VDD_1)", ".VDD(FLOAT_VDD_2)"))
                if new != ln:
                    n_rail += 1
                ln = new
            # prefix the instance name (keep the connection list intact)
            ln = INST_RX.sub(lambda mm: "%s%sI_%s%s" % (
                mm.group(1) + mm.group(2) + mm.group(3), "", mm.group(4), mm.group(5)),
                ln, count=1)
            n_pref += 1
        out.append(ln)
        if ln.strip() == "wire FLOAT_VDD_1;":
            out.append("  wire FLOAT_VDD_2, FLOAT_DVDD_2, FLOAT_DVSS_2; "
                       "// Arc-B (non-BV) dummy rails, isolated by brk5")

    open(OUT, "w").write(
        "// GENERATED from A09_BV_padring.v by bv_chip/prep.py - do not edit.\n"
        "//  * every instance name prefixed 'I_' (Yosys/Icarus: instance != port name)\n"
        "//  * Arc-B dummy pad rails split onto isolated floating nets (brk5 power breaks)\n"
        + "\n".join(out) + "\n"
    )
    print("wrote %s" % OUT)
    print("  %d instances prefixed 'I_', %d Arc-B instances re-railed" % (n_pref, n_rail))


main()
