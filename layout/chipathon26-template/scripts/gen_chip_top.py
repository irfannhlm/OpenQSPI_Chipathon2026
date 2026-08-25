#!/usr/bin/env python3
"""
Generate chip_top.sv for the SSCS Chipathon 2026 A09 padring integration.

Reads Mitch's delivered interface spec and emits a chip_top that instantiates:
  - the supplied padring netlist  (A09_<VARIANT>_padring)
  - the hardened user macro       (a09_chipathon26_top)
and wires the two together.

The wiring is derived entirely from A09_<VARIANT>_interface.yaml, which maps
each macro port (`project_pin`) to a padring slot + pad-cell terminal
(`padring_instance` + `cell_terminal`).  Padring core-side ports are named
`<padring_instance>_<cell_terminal>`; power/ground slots expose the bare slot
name instead.

Regenerate whenever a new set of DEFs arrives:
    python3 scripts/gen_chip_top.py --variant BV
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

import yaml

TEMPLATE_ROOT = Path(__file__).resolve().parents[1]      # .../chipathon26-template
LAYOUT_ROOT = TEMPLATE_ROOT.parent                        # .../layout
DEFS_ROOT = LAYOUT_ROOT / "project_defs"

MACRO_MODULE = "a09_chipathon26_top"

# Pad-cell terminals that carry the power/ground rail rather than a signal.
POWER_TERMINALS = {"DVDD", "DVSS"}

BUS_RE = re.compile(r"^(?P<base>[A-Za-z_]\w*?)\[(?P<idx>\d+)\]$")


def parse_pin(name: str) -> tuple[str, int | None]:
    """Split `qspi_io_OUT[3]` -> ("qspi_io_OUT", 3); scalars -> (name, None)."""
    m = BUS_RE.match(name)
    if m:
        return m.group("base"), int(m.group("idx"))
    return name, None


def padring_port(entry: dict) -> str:
    """Core-side padring port name for one interface entry."""
    slot = entry["padring_instance"]
    term = entry["cell_terminal"]
    if term in POWER_TERMINALS:
        # dvdd/dvss cells expose the rail as the bare slot port.
        return slot
    return f"{slot}_{term}"


def load(variant: str):
    vdir = DEFS_ROOT / variant
    iface = yaml.safe_load((vdir / f"A09_{variant}_interface.yaml").read_text())
    padmap = yaml.safe_load((vdir / f"A09_{variant}_pad_map.yaml").read_text())
    return iface, padmap


def collect_slots() -> list[str]:
    """Every physical slot on the die, in padring port order (N, E, S, W)."""
    return [f"{side}{i:02d}" for side in ("N", "E", "S", "W") for i in range(1, 23)]


def build(variant: str) -> str:
    iface, padmap = load(variant)
    padring_module = padmap["design_name"]

    # macro port base -> {index or None: padring net}
    macro_conn: dict[str, dict] = defaultdict(dict)
    # padring core-side nets that need a local wire declaration
    core_nets: list[str] = []

    for entry in iface["pins"]:
        proj = entry["project_pin"]
        net = padring_port(entry)
        base, idx = parse_pin(proj)
        macro_conn[base][idx] = net
        if entry["cell_terminal"] not in POWER_TERMINALS:
            core_nets.append(net)

    slots = collect_slots()
    nets = sorted(set(core_nets))

    L: list[str] = []
    add = L.append

    add("// SPDX-License-Identifier: Apache-2.0")
    add("//")
    add(f"// chip_top for SSCS Chipathon 2026 - Team A09 (variant {variant})")
    add("//")
    add("// GENERATED FILE - do not edit by hand.")
    add(f"//   source: project_defs/{variant}/A09_{variant}_interface.yaml")
    add(f"//   script: scripts/{Path(__file__).name}")
    add(f"//   spec:   {iface['spec_blob_sha']}")
    add("//")
    add(f"// Block origin {iface['origin_microns']} um, "
        f"size {iface['size_microns']} um, "
        f"{iface['participant_pin_count']} user pins -> "
        f"{len(iface['pins'])} core-side connections.")
    add("")
    add("`default_nettype none")
    add("")
    add("module chip_top (")
    add("    // Physical bond pads")
    for i, s in enumerate(slots):
        comma = "" if i == len(slots) - 1 else ","
        add(f"    inout wire {s}{comma}")
    add(");")
    add("")

    add("    // ---- padring core-side nets ----")
    for net in nets:
        add(f"    wire {net};")
    add("")

    add(f"    // ---- padring ({padring_module}) ----")
    add(f"    {padring_module} u_padring (")
    conns = [f"        .{s}({s})" for s in slots]
    conns += [f"        .{n}({n})" for n in nets]
    add(",\n".join(conns))
    add("    );")
    add("")

    add(f"    // ---- user macro ({MACRO_MODULE}) ----")
    add(f"    {MACRO_MODULE} u_core (")
    power = sorted(b for b in macro_conn if b in ("VDD", "VSS"))
    signal = sorted(b for b in macro_conn if b not in ("VDD", "VSS"))

    chunks: list[str] = []
    if power:
        chunks.append("    `ifdef USE_POWER_PINS")
        for b in power:
            chunks.append(f"        .{b}({macro_conn[b][None]}),")
        chunks.append("    `endif")

    body: list[str] = []
    for base in signal:
        m = macro_conn[base]
        if list(m) == [None]:
            body.append(f"        .{base}({m[None]})")
        else:
            # bus: concatenate MSB..LSB
            idxs = sorted((i for i in m if i is not None), reverse=True)
            inner = ", ".join(m[i] for i in idxs)
            body.append(f"        .{base}({{{inner}}})")
    chunks.append(",\n".join(body))
    add("\n".join(chunks))
    add("    );")
    add("")
    add("endmodule")
    add("")
    add("`default_nettype wire")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="BV", choices=["BV", "BH"])
    ap.add_argument("--out", default=str(TEMPLATE_ROOT / "src" / "chip_top.sv"))
    args = ap.parse_args()

    text = build(args.variant)
    out = Path(args.out)
    out.write_text(text)
    print(f"wrote {out}  ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
