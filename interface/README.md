# UART FPGA Bridge GUI

A Python/Tkinter GUI for configuring and testing a QSPI master peripheral
(`qspi_master.sv`) over UART (8N1), with a dedicated tab for every register
plus an in-app reference guide.

## Protocol

- PC sends 1 **ADDR** byte (7-bit register offset + mode bit).
  - MSB = `1` -> **WRITE** mode
  - MSB = `0` -> **READ** mode
- **READ** mode: FPGA responds with 1 ACK byte, then 4 data bytes.
  Sequence: `ADDR, ACK, DATA, DATA, DATA, DATA`.
- **WRITE** mode: PC sends 4 data bytes, FPGA responds with 1 ACK byte.
  Sequence: `ADDR, DATA, DATA, DATA, DATA, ACK`.

**Byte order:** all 32-bit register values are transmitted **high byte
first** (big-endian). Both the Python GUI and the ESP32 test firmware
reconstruct/log the 32-bit value this way
(`int.from_bytes(data, byteorder="big")` in Python;
`(data[0]<<24)|(data[1]<<16)|(data[2]<<8)|data[3]` in firmware).

**Write timing:** the ADDR byte and the 4 DATA bytes are sent in a single
`write()` call (one UART/USB burst) rather than two separate calls, to avoid
an inter-byte gap caused by some USB-serial adapters' internal latency
timers.

UART settings: 8 data bits, No parity, 1 stop bit (8N1), baud rate
configurable in the GUI.

## Register Map

| Offset | Register | Access | Description |
|---|---|---|---|
| `0x00` | `QSPI_CTRL` | RW/RO | Control / status (see bit table below) |
| `0x04` | `QSPI_CFG0` | RW | Config, packed (see bit table below) |
| `0x08` | `QSPI_DLEN` | RW | Data length in bytes -> `qspi_data_len_i` |
| `0x0C` | `QSPI_CMD` | RW | Command opcode + XIP mode byte (see bit table below) |
| `0x10` | `QSPI_ADDR` | RW | Target device address -> `qspi_addr_i` |
| `0x14` | `QSPI_DR` | RW | TX/RX FIFO data word (direction-gated by `CFG0.DATA_DIR`) |
| `0x18` | `QSPI_BCNT` | RO | Bytes transferred so far -> `qspi_byte_cnt_o` |
| `0x1C` | `QSPI_TIMEOUT` | RW | Timeout value -> `qspi_timeout_i` (units not yet confirmed) |

### `QSPI_CTRL` (0x00) bit fields

| Bits | Field | Access | Description |
|---|---|---|---|
| `[31:10]` | RESERVED | - | - |
| `[9]` | `FLUSH` | WO, pulse | Flush FIFO |
| `[8:5]` | `FIFO_ERR` | RO, W1C | FIFO error flags |
| `[4]` | `TIMEOUT` | RO, W1C | Timeout occurred -> `qspi_timeout_o` |
| `[3]` | `BUSY` | RO | Transaction in progress |
| `[2]` | `DONE` | RO, W1C | Transaction complete |
| `[1]` | `ABORT` | WO, pulse | Abort current transaction |
| `[0]` | `START` | WO, pulse | Start transaction |

`START`/`ABORT`/`FLUSH` are self-clearing pulse bits — write a single `1`
to the relevant bit with everything else `0`; no read-modify-write needed
since every other bit is RO or W1C. `DONE`/`TIMEOUT`/`FIFO_ERR` clear by
writing `1` back to them (write-1-to-clear).

### `QSPI_CFG0` (0x04) bit fields

| Bits | Field | Access | Description |
|---|---|---|---|
| `[31:30]` | RESERVED | - | - |
| `[29:26]` | `CSN_SEL` | RW | Chip-select lines to activate, active HIGH, one bit per CS (4 lines) |
| `[25]` | `ENDIAN` | RW | `0` = Big Endian, `1` = Little Endian |
| `[24]` | `DDR` | RW | Dual Data Rate enable |
| `[23]` | `CRM` | RW | Continuous Read Mode enable |
| `[22]` | `DATA_DIR` | RW | `0` = Read, `1` = Write |
| `[21]` | `SCK_MODE` | RW | `0` = Mode 0, `1` = Mode 3 |
| `[20:19]` | `DATA_MODE` | RW | `00`=None, `01`=Single, `10`=Dual, `11`=Quad |
| `[18:17]` | `ADDR_MODE` | RW | Same encoding as `DATA_MODE` |
| `[16:15]` | `CMD_MODE` | RW | Same encoding as `DATA_MODE` |
| `[14:9]` | `DUMMY_LEN` | RW | Dummy cycles, `0`-`63` |
| `[8]` | `ADDR_LEN` | RW | `0` = 3-byte addressing, `1` = 4-byte addressing |
| `[7:0]` | `PRESCALER` | RW | SCK freq = `fclk / (prescaler*2+2)`, min `2` |

### `QSPI_CMD` (0x0C) bit fields

| Bits | Field | Access | Description |
|---|---|---|---|
| `[31:16]` | RESERVED | - | - |
| `[15:8]` | `MODE_BYTE` | RW | XIP mode byte -> `qspi_mode_byte_i` |
| `[7:0]` | `CMD` | RW | Command opcode -> `qspi_cmd_i` |

`QSPI_DLEN`, `QSPI_ADDR`, `QSPI_DR`, `QSPI_BCNT`, and `QSPI_TIMEOUT` are
plain 32-bit values with no internal bit-field packing.

## Requirements

- Python 3.9+
- `pyserial` (see `requirements.txt` — no other third-party packages are
  used; everything else, including the GUI toolkit, is Python standard
  library)

## Setup (venv)

Using a virtual environment keeps this project's dependencies isolated from
the rest of your system, and lets anyone on the team reproduce the exact same
setup from `requirements.txt`.

### 1. Clone the repo and move into it

```bash
git clone <your-repo-url>
cd <your-repo-folder>
```

### 2. Create the virtual environment

**Windows (PowerShell / cmd):**
```bash
python -m venv venv
```

**macOS / Linux:**
```bash
python3 -m venv venv
```

This creates a `venv/` folder containing an isolated Python install. It is
machine-specific, so **do not commit it to git** (see `.gitignore` note
below).

### 3. Activate the virtual environment

**Windows (PowerShell):**
```bash
venv\Scripts\Activate.ps1
```
If you get a script execution error, run PowerShell as admin once and use:
```bash
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**Windows (cmd.exe):**
```bash
venv\Scripts\activate.bat
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

You'll know it worked when your terminal prompt is prefixed with `(venv)`.

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the GUI

```bash
python uart_fpga_gui.py
```

### 6. Deactivate when done

```bash
deactivate
```

## Sharing this setup with your colleague

Only `requirements.txt`, the `.py` source, and this `README.md` need to be in
the repo. Your colleague then just runs steps 1-4 above on their own machine
and gets the identical dependency versions — the `venv/` folder itself is
never shared or committed, it's regenerated locally each time.

Recommended `.gitignore` entries:

```
venv/
__pycache__/
*.pyc
```

## GUI Tabs

- **Guide** — scrollable in-app reference mirroring this README: feature
  list, UART framing table, full register map, per-register bit-field
  tables, and a suggested workflow. Meant to be the first stop for anyone
  new to the tool.
- **Raw Transaction** — manual byte-level control: pick Read/Write, enter
  any 7-bit hex `ADDR` and (for writes) a 4-byte hex data string, and send
  it directly. Useful for probing registers not yet covered by a dedicated
  tab, or for debugging unexpected responses.
- **QSPI Config (CFG0)** — friendly widgets (checkboxes, radios, dropdowns,
  spinboxes) for every `QSPI_CFG0` field, with a live packed-hex/binary
  preview as you edit and an optional FPGA clock field to preview the
  resulting SCK frequency. `Write Config to FPGA` packs and sends it;
  `Read Config from FPGA` reads back and unpacks the live value into the
  widgets.
- **Control (CTRL)** — `Start QSPI`, `Abort QSPI`, `Flush FIFO` pulse
  buttons, plus `Read Status` (decodes `BUSY`/`DONE`/`TIMEOUT`/`FIFO_ERR`)
  and `Clear DONE / TIMEOUT / FIFO_ERR` (write-1-to-clear all three at
  once).
- **Transaction Setup** — `QSPI_DLEN`, `QSPI_CMD` (separate `CMD` and
  `MODE_BYTE` fields, packed/unpacked automatically), `QSPI_ADDR`, and
  `QSPI_TIMEOUT`, each with its own Write/Read controls.
- **FIFO & Status** — `QSPI_DR` push (write, TX FIFO) / pop (read, RX FIFO),
  and `QSPI_BCNT` read-only byte-count display.

Every Write/Read action across all tabs shares one serial connection and one
busy-lock, so only one transaction is ever in flight at a time; buttons
disable themselves while a transaction is pending and re-enable on
completion. The shared **Last Result** panel (below the tabs) always shows a
detailed breakdown of the most recent transaction regardless of which tab
triggered it, and the **Log** panel keeps a full timestamped history
(clearable with the **Clear Log** button).

### Suggested workflow

1. Connect to the serial port (top bar).
2. Set up `QSPI_CFG0`: chip select, endianness, DDR/CRM, data direction, SCK
   mode, CMD/ADDR/DATA modes, dummy cycles, address length, and prescaler.
3. Set `QSPI_CMD` (opcode + mode byte), `QSPI_ADDR` (target address),
   `QSPI_DLEN` (data length), and `QSPI_TIMEOUT` as needed.
4. Press **Start QSPI** (Control tab) to pulse the `START` bit.
5. For writes, push data words to `QSPI_DR` (TX FIFO). For reads, pop from
   `QSPI_DR` (RX FIFO) as they arrive.
6. Poll CTRL status (`BUSY`/`DONE`) and check `QSPI_BCNT` for bytes
   transferred.
7. Clear `DONE`/`TIMEOUT`/`FIFO_ERR` flags on the Control tab before
   starting the next transaction.

## Known limitations / next steps

- No automatic retry on timeout or malformed response.
- `QSPI_TIMEOUT`'s unit (clock cycles, SCK cycles, etc.) isn't confirmed yet
  — the GUI treats it as a raw 32-bit value until that's specified.
- The ESP32-S3 test firmware only simulates `QSPI_CTRL` at address `0x00`
  with random/echoed data; it doesn't model the other 7 registers, so full
  end-to-end testing of `CFG0`/`CMD`/`ADDR`/`DLEN`/`DR`/`BCNT` still needs
  the real FPGA (or an expanded test firmware, if useful before then).
- No hardware flow control (RTS/CTS) configured — add if your board requires
  it.
