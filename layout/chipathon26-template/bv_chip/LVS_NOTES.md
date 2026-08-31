# LVS notes — `A09_BV_chip`

## Pad-ring power-domain breaks (resolved by `prep.py`)

### The problem

The organizers' `layout/project_defs/BV/A09_BV_padring.v` is a *logical* netlist: it ties
every dummy cell (fillers, unused analog pads, corners) to `.VSS/.DVSS(W12)` and
`.VDD/.DVDD(FLOAT_VDD_1)` regardless of the `gf180mcu_fd_io__brk5` cells that physically
**cut the pad supply rails**. Per the Chipathon spec the pad supply must be broken for each
project IO group, and `A09_BV_padring.def` places the breaks accordingly — so the
as-supplied `.v` and `.def` disagree on dummy-rail topology.

Running LVS against the raw `.v` gave one clean net-count mismatch:

```
Circuit 1 (layout):  180 nets     Circuit 2 (raw .v):  178 nets
```

The layout has extra floating nets because the dummy cells beyond the breaks sit on
isolated rail segments; the raw `.v` merges them.

### The fix

`prep.py` reads the two `brk5` group positions from `A09_BV_padring.def`
(`BRK_W11_*` on the west edge, `BRK_N02_*` on the north edge) and splits the ring:

- **Arc A** — `W12..W22 → CORNER_4 (NW) → N01, N02`: the BV power domain. Already wired to
  `W13` / `W12` in the supplied `.v`; left untouched.
- **Arc B** — `W01..W11`, `N03..N22`, `E01..E22`, `S01..S22`, `CORNER_1/2/3` and their
  fillers: all dummy. 463 instances, re-railed:

  | pin | raw `.v` | `A09_BV_padring.prep.v` |
  |---|---|---|
  | `.VSS`  | `W12` | `W12` (core ground stays continuous) |
  | `.DVSS` | `W12` | `FLOAT_DVSS_2` |
  | `.VDD`  | `FLOAT_VDD_1` | `FLOAT_VDD_2` |
  | `.DVDD` | `FLOAT_VDD_1` | `FLOAT_DVDD_2` |

The 463 count and the split (`fill5` 385, `asig_5p0` 75, `cor` 3) match the layout's
Arc-B fanout exactly. `run.sh` regenerates `A09_BV_padring.prep.v` and points
`PADRING_V` at it before LVS; the organizers' original file is not modified.

`prep.py` also prefixes every pad-ring instance name with `I_` in the same pass — the
supplied netlist names each instance the same as its port (instance `N01` vs port `N01`),
which Yosys and Icarus both reject. Ports and nets are untouched.

### What LVS verifies

- `A09_BV` macro — matches uniquely (6027 devices, 6023 nets)
- all 552 pad-ring IO cells, all 88 perimeter signal balls, the real supply pads
  (`dvdd`/`dvss`) and the `W13`/`W12` functional rails — matched
- top-level `A09_BV_chip` port list — equivalent
- **Final result: `Circuits match uniquely.`**
