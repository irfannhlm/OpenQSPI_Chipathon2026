# UART FPGA Bridge GUI

A Python/Tkinter GUI for sending and receiving UART data (8N1) between a PC and
an FPGA implementing a QSPI-based register interface.

## Protocol

- PC sends 1 **ADDR** byte.
  - MSB = `1` -> **WRITE** mode
  - MSB = `0` -> **READ** mode
- **READ** mode: FPGA responds with 1 ACK byte, then 4 data bytes.
  Sequence: `ADDR, ACK, DATA, DATA, DATA, DATA`.
- **WRITE** mode: PC sends 4 data bytes, FPGA responds with 1 ACK byte.
  Sequence: `ADDR, DATA, DATA, DATA, DATA, ACK`.

**Byte order:** the 4 DATA bytes are transmitted **high byte first**
(big-endian) — i.e. for a 32-bit value, the first data byte on the wire is
the most significant byte and the last is the least significant. Both the
Python GUI and the ESP32 test firmware reconstruct/log the 32-bit value this
way (`int.from_bytes(data, byteorder="big")` in Python;
`(data[0]<<24)|(data[1]<<16)|(data[2]<<8)|data[3]` in firmware) so this can be
visually double-checked during testing.

UART settings: 8 data bits, No parity, 1 stop bit (8N1), baud rate configurable
in the GUI.

## Requirements

- Python 3.9+
- `pyserial` (see `requirements.txt`)

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

## Usage notes

- **Connect**: pick the serial port and baud rate, then click `Connect`.
  Use `Refresh` if your FPGA board isn't listed (e.g. plugged in after the
  GUI was opened).
- **Address**: enter as 7-bit hex (`00`-`7F`). The MSB (mode bit) is set
  automatically based on the selected Read/Write radio button — don't
  include it yourself.
- **Write data**: 4 bytes as an 8-character hex string (e.g. `DEADBEEF`).
- **Read mode**: displays the 4 returned bytes in both hex and binary.
- **Write mode**: displays the sent data and the returned ACK byte.
- The **Log** panel keeps a timestamped history of every transaction for
  debugging; **Last Result** shows a clean summary of the most recent one.

## Known limitations / next steps

- No automatic retry on timeout or malformed response.
- Binary display is raw per-byte for now; a payload parser (for interpreting
  the 4 bytes as specific fixed-point/struct formats) is planned.
- No hardware flow control (RTS/CTS) configured — add if your board requires
  it.
