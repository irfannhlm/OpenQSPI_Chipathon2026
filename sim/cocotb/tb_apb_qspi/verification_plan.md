# apb_qspi Verification Plan

Snapshot of the pyuvm/cocotb environment at `sim/cocotb/tb_apb_qspi/`, verifying
`rtl/apb_qspi.sv` (APB wrapper + `qspi_master` + shared FIFO) against the
Infineon S25FL128S flash model. See `README.md` in this directory for how to
run it and the full DUT issue tracker.

> **Note on coverage:** this is a pyuvm/cocotb environment, not native
> SystemVerilog UVM, so there are no `covergroup`/`coverpoint` language
> constructs. Real functional coverage is instead collected with
> `cocotb-coverage` (`pyuvm_tb/qspi_coverage.py`): the `QspiCoverage`
> subscriber samples every transaction the QSPI monitor decodes off the wire.
> Section 2 documents the axes each sequence deliberately sweeps; section 3
> reports the actual bin-hit results from the last regression run.

## 1. Test sequences

| `@pyuvm.test` class | Sequence class | Purpose | Status (qspi_master v0.6.0, fifo v0.1.2) |
|---|---|---|---|
| `ApbComplianceTest` | `CsrComplianceSeq` | APB protocol rules + CSR-level behavior: reset values, full-word readback, RO regs, W1C semantics, FIFO error codes, pready stall-while-busy | **PASS** |
| `SpiComplianceTest` | `SpiModesSeq` | Every lane combo (1-1-1, fast, 1-1-2, 1-2-2, 1-1-4, 1-4-4) swept through SCK mode / endian / addr-len / non-aligned-length variants, plus prescaler, address-integrity, FIFO-full pause, and abort tests | **PASS** |
| `AllCommandsTest` | `AllCommandsSeq` | Every flash command the competition spec requires, end to end | **PASS** |
| `FlashModelTest` | `FlashDataSeq` | Randomized program/read data integrity vs. golden flash model, x1 and x4 | **PASS** |

Full regression 2026-07-11: **4/4 PASS, zero errors, zero waivers triggered.**
All previously tracked DUT issues are fixed and verified (see `README.md` tracker).

### 1.1 Per-test key coverage and pass criteria

Each test is a soft-check sequence (collect every failure, assert at the end)
running alongside the always-on checkers. A test is a **PASS** only when *all*
of these hold: every `self.check`/assert in the sequence passes, every transfer
asserts `DONE` with `FIFO_ERR == 0`, and the three `check_phase` gates report
clean — `ApbMonitor` = 0 APB violations, `QspiMonitor` = 0 SPI violations,
`QspiScoreboard` = 0 mismatches over `compared > 0` transactions, with 0
known-issue waivers triggered.

| Test | Key functionality exercised | Test-specific pass criteria |
|---|---|---|
| `ApbComplianceTest` | CSR reset values; 32-bit write/readback (30 random); `BCNT` read-only; FIFO error codes `RX_EMPTY` / `WRONG_DIR` / `TX_FULL`; `pready` stall while BUSY | All registers read back what was written; `BCNT` write does not stick; each induced FIFO error returns the exact expected code; a config write during BUSY records `wait_states > 0` |
| `SpiComplianceTest` | 6 lane combos (1-1-1, 1-1-2, 1-2-2, 1-1-4, 1-4-4, +fast) × {SPI mode 3, little-endian, 3B/4B addr, dlen=7}; prescaler; address integrity @0x000102; FIFO-full SCK pause (264 B); mid-flight abort | Every variant read equals the same-location base read (content); `QspiScoreboard` confirms wire shape / address / exact SCK-edge count per variant; pause test drains with `FIFO_ERR == 0` and exact edge count; abort still asserts `DONE` |
| `AllCommandsTest` | WREN/WRDI (WEL), RDID/REMS/RES IDs, RDSR1/RDSR2/RDCR, WRR (sets QE), SE + erased read, PP + READ, QPP + QOR, CLSR, software RESET | WEL follows WREN/WRDI; ID reads match the datasheet fixed values; erased read-back = all `0xFF`; PP/QPP read-back equals the programmed pattern; `RDID` still correct after RESET |
| `FlashModelTest` | Randomized program/read integrity: 2× x1 (PP/READ) + 2× x4 (QPP/QOR), 32 random bytes each, on a freshly erased sector | Every read-back equals the exact random pattern written, and the `FlashGolden` model agrees byte-for-byte in the scoreboard |

## 2. READ-operation coverage model (`SpiModesSeq`)

Swept once per lane combo in `run_read_variants()` (`sequences.py:272`), for
every READ-family opcode: `READ` (1-1-1), `FAST_READ` (1-1-1), `DOR` (1-1-2),
`DIOR` (1-2-2), `QOR` (1-1-4, QE-gated), `QIOR` (1-4-4, QE-gated).

| Axis | Values swept | Implemented in |
|---|---|---|
| SCK mode (`qspi_sck_mode_i`) | mode 0 (base), mode 3 (CPOL=1/CPHA=1) | `run_read_variants` — `sck_mode=1` case |
| Endianness (`qspi_endian_i`) | big-endian (base), little-endian DR packing | `run_read_variants` — `endian=1` case |
| Address length (`qspi_addr_len_i`) | 3-byte (base opcode), 4-byte (dedicated 4B opcode: 0x13/0x0C/0x3C/0xBC/0x6C/0xEC) | `run_read_variants` — `addr4=1` case, gated on `opcode4 is not None` |
| Non-word-aligned length | dlen=8 (base), dlen=7 (partial final DR word) | `run_read_variants` — `dlen=7` case |
| Prescaler | prescaler=0 (base), prescaler=3 | `SpiModesSeq.body`, base-mode only |
| Address integrity | nonzero mid/low address bytes (`0x000102`) so a dropped/zeroed byte can't hide | `SpiModesSeq.body`, base-mode only |
| SCK pausing (FIFO full) | 264B (66-word) read against a 64-word FIFO, forcing a pause/resume at the FIFO-full boundary, exact edge count checked | `pause_test()` |
| Software abort | `CTRL_ABORT` mid-flight on a slow (prescaler=4) read; DONE must still assert, partial wire transaction accepted | `abort_test()` |

Each variant is cross-checked against a same-location base read (data content
at flash address 0 is otherwise unknown), so a variant failing only on
content — not shape — still gets flagged. Shape/protocol correctness for
every variant is independently checked by `QspiMonitor` + `QspiScoreboard`
(section 4), not just the sequence-level `self.check`.

## 3. Functional coverage results (`cocotb-coverage`)

Collected by `QspiCoverage` (`pyuvm_tb/qspi_coverage.py`), which subscribes to
the QSPI monitor's analysis port and samples every transaction decoded off the
wire (ground truth, not intent). The database is cumulative across all four
tests in one `make` run — **460 transactions sampled** — and each test's
`report_phase` rewrites `sim_build/coverage.xml` and `sim_build/coverage.yml`.

**Overall: 73 / 86 bins hit — 84.88 %.**

| Coverpoint | Bins hit | % | Uncovered bins |
|---|---|---|---|
| `cmd` (opcode) | 26 / 29 | 89.7 | `P4E`, `other`, `none` |
| `cmd_lanes` | 1 / 4 | 25.0 | `0`, `2`, `4` |
| `addr_bytes` | 3 / 3 | 100 | — |
| `addr_lanes` | 4 / 4 | 100 | — |
| `dir` | 3 / 3 | 100 | — |
| `data_lanes` | 4 / 4 | 100 | — |
| `dlen` (buckets) | 7 / 7 | 100 | — |
| `dummy` (buckets) | 4 / 4 | 100 | — |
| `sck_mode` | 2 / 2 | 100 | — |
| `endian` | 2 / 2 | 100 | — |
| `aborted` | 1 / 2 | 50.0 | `True` |
| `mode_phase` | 1 / 2 | 50.0 | `True` |
| `dir × data_lanes` | 6 / 7 | 85.7 | `(WR, x2)` |
| `dir × dlen` | 9 / 13 | 69.2 | `(WR,1)`, `(WR,5-8)`, `(WR,33-256)`, `(WR,>256)` |

The 13 uncovered bins are an honest to-do list, not noise:

- **`cmd` — `P4E` (0x20):** defined in the opcode map but no sequence issues it.
  `other` / `none` are catch-all bins that only fire on an unknown opcode or a
  command-less transfer, neither of which happens today.
- **`cmd_lanes` x2 / x4:** every spec command uses an x1 command phase, so
  dual/quad command lanes are never driven; bin `0` needs a command-less
  (CRM-locked) transfer.
- **`aborted=True`:** the abort test *does* run, but the abort flag lives on the
  predictor's transaction object — the monitor-side record the coverage samples
  never carries it. Cosmetic; sampling the predictor stream would close it.
- **`mode_phase=True`:** needs CRM / XIP tests (the predictor's MODE-phase model
  is pending rework anyway — see section 6).
- **`dir × data_lanes` `(WR, x2)` and the `dir × dlen` write buckets:** no
  dual-lane write and no 1-byte / large write in the current sequences — writes
  are PP (x1) and QPP (x4) at 16–32 B.

For context, the busiest bin is `cmd=RDSR1` (386 hits) — WIP polling during
program/erase dominates the transaction count.

### 3.1 Bin-level detail (all coverpoints & crosses)

The **bin** is the atomic unit: one concrete value of an axis. A coverpoint's
"coverage %" above is just (bins hit / total bins); the counts below are how
many sampled transactions landed in each bin over the 460-transaction run.
**Bold `0`** marks an uncovered bin (the open items from the summary table).

**`cmd` — opcode (26 / 29):**

| Group | Bins (hits) |
|---|---|
| Reads (3B) | `READ`:13, `FAST_READ`:4, `DOR`:4, `DIOR`:4, `QOR`:7, `QIOR`:4 |
| Reads (4B) | `READ4`:1, `FAST_READ4`:1, `DOR4`:1, `DIOR4`:1, `QOR4`:1, `QIOR4`:1 |
| Program / erase | `PP`:3, `QPP`:3, `SE`:2, **`P4E`:0** |
| Status / config | `RDSR1`:386, `RDSR2`:1, `RDCR`:5, `WRR`:1 |
| ID | `RDID`:2, `REMS`:1, `RES`:1 |
| Control | `WREN`:10, `WRDI`:1, `CLSR`:1, `RESET`:1 |
| Catch-all | **`other`:0**, **`none`:0** |

**Other coverpoints:**

| Coverpoint | Bins (hits) |
|---|---|
| `cmd_lanes` (1 / 4) | `1`:460 · **`0`:0** · **`2`:0** · **`4`:0** |
| `addr_bytes` (3 / 3) | `0`:409 · `3`:45 · `4`:6 |
| `addr_lanes` (4 / 4) | `0`:409 · `1`:41 · `2`:5 · `4`:5 |
| `dir` (3 / 3) | `none`:15 · `RD`:438 · `WR`:7 |
| `data_lanes` (4 / 4) | `0`:15 · `1`:419 · `2`:10 · `4`:16 |
| `dlen` bucket (7 / 7) | `0`:15 · `1`:393 · `2-4`:4 · `5-8`:32 · `9-32`:14 · `33-256`:1 · `>256`:1 |
| `dummy` bucket (4 / 4) | `0`:431 · `1-7`:10 · `8`:18 · `>8`:1 |
| `sck_mode` (2 / 2) | `0`:454 · `1`:6 |
| `endian` (2 / 2) | `0`:454 · `1`:6 |
| `aborted` (1 / 2) | `False`:460 · **`True`:0** |
| `mode_phase` (1 / 2) | `False`:460 · **`True`:0** |

**Crosses** (illegal combinations `ign_bins`'d out, so totals are 7 and 13, not
3×4 and 3×7):

| Cross | Bins (hits) |
|---|---|
| `dir × data_lanes` (6 / 7) | `(none,0)`:15 · `(RD,1)`:415 · `(RD,2)`:10 · `(RD,4)`:13 · `(WR,1)`:4 · **`(WR,2)`:0** · `(WR,4)`:3 |
| `dir × dlen` (9 / 13) | `(none,0)`:15 · `(RD,1)`:393 · `(RD,2-4)`:3 · `(RD,5-8)`:32 · `(RD,9-32)`:8 · `(RD,33-256)`:1 · `(RD,>256)`:1 · **`(WR,1)`:0** · `(WR,2-4)`:1 · **`(WR,5-8)`:0** · `(WR,9-32)`:6 · **`(WR,33-256)`:0** · **`(WR,>256)`:0** |

## 4. Protocol / scoreboard checkers

These run continuously under every test, not just the sequence above — they
are what actually catches corner-case protocol violations.

| Checker | Rule enforced | Location |
|---|---|---|
| `ApbMonitor` | PENABLE only with PSEL; PENABLE deasserts ≥1 cycle after completion; setup phase always followed by access phase; PADDR/PWRITE/PWDATA stable while stalled | `monitors.py:43` |
| `QspiMonitor` | SCK parked at CPOL idle level on CSn assert/deassert; DUT drives `qspi_oe=0` during read data phase (must not contend with flash); exact SCK edge count per transaction (`expected_edges()`); CSn not deasserted mid-phase (except known abort/KI-1 cases) | `monitors.py:127` |
| `QspiScoreboard` | Wire command/address/mode-byte match programmed CFG; edge count match; TX data-on-wire match; WEL bookkeeping (WREN/WRDI/WRR/CLSR/RESET/SE/PP-QPP); read data vs. golden flash model; RDID/REMS/RES fixed-value checks | `scoreboards.py:65` |
| `FlashGolden` | Byte-accurate golden model: erase→0xFF, program→AND-semantics, 256B page-wrap on PP | `scoreboards.py:42` |

## 5. Boundary / corner cases

| Case | Description | Exercised by | Result |
|---|---|---|---|
| RX FIFO full mid-READ | 66-word READ against 64-word FIFO; DUT must pause SCK exactly at the full boundary and resume on drain | `pause_test` (`SpiModesSeq`) | **PASS** (KI-1 fixed in v0.5.0) |
| TX FIFO full (CSR-level) | 65th DR push after 64 fills → `TX_FULL` FIFO_ERR | `CsrComplianceSeq` | **PASS** |
| DR read while RX empty | → `RX_EMPTY` FIFO_ERR | `CsrComplianceSeq` | **PASS** |
| DR read in write direction | → `WRONG_DIR` FIFO_ERR | `CsrComplianceSeq` | **PASS** |
| Config write while BUSY | APB write must stall (`pready` wait states) until transfer completes | `CsrComplianceSeq` | **PASS** |
| Mid-flight software abort | `CTRL_ABORT` during a slow read; DONE must still assert; partial transaction accepted, not treated as protocol error | `abort_test` (`SpiModesSeq`) | **PASS** |
| Non-word-aligned dlen | dlen=7 READ (partial final DR word); also RES(1B)/REMS(2B)/RDID(4B) in `AllCommandsSeq` | `SpiModesSeq`, `AllCommandsSeq` | **PASS** |
| 4-byte address boundary | Dedicated 4B opcodes with `addr_len4=1` | `SpiModesSeq` | **PASS** (KI-3 fixed in v0.5.1) |
| Address byte integrity (non-zero mid/low bytes) | READ @ 0x000102 — catches a dropped/zeroed address byte | `SpiModesSeq` | **PASS** (KI-3 fixed in v0.5.1) |
| Command-only + dummy cycles | RES (0xAB) with 24 dummy cycles, no address/data phase | `AllCommandsSeq` | **PASS** (KI-6 fixed in v0.5.1) |
| Sector-erase boundary | SE then read-back must return all-0xFF | `AllCommandsSeq` | **PASS** |
| PP page-wrap | Golden model wraps address within 256B page on program | `FlashGolden.program` | modeled, not directly asserted by a dedicated cross-page test |
| Write-path FIFO empty at word boundary (dlen>4 PP/QPP) | DUT previously deadlocked when the write FIFO went empty after the last word was popped into the shifter (paused SCK on `fifo_empty && dir_write`, DONE never asserted) | `AllCommandsSeq`, `FlashDataSeq` | **PASS** (KI-5 fixed in v0.6.0) |
| Simultaneous FIFO push+pop | `rtl/fifo.sv` pop branch was `else if` behind push, so concurrent push+pop froze `rptr` → duplicate/lost word | standalone dual-op directed test (not in the 4 top-level sequences — current sequences pop only after DONE) | **PASS** (KI-7 fixed in v0.1.2, 11/11 checks) |
| SPI mode 3 return-to-idle edge | DUT emits one extra rising SCK edge returning to idle at DONE in mode 3 | `QspiScoreboard.compare`, flagged as a distinct warning | noted, not yet a hard failure |

## 6. Known gaps in this plan

- Coverage sits at **84.88 % (73/86 bins)**; the 13 open bins are enumerated in
  section 3. The reachable ones (write-side `dir × dlen`/`data_lanes` buckets,
  `P4E`, the `aborted` sampling fix) are the concrete next steps; the rest wait
  on CRM/XIP tests.
- No dedicated cross-page-boundary PP test (page-wrap is modeled in
  `FlashGolden` but not specifically asserted against real DUT behavior).
- KI-7 (fifo.sv push+pop race) has no regression inside the 4 top-level
  sequences — it's only proven by a standalone scratchpad testbench, since
  every current sequence pops DR only after DONE.
- CRM (continuous read mode) / MODE-phase semantics changed in the DUT rework
  (mode byte now counts within `dummy_len`); the predictor still models the
  old semantics. Irrelevant today since no sequence exercises CRM yet — and the
  reason `mode_phase=True` coverage stays at 0.
