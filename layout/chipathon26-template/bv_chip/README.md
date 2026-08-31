# bv_chip — assemble A09_BV into the supplied pad ring, DRC + LVS (no LibreLane)

The Chipathon deliverables `layout/project_defs/BV/A09_BV_padring.{v,def}` are outputs of
the organizers' `padring` generator: meant to be read straight into a layout tool and
merged with a block GDS, not run through synthesis. This directory does the integration the
direct way — KLayout for the GDS assembly + DRC, Magic + Netgen for LVS. **No blackboxes**:
LVS is device-level on both sides, like the A09_BV macro's own LibreLane step
(`macros/A09_BV/runs/*/74-netgen-lvs/`).

```
A09_BV_padring.def  ─┐  (552 IO cells, exact coords)
A09_BV.gds           ─┼─► assemble.py (KLayout) ─► out/A09_BV_chip.gds
                     ─┘                                    │
                              run_drc.py (KLayout) ◄───────┤  -> out/drc/     (CLEAN)
                              extract.tcl (Magic)   ◄───────┘  -> out/A09_BV_chip.ext.spice
                                                             │
A09_BV_padring.v ─► prep.py ─► A09_BV_padring.prep.v ───┤
A09_BV.pnl.v + A09_BV_chip.v + PDK device SPICE  ─────────────┤
                              lvs.tcl (Netgen)     ◄───────────┘  -> out/lvs/  (MATCH)
```

## Run

```bash
cd layout/chipathon26-template
nix-shell                 # klayout, magic, netgen
make clone-pdk            # if gf180mcu/ is missing
bv_chip/run.sh            # prep -> assemble -> drc -> extract -> lvs -> summary
```

Single stages: `bv_chip/run.sh {prep|assemble|drc|extract|lvs|summary}`.
View: `bv_chip/run.sh openklayout` (merged GDS) ·
Env: `PDK_ROOT`, `PDK` (`gf180mcuD`), `VARIANT` (`D`).

Every run ends with a summary:

```
==================  bv_chip : A09_BV_chip  ==================
  DRC   : CLEAN  (0 violations)
  LVS   : MATCH  (Circuits match uniquely.)
  GDS   : bv_chip/out/A09_BV_chip.gds
===========================================================
```

## Files

- **`assemble.py`** (KLayout) — places the 552 IO cells from the PDK GDS libs at their
  `A09_BV_padring.def` coordinates (anchored to the LEF `SIZE` frame, not the GDS bbox),
  then `A09_BV.gds` at (350, 1475) µm orient N. Adds a text label per perimeter ball so
  Magic extracts a port list. IO cells' own Metal2 pins abut the macro's — no routing.
- **`A09_BV_chip.v`** — integration netlist (plain Verilog-2001): `A09_BV_padring` +
  `A09_BV` wired per `A09_BV_pad_map.yaml`. Also the cocotb DUT (`cocotb/bv_chip_tb.sv`).
- **`prep.py`** — regenerates `A09_BV_padring.v` → **`A09_BV_padring.prep.v`**: every
  instance name prefixed `I_` (Yosys/Icarus reject instance == port name) + the `brk5`
  power-domain breaks modeled (Arc-B dummy rails split onto isolated floating nets).
  Details in `LVS_NOTES.md`. Organizers' original untouched.
- **`extract.tcl`** (Magic) — `gds read` + `port makeall` + `extract all` + `ext2spice lvs`.
- **`lvs.tcl`** (Netgen) — extracted layout vs `A09_BV_chip.v` + `A09_BV_padring.prep.v`
  + `A09_BV.pnl.v` + PDK std-cell/IO device SPICE. `-blackbox` placeholders only the PDK
  leaf FETs.

## Results

- **DRC** — clean, 0 violations.
- **LVS** — `Circuits match uniquely` (with `prep.py`'s break modeling). `A09_BV`, all 552
  IO cells, all 88 signal balls, the real supply pads and the top-level port list match.

## Gate-level simulation

`cocotb/bv_chip_tb.py` drives `A09_BV_chip.v` + `A09_BV_padring.prep.v` +
`A09_BV.pnl.v` (`make sim-gl MACRO=A09_BV`). Pad delays come from the `specify` blocks in
`gf180mcu_fd_io.v`; the `A09_BV` core annotates from `macros/A09_BV/final/sdf/`. No
top-level SDF is needed — the chip has no routing (all pad↔macro nets abut, zero
interconnect delay). Run `bv_chip/run.sh prep` first if `A09_BV_padring.v` changed.
