# apb_qspi pyuvm verification environment

cocotb + pyuvm testbench for `rtl/apb_qspi.sv` (APB wrapper + `qspi_master` +
shared FIFO), simulated against the Infineon S25FL128S flash model. Structure
mirrors the pyuvm flow from [AvlKP/ldpc-personal](https://github.com/AvlKP/ldpc-personal).

```
tb_apb_qspi.sv          DUT wrapper: apb_qspi (FIFO_DEPTH=64) + IO bufs/pullups + S25FL128S
run.py                  Windows runner (no make needed): python run.py [-t TEST] [--waves]
Makefile                cocotb Makefile flow (WSL/Linux)
pyuvm_tb/
  regs.py               register map + CFG0 field packing + DR word packing helpers
  seq_items.py          ApbItem (sequence item), QspiXfer (transaction record)
  bfm.py                APB pin BFM + clock/reset/flash-power-up
  driver.py             ApbDriver (sequencer -> BFM)
  monitors.py           ApbMonitor (APB protocol checks), QspiMonitor (wire decode + SPI checks)
  predictor.py          shadows CSRs from APB traffic; emits expected QSPI xfer on START
  scoreboards.py        predicted-vs-observed compare + FlashGolden memory model
  qspi_coverage.py      functional coverage on the observed transaction stream
  agent_env.py          ApbAgent, QspiEnv
  sequences.py          CSR helpers, flash command library, 4 top-level sequences
  test.py               the 4 @pyuvm.test classes
```

## Running

```sh
# WSL/Linux/IIC-OSIC-TOOLS (make flow)
make                                    # all 4 tests
make test_apb                           # shortcuts: test_apb/test_spi/test_cmds/test_flash
make COCOTB_TESTCASE=ApbComplianceTest  # explicit single test
make test_apb WAVES=1                   # + sim_build/tb_apb_qspi.fst (open in surfer/gtkwave)

# Windows (no make)
python run.py                           # all 4 tests
python run.py -t ApbComplianceTest      # one test
python run.py -t ApbComplianceTest --waves   # + sim_build/tb_apb_qspi.fst
```

Env knobs (both flows): `WAIVERS=0` turns known-issue waivers into hard errors;
`FIFO_PROBE=1` traces every FIFO push/pop with occupancy and data.

Requires `pip install cocotb pyuvm` (developed against cocotb 2.0.1 / pyuvm 4.0.1)
and Icarus Verilog. Optional: `pip install cocotb-coverage` for functional
coverage (env runs without it, sampling is just skipped).

## Functional coverage

Every transaction the QSPI monitor decodes off the wire is sampled into
cocotb-coverage coverpoints (`pyuvm_tb/qspi_coverage.py`): command opcode,
lanes per phase, address length, direction, dlen/dummy buckets, SCK mode,
endianness, abort, MODE-phase presence, plus direction x lanes and
direction x dlen crosses. The database is cumulative across all tests in one
run; each test's report_phase logs running totals and rewrites
`sim_build/coverage.xml` / `coverage.yml` (full 4-test run: 73/86 bins).
Known-uncoverable-today bins double as a to-do list: dual/quad *command*
phase (spec commands are all x1-cmd), MODE phase (needs CRM tests), and
`aborted=True` (the monitor-side record never carries the abort flag; the
predictor's does).

## Tests

| Test | Checks | Status (qspi_master v0.6.0, fifo v0.1.2) |
|---|---|---|
| `ApbComplianceTest` | APB protocol rules (monitor: PENABLE⇒PSEL, setup→access, stability under stalls, ENABLE deassert), CSR reset values, full-word readback, RO regs, W1C semantics, FIFO error codes (RX_EMPTY / WRONG_DIR / TX_FULL), pready stall-while-busy | **PASS** |
| `SpiComplianceTest` | every lane combo (1-1-1, fast, 1-1-2, 1-2-2, 1-1-4, 1-4-4), each with variants: SPI mode 3, little-endian DR packing, 4-byte addressing (0x13/0x0C/0x3C/0xBC/0x6C/0xEC), non-word-aligned dlen=7; prescaler run; address-integrity probe @0x000102; FIFO-full SCK pause test (264B read, mid-flight drain); software abort test | **PASS** |
| `AllCommandsTest` | all spec commands end-to-end: WREN/WRDI (WEL), RDID/REMS/RES (fixed IDs), RDSR1/RDSR2/RDCR, WRR, SE + erased readback, PP+READ, QPP+QOR, CLSR, RESET | **PASS** |
| `FlashModelTest` | randomized program/readback data integrity vs golden flash model, x1 and x4 | **PASS** |

Full regression 2026-07-11: **4/4 PASS, zero errors, zero waivers triggered.**
All previously tracked DUT issues are fixed and verified.

## DUT issue tracker

Fixed (verified by this env):

- **KI-1 — SCK-pause desync**: FIXED in v0.5.0. The new `qspi_sck_pause`
  freezes the pin toggle and all counters/shifters coherently. The 264-byte
  FIFO-full pause test confirms pause/resume with an exact edge count.
- **KI-2 — TX byte load indexing**: FIXED in v0.5.0. `tx_shifter_preset` +
  anticipatory mux indices deliver correct TX streams; WRR sends [00, 02],
  QE sets, and all quad lane modes pass shape compare.
- **KI-3 — ADDRESS phase never reloads the shifter**: FIXED in v0.5.1 (load
  added to the non-final byte boundary). Probe read @0x000102 now shows the
  correct wire address; 4-byte addressing variants pass.
- **KI-6 — command-only transfers lose dummy cycles**: FIXED in v0.5.1
  (COMMAND state regained its DUMMY branch). RES returns 0x17 again.
- **KI-5 — write-path SCK pause deadlocked every PP/QPP with dlen > 4**:
  FIXED in v0.6.0 (the `qspi_wdata` holding register was removed, the TX mux
  reads the FIFO output directly, pops moved to `qspi_wdata_ready` at
  `[1:0]==2` boundaries plus a final drain pop at `last_byte`, and the DATA
  pause only fires at mid-transfer word boundaries). Verified: 16B PP and
  32B PP/QPP complete with exact edge counts (8+24+128 for 16B PP) and
  byte-exact TX data on the wire; AllCommands + FlashModel pass end to end.
- **KI-7 (fifo.sv) — simultaneous push+pop froze the read pointer**:
  FIXED in v0.1.2 (pop branch is now an independent `if`, both pointers
  update in the same cycle). Verified with the standalone dual-op directed
  test re-run (11/11 checks: dual-op head advance, occupancy hold, dual-op
  at full, drain order without duplicate/lost words).

Still open: none.

Testbench-side fix found during the v0.6.0 regression (TB-1, our bug, not
the DUT): `tb_apb_qspi.sv` instantiated the S25FL128S model without a
`TimingModel` parameter. The model parses that string's 15th/16th characters
for latency config and sector/page size; with the default
`"DefaultTimingModel"` its `PageSize`/`SecSize` integers stay X, the PP/QPP
`WByte` assembly loop (`for i=0..PageSize`) never iterates, and every page
program silently writes X (reads back as all-X SO / scoreboard `0x00`) even
though the wire transaction is byte-perfect. Masked until now because KI-5
hung every PP before its data ever reached the model's program dispatch.
Fixed by instantiating with `.TimingModel("S25FL128SAGMFI000_R_30pF")`
(256-byte page, 64KB sectors — matches the golden model's assumptions).

Also noted: in SPI mode 3 the DUT emits one extra rising edge returning SCK
to idle at DONE (flagged by the scoreboard as a distinct message). The
MODE-phase semantics also changed in the rework (mode byte now counts within
`dummy_len`, MODE entered only when `crm && dummy != 0`); the env's predictor
still models the old semantics — irrelevant until CRM tests exist.

## Design notes

- The QSPI wire format is not self-describing, so the monitor receives each
  transaction's phase shape from the predictor (built from the same APB writes
  that configured the DUT) via a queue, then decodes and checks independently.
- The golden flash model tracks memory only where the testbench has made it
  knowable (erase → 0xFF, program → AND semantics, page wrap), and mirrors
  wire-observed operations, so it stays truthful even when the DUT corrupts a
  transfer.
- One shared RX/TX FIFO sits behind QSPI_DR per the spec; sequences flush
  between direction changes. Reads pop after DONE, so keep dlen ≤ 256 bytes
  (FIFO_DEPTH=64 words).
- The S25FL128S model runs with `SPEEDSIM` (tPU 300 µs, WRR ~2 ms, SE ~6.5 ms
  sim time). Flash reset is a separate wrapper port so re-resetting the DUT
  between tests doesn't re-trigger power-up.


## [Back to `testbench.md`](../../../docs/testbench.md)