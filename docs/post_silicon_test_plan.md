# Post-Silicon Test Plan - A09 Crispi QSPI Master (`A09_BV`)

This document is the plan for testing the fabricated `A09_BV` chip from the IEEE SSCS Chipathon 2026 GF180MCU shuttle (January 2027 tapeout). It states what is tested, on which hardware, in what order, what counts as a pass, how results are recorded, and who does what.

| Item | Value | Source |
|---|---|---|
| Design | `A09_BV`, 32-bit QSPI master with UART-to-APB host interface | [`A09_BV.sv`](../layout/chipathon26-template/macros/A09_BV/A09_BV.sv) |
| Block size | 550 um x 1110 um (block type BV) | issue #74 |
| Core clock | 40 MHz (`CLOCK_PERIOD: 25` ns) | [`config.yaml`](../layout/chipathon26-template/macros/A09_BV/config.yaml) |
| UART | 8N1, 2 Mbps at 40 MHz (`BAUD_RATE = 2_000_000`, fixed ratio of 20 clocks per bit) | `A09_BV.sv` |
| QSPI clock | `SCK = clk / (2 x PRESCALER + 2)`, so 20 MHz at `PRESCALER = 0` | [`qspi_master.sv`](../rtl/qspi_master.sv) lines 85-115 |
| Chip selects | 2 (`CS_NUM = 2`) | `A09_BV.sv` |
| Primary test supply | 3.3 V on `VDD` | this plan, section 3 |

## 1. Signoff numbers this plan checks against

These are the pre-silicon numbers that the silicon results are compared to. They come from [`final/metrics.json`](../layout/chipathon26-template/macros/A09_BV/final/metrics.json) of the hardened macro and from the simulation reports.

Worst setup slack at 40 MHz (positive means timing is met with that much time left in the 25 ns period):

| STA corner (process, temperature, VDD) | Worst setup slack (ns) | Max-slew violations |
|---|---|---|
| tt, 25 C, 3.30 V | 12.21 | 0 |
| ff, -40 C, 3.60 V | 15.37 | 0 |
| ss, 125 C, 3.00 V | 0.45 | 92 |
| tt, 25 C, 5.00 V | 14.43 | 0 |
| ff, -40 C, 5.50 V | 16.39 | 0 |
| ss, 125 C, 4.50 V | 9.28 | 0 |

The STA power estimate is 25.5 mW total (`power__total`; the metrics file does not name the corner). At 3.3 V that is about 7.7 mA of core current. It excludes the I/O pads.

Simulation status: `tb_apb_qspi` passes 4/4 tests with 84.88 % functional coverage (73 of 86 bins) against the S25FL128S model ([`verification_plan.md`](../sim/cocotb/tb_apb_qspi/verification_plan.md), regression of 2026-07-11). `tb_top` covers the full UART path ([`tb_top/README.md`](../sim/cocotb/tb_top/README.md)).

## 2. Pins and fixed pad settings

The pad drive strength, slew rate and pulls are tied off in RTL (`A09_BV.sv` lines 76-119). They cannot be changed on silicon.

| Pin | Direction | Pad type (`info.yaml`) | Drive | Pull | Connects to |
|---|---|---|---|---|---|
| `VDD`, `VSS` | power | power / ground | - | - | bench supply |
| `clk` | in | Schmitt input | - | none | 40 MHz oscillator or FPGA clock |
| `rst_n` | in | CMOS input | - | none | reset button or FPGA GPIO (active low) |
| `uart_rx` | in | CMOS input | - | none | USB-UART TX |
| `uart_tx` | out | bidirectional, output only | 8 mA, fast | none | USB-UART RX |
| `qspi_csn[0]`, `qspi_csn[1]` | out | bidirectional, output only | 12 mA, fast | pull-up | flash `CS#` |
| `qspi_sck` | out | bidirectional, output only | 12 mA, fast | none | flash `CLK` |
| `qspi_io[3:0]` | in/out | bidirectional, `OE` from controller | 16 mA, fast | pull-up | flash `IO0`-`IO3` |

`clk`, `rst_n` and `uart_rx` have no pull resistors on chip, so the board must never leave them floating.

## 3. Supply voltage

The GF180MCU I/O pads are 5 V pads that also work at 3.3 V ([Chipathon Integration README](https://github.com/sscs-ose/sscs-chipathon-2026/blob/main/resources/Integration/README.md)). The memories we test against are 2.7-3.6 V parts, so a 5 V supply would drive 5 V into them. For that reason:

* **All Tier 1 and Tier 2 tests run at VDD = 3.3 V**, with the memories connected directly to the pads.
* An **optional 5 V run** uses only the Microchip 23LC1024 SRAM (rated 2.5-5.5 V, `microchip-PSRAM-23LC1024.pdf` parameter D001). Every 3 V memory must be **removed** from the board before VDD is raised above 3.6 V.

Timing at 3.3 V has 12.21 ns of slack at the typical corner (section 1), so 40 MHz is expected to work at room temperature.

## 4. Test setup

The organisers deliver packaged chips without a test board, as in the previous Chipathon, so the team designs its own test PCB. The package (64 pins, QFN or QFP) and the bond map (which package pin connects to each of our pads) have not been decided by the organisers yet (section 14, item 2), so the board is specified here by what it must provide, not by its layout.

```
 +-----------+  USB-UART  +----------------------------------+   PMOD    +-------------+
 |    PC     |<---------->| team test PCB                    |<--------->|  PYNQ-Z1    |
 | silicon_  | (FT232R or |  chip (64-pin package, TBD)      | clk,rst_n |  MMCM clock |
 | test.py   |  CP2102N)  |  W25Q32JV on qspi_csn[0]         |   PMOD    |  generator, |
 +-----------+            |  MX25L6445E on qspi_csn[1]       |---------->|  ILA on     |
                          |  shared qspi_sck, qspi_io[3:0]   | (monitor) |  qspi_*     |
         bench supply --->|  VDD (chip), 3.3 V (memories)    |           +-------------+
                          +----------------------------------+
```

**Board requirements.** The test PCB must provide:

1. an adjustable supply for our `VDD` (2.7-3.6 V, and 5.0 V for the optional C5 run) with a current readout, separate from the 3.3 V supply of the memories;
2. a 40 MHz clock on `clk`, with a way to take `clk` from the PYNQ-Z1 instead for the clock sweep (C2);
3. control of `rst_n`, from a button or from the PYNQ-Z1;
4. a 3.3 V USB-UART bridge to the PC that supports 2 Mbps;
5. the two Tier 1 memories close to the chip with short traces, on `qspi_csn[0]` and `qspi_csn[1]`, and a way to fit the Tier 2 parts;
6. test points on `qspi_sck`, `qspi_csn[1:0]` and `qspi_io[3:0]` for the oscilloscope;
7. a PMOD connection to the PYNQ-Z1 (3.3 V PMOD headers) carrying `clk`, `rst_n` and the QSPI lines.

The board architecture (for example one board, or a chip adapter on a separate motherboard) is decided by the hardware owner once the package and bond map are known (section 12, task 5).

**Role of the PYNQ-Z1.** It generates `clk` from an MMCM (Mixed-Mode Clock Manager, the FPGA's on-chip clock synthesiser) so the frequency can be swept, drives `rst_n`, and monitors the QSPI lines with an ILA (Integrated Logic Analyzer, Xilinx's on-chip logic analyser). It is only an instrument: the memories sit on the test PCB, not at the end of a PMOD cable. Before silicon arrives, it also runs the RTL as a stand-in chip to validate the test script (section 7).

**Bench equipment:** a bench supply with current readout, a digital multimeter, an oscilloscope of at least 200 MHz bandwidth, and the PC running `interface/silicon_test.py` (section 7).

## 5. Memories under test

| Tier | Part | Type | Size | Supply | What it proves | Status |
|---|---|---|---|---|---|---|
| 1 | Winbond W25Q32JV | NOR flash | 32 Mb | 2.7-3.6 V | x1/x2/x4 reads, program, erase | owned |
| 1 | Macronix MX25L6445E | NOR flash | 64 Mb | 2.7-3.6 V | x1/x2/x4 reads, 1-4-4 program, DTR read (to be confirmed) | owned |
| 2 | Macronix MX25L51245G | NOR flash | 512 Mb | 2.7-3.6 V | 4-byte (32-bit) addressing above 16 MB, DTR read | to purchase |
| 2 | AP Memory APS6404L-3SQR | quad PSRAM | 64 Mb | 2.7-3.6 V | quad write, random access without erase | to purchase |
| 2 | Microchip 23LC1024 (LC variant only) | SPI/SQI SRAM | 1 Mb | 2.5-5.5 V | SQI write/read, optional 5 V run | to purchase |

Notes:

* The W25Q32JV and MX25L6445E datasheets are not yet in [`datasheet/`](../datasheet/). Their supply range, JEDEC IDs and DTR support must be confirmed from the datasheets before the pre-silicon re-simulation (section 10, item 3). The plain W25Q32JV has no DTR mode; Winbond sells DTR as a separate "-DTR" part.
* The 23LC1024 is limited to 20 MHz SCK (`microchip-PSRAM-23LC1024.pdf`, selection table). The 23**A**1024 is a 1.7-2.2 V part and must not be used.
* On the test PCB, the W25Q32JV sits on `qspi_csn[0]` and the MX25L6445E on `qspi_csn[1]`, sharing `qspi_sck` and `qspi_io[3:0]`. This tests both chip-select lines without rewiring.

## 6. Bring-up sequence

Each step must pass before the next. A failing step goes to the triage column instead.

| Step | Action | Pass | If it fails |
|---|---|---|---|
| B1 | Visual check of the package and board; continuity of `VDD`-`VSS` (no short) | resistance well above 0 ohm | do not power; inspect bonding/soldering |
| B2 | Power `VDD` = 3.3 V with a 100 mA current limit, `clk` stopped, `rst_n` low | current limit not reached; record current | stop; record current; check for shorts |
| B3 | Start 40 MHz `clk`, hold `rst_n` low for at least 1 us, then release | `uart_tx` idles high; `qspi_csn[1:0]` high; `qspi_sck` idle | probe `clk` at the pad; check `rst_n` level |
| B4 | UART: read `QSPI_CTRL` (0x00) and `QSPI_CFG0` (0x04) | reply has the ACK byte and the reset values seen in simulation | check baud = clk / 20; retry at clk 20 MHz and 1 Mbps; scope `uart_tx` |
| B5 | CSR write/readback on `CFG0`, `DLEN`, `ADDR`, `TIMEOUT` with 0x00000000, 0xFFFFFFFF, 0xA5A5A5A5, 0x5A5A5A5A and walking ones | every readback equals the written value; `BCNT` write does not stick | log the failing bits; repeat at lower clk |
| B6 | RDID (0x9F) on `qspi_csn[0]` at `PRESCALER = 3` (5 MHz SCK) | JEDEC ID matches the datasheet | scope SCK, CS#, IO0, IO1; check memory power |

Steps B2-B6 form the **smoke test** (section 8).

## 7. Test software

`interface/silicon_test.py` (owner: Hifz) is a scripted regression that runs on the PC. It uses the same UART protocol as [`uart_fpga_gui.py`](../interface/uart_fpga_gui.py) ([protocol](uart_fpga_gui.md)) and implements the test steps of sections 6, 8 and 9 as the cocotb tests do in simulation. For every test it records pass/fail and the raw data (section 11).

Before silicon arrives, the script is validated against the RTL running on the PYNQ-Z1 with the same W25Q32JV and MX25L6445E parts. That run is the known-good baseline the chip is compared with. [`uart_fpga_gui.py`](../interface/uart_fpga_gui.py) remains the tool for manual debugging.

## 8. Functional tests

All functional tests run at VDD = 3.3 V and `clk` = 40 MHz, at `PRESCALER = 0` (SCK 20 MHz) and `PRESCALER = 3` (SCK 5 MHz). Each test lists the simulation test it mirrors. A test passes when every read-back byte equals the expected byte, every transfer ends with `DONE = 1` and `FIFO_ERR = 0`, and no unexpected `TIMEOUT` occurs.

### 8.1 Tier 1 (must pass, owned parts: W25Q32JV and MX25L6445E)

| ID | Test | Opcodes | Mirrors | Pass |
|---|---|---|---|---|
| T1-01 | ID reads on both chip selects | RDID 0x9F, REMS 0x90, RES 0xAB | `AllCommandsTest`, `tb_top::test_qspi_rdid` | IDs match the datasheets |
| T1-02 | Status register and write enable | RDSR 0x05, WREN 0x06, WRDI 0x04 | `AllCommandsTest` | WEL bit follows WREN/WRDI |
| T1-03 | Sector erase and erased read | SE 0x20, READ 0x03 | `AllCommandsTest` | 4 KB sector reads all 0xFF |
| T1-04 | Page program and read, x1 | PP 0x02, READ 0x03 | `tb_top::test_qspi_program_read` | 256 B random pattern reads back exactly |
| T1-05 | Fast read | FAST_READ 0x0B (8 dummy) | `SpiComplianceTest` | equals T1-04 data |
| T1-06 | Dual reads | 0x3B (1-1-2), 0xBB (1-2-2) | `SpiComplianceTest` | equals T1-04 data |
| T1-07 | Quad enable and quad reads | QE bit set per datasheet, 0x6B (1-1-4), 0xEB (1-4-4) | `SpiComplianceTest` | equals T1-04 data |
| T1-08 | Quad program | W25Q32JV 0x32 (1-1-4), MX25L6445E 0x38 (1-4-4) | `AllCommandsTest` (QPP) | random 256 B reads back exactly |
| T1-09 | Controller options | SCK mode 0 and 3; big/little endian; 3-byte address; length 7 (partial word); 264 B read (FIFO-full SCK pause); abort mid-read; timeout | `SpiComplianceTest` | each variant equals the base read; abort still sets `DONE` |
| T1-10 | Data integrity | 4 KB random data, programmed and read in x1, x2 and x4 | `FlashModelTest` | 0 mismatched bytes over 4 KB per lane width |
| T1-11 | DTR read (MX25L6445E, if confirmed) | FASTDTRD 0x0D, 4DTRD 0xED, `CFG0.DDR = 1` | `tb_qspi_master` DDR tests | equals T1-04 data; moves to Tier 2 if the part has no DTR |

### 8.2 Tier 2 (extended, parts to purchase)

| ID | Test | Part | Pass |
|---|---|---|---|
| T2-01 | 4-byte addressing: EN4B 0xB7 and 4-byte opcodes 0x13, 0x0C, 0x3C, 0xBC, 0x6C, 0xEC; data written above 16 MB and read back | MX25L51245G | exact read-back; no aliasing to address - 16 MB |
| T2-02 | DTR quad read 0xEE/0xED family | MX25L51245G | exact read-back |
| T2-03 | Quad PSRAM: enter quad 0x35, quad write 0x38, quad read 0xEB; 64 KB random data | APS6404L | 0 mismatched bytes |
| T2-04 | SQI SRAM at 3.3 V: EQIO 0x38, write 0x02, read 0x03; 128 KB random data; SCK at most 20 MHz | 23LC1024 | 0 mismatched bytes |
| T2-05 | Continuous read mode (`CFG0.CRM = 1`) with mode byte | W25Q32JV, MX25L6445E | second read without opcode returns correct data |
| T2-06 | Paths not covered in simulation: dual-lane write, 1-byte and >256 B writes, quad command phase (QPI) where the part supports it | APS6404L, MX25L51245G | exact read-back |

## 9. Characterisation

Characterisation runs on 3 chips (section 10). Every point is recorded per chip; values from different chips are never averaged.

| ID | Measurement | Method | Recorded value |
|---|---|---|---|
| C1 | Supply current | Bench supply readout or series shunt with a DMM; (a) `clk` running, idle; (b) continuous x4 read at SCK 20 MHz | mA at 3.3 V for (a) and (b); compare with the 7.7 mA STA estimate |
| C2 | Highest working `clk` at 3.3 V | Raise `clk` from 40 MHz in 2 MHz steps (PYNQ-Z1 MMCM or a function generator). The UART baud follows `clk / 20`, so the PC baud is changed at every step. At each step run a 1 KB x4 read and compare. | last passing `clk` in MHz |
| C3 | Lowest working VDD at 40 MHz | Lower VDD from 3.6 V in 0.1 V steps to 2.7 V (the memory minimum), running T1-10 at each step. Below 2.7 V a failure says nothing about our chip. DTR reads stop at the lower limit in the memory datasheet. | lowest passing VDD in V |
| C4 | Signal quality at the fixed pad settings | Scope `qspi_sck` and `qspi_io0` at the memory pin at SCK 20 MHz | rise time, fall time, overshoot, ringing |
| C5 | Optional 5 V run | Remove all 3 V memories. 23LC1024 only, VDD 5.0 V, `PRESCALER = 1` (SCK 10 MHz). The USB-UART interface must accept 5 V levels on its RX pin. Run T2-04. | pass/fail; supply current at 5 V |

For C2 and C3, repeating one setting several times only samples the setup's own noise. A failure that repeats at one setting counts as one failure point, not several.

## 10. Sample plan and pass criteria

Each chip gets a label written on the package or carrier, for example `A09-U01`, used in every log line.

| Stage | Chips | Tests |
|---|---|---|
| Smoke | every chip | B2-B6 |
| Tier 1 | every chip that passes smoke | T1-01 to T1-11 |
| Tier 2 and characterisation | 3 chips that pass Tier 1 | T2-01 to T2-06, C1 to C5 |

* **A chip passes** when it passes the smoke test and all of Tier 1 at VDD = 3.3 V and `clk` = 40 MHz.
* **The design is verified** when at least one chip passes Tier 1 and Tier 2.
* **Yield** is reported as chips passing Tier 1 divided by chips tested, with both numbers stated.
* A chip that fails is not removed from the count. Its failure is diagnosed (design bug versus manufacturing defect) and reported.

## 11. Data logging and reporting

`silicon_test.py` appends one row per test step to `silicon_results/<chip_id>/<date>_<board_rev>.csv` with these columns:

`timestamp, chip_id, board_rev, clk_source, vdd_V, clk_MHz, baud, prescaler, memory_part, chip_select, test_id, result, bytes_compared, bytes_mismatched, notes`

Raw read-back dumps, scope screenshots and ILA captures are stored next to the CSV. The final report (`docs/post_silicon_results.md`) gives per-chip tables, the yield, the C1-C5 values next to the signoff numbers of section 1, and every deviation from this plan.

## 12. Pre-silicon preparation

| # | Task | Owner | Due |
|---|---|---|---|
| 1 | Write `interface/silicon_test.py` covering sections 6, 8 and 9 | Hifz | T0 + 4 weeks |
| 2 | Validate the script against the RTL on the PYNQ-Z1 with W25Q32JV and MX25L6445E; store the baseline logs | Hifz | T0 + 4 weeks |
| 3 | Add the W25Q32JV and MX25L6445E datasheets to `datasheet/`; confirm IDs, QE bit and DTR support; obtain their vendor Verilog models and re-run `tb_qspi_master` and `tb_apb_qspi` against them | Hifz | T0 + 4 weeks |
| 4 | Buy the Tier 2 parts and USB-UART bridges | Irfan | T0 + 8 weeks |
| 5 | Design the test PCB to the section 4 requirements once the package and bond map are published; choose the board architecture | Irfan | T0 + 8 weeks, or 4 weeks after the bond map is published if later |
| 6 | Prepare the bench: supply, DMM, scope, probes; write the measurement procedure for C1-C5 | Velin | T0 + 8 weeks |

## 13. Schedule and owners

T0 is the tapeout date (January 2027). S0 is the day packaged chips arrive. The organisers have not announced S0.

| Milestone | Target |
|---|---|
| Test script written and validated on the PYNQ-Z1 | T0 + 4 weeks |
| Parts bought; test PCB designed | T0 + 8 weeks |
| Smoke test done on all chips | S0 + 1 week |
| Tier 1 done on all chips | S0 + 3 weeks |
| Tier 2 and characterisation done on 3 chips | S0 + 6 weeks |
| Results report published in this repository | S0 + 8 weeks |

| Role | Person | Responsible for |
|---|---|---|
| Test lead | Nur Dawam | this plan, scheduling, pass/fail decisions, final report |
| Software / script | Hifz | `silicon_test.py`, FPGA baseline, re-simulation with the owned parts |
| Hardware / board | Irfan | test PCB, package and bond map follow-up with the organisers, parts |
| Measurement | Velin | bench setup, C1-C5 measurements, scope and ILA captures |

## 14. Open items and risks

| # | Item | Effect | Action |
|---|---|---|---|
| 1 | It is not confirmed that our `VDD` pad powers only our block on the shared die | If the supply is shared, we may not choose 3.3 V, and C1 would include other blocks' current | Ask the organisers on issue #74 |
| 2 | Package (64-pin, QFN or QFP) and bond map not decided by the organisers | The test PCB cannot be laid out yet | Ask the organisers on issue #74; track announcements |
| 3 | The intake form lists 5 V core and I/O; this plan tests at 3.3 V | Mismatch in the organisers' records | Raise on issue #74 |
| 4 | W25Q32JV and MX25L6445E datasheets not in the repository | IDs, QE bit and DTR support of T1-01, T1-07 and T1-11 are unconfirmed | Pre-silicon task 3 |
| 5 | `docs/qspi_master.md` and `docs/uart_fpga_gui.md` state a minimum `PRESCALER` of 2, while the RTL and all testbenches use 0 | The plan assumes 0 works, as in simulation | Correct the docs or confirm the limit |
| 6 | Thin margin at the slow corner (0.45 ns slack, 92 slew violations at ss, 125 C, 3.00 V) | Vmin in C3 may be close to 3.0 V; room temperature is expected to be fine | Report C3 against this corner |
| 7 | No scan chain or debug port; the UART is the only way in | If B4 fails, the core cannot be observed directly | Triage in B3-B4: clock at the pad, reset level, baud = clk / 20, lower clk |
| 8 | Pad drive strength and slew are fixed in RTL | No drive-strength sweep is possible on silicon | C4 measures signal quality at the fixed settings |
