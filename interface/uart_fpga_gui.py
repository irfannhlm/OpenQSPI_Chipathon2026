"""
UART FPGA Bridge GUI
=====================
Simple GUI for sending/receiving UART data (8N1) to/from an FPGA that implements
a QSPI-based register interface.

Protocol:
  - PC sends 1 ADDR byte.
      MSB = 1 -> WRITE mode
      MSB = 0 -> READ mode
  - READ mode:  FPGA responds with 4 data bytes.
  - WRITE mode: PC sends 4 data bytes, FPGA responds with 1 ACK byte.

Requires: pyserial  (pip install pyserial)
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import serial
import serial.tools.list_ports
import threading
import queue
import time

BAUD_RATES = [1200, 2400, 4800, 9600, 19200, 38400, 57600,
              115200, 230400, 460800, 921600]

# QSPI_CFG0 register (offset 0x04) bit layout
CFG0_ADDR = 0x04
CS_NUM = 4  # CSN_SEL field is 4 bits wide -> 4 chip-select lines
MODE_OPTIONS = ["None", "Single", "Dual", "Quad"]  # maps to 2'b00.."11"

# QSPI_CTRL register (offset 0x00) -- control / status
# RESERVED [31:10], FLUSH [9] WO pulse, FIFO_ERR [8:5] RO W1C, TIMEOUT [4] RO W1C,
# BUSY [3] RO, DONE [2] RO W1C, ABORT [1] WO pulse, START [0] WO pulse
CTRL_ADDR = 0x00
CTRL_START_BIT = 0
CTRL_ABORT_BIT = 1
CTRL_DONE_BIT = 2
CTRL_BUSY_BIT = 3
CTRL_TIMEOUT_BIT = 4
CTRL_FIFO_ERR_LSB = 5   # 4 bits: [8:5]
CTRL_FLUSH_BIT = 9

# Remaining registers
DLEN_ADDR = 0x08     # QSPI_DLEN -- DATA_LEN[31:0] RW
CMD_ADDR = 0x0C       # QSPI_CMD  -- MODE_BYTE[15:8] RW, CMD[7:0] RW
QADDR_ADDR = 0x10     # QSPI_ADDR -- ADDR[31:0] RW (target device address, distinct from the
                      # 7-bit UART protocol ADDR byte used to select this register)
DR_ADDR = 0x14        # QSPI_DR   -- TX/RX FIFO data word, direction gated by CFG0.DATA_DIR
BCNT_ADDR = 0x18      # QSPI_BCNT -- BYTE_CNT[31:0] RO
TIMEOUT_ADDR = 0x1C   # QSPI_TIMEOUT -- TIMEOUT_VAL[31:0] RW (units not yet confirmed)

# Shared UI styling -- keeps every register header, description, and result
# line looking identical across tabs instead of ad hoc per-tab formatting.
UI_FONT = ("Segoe UI", 9)
UI_FONT_BOLD = ("Segoe UI", 9, "bold")
MONO_FONT = ("Consolas", 9)
MONO_FONT_LG = ("Consolas", 10)  # slightly larger for the primary "Last Result" panel
MUTED_COLOR = "#5a5a5a"
RESULT_COLOR = "#0055aa"
ACCESS_COLORS = {
    "RW": "#0057b8",       # blue -- read/write
    "RO": "#6a3fb5",       # purple -- read-only
    "WO": "#b35c00",       # orange -- write-only
    "RW/RO": "#0057b8",    # mixed register (CTRL) -- treat like RW for the badge
}


class UartFpgaGui:
    def __init__(self, root):
        self.root = root
        root.title("UART FPGA Bridge (8N1)")
        root.geometry("760x900")

        self.ser = None
        self.busy = False
        self.result_queue = queue.Queue()

        self._build_ui()
        self.refresh_ports()
        self.root.after(100, self._poll_queue)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self):
        self._action_buttons = []  # buttons disabled together while a transaction is in flight

        conn_frame = ttk.LabelFrame(self.root, text="Serial Connection")
        conn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var,
                                        width=18, state="readonly")
        self.port_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(conn_frame, text="Refresh", command=self.refresh_ports).grid(
            row=0, column=2, padx=5, pady=5)

        ttk.Label(conn_frame, text="Baud:").grid(row=0, column=3, padx=5, pady=5, sticky="w")
        self.baud_var = tk.StringVar(value="115200")
        ttk.Combobox(conn_frame, textvariable=self.baud_var, width=10,
                     values=[str(b) for b in BAUD_RATES], state="readonly").grid(
            row=0, column=4, padx=5, pady=5)

        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self.toggle_connect)
        self.connect_btn.grid(row=0, column=5, padx=5, pady=5)

        self.status_var = tk.StringVar(value="Disconnected")
        self.status_lbl = ttk.Label(conn_frame, textvariable=self.status_var, foreground="red")
        self.status_lbl.grid(row=0, column=6, padx=10)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="x", padx=10, pady=5)

        guide_tab = ttk.Frame(notebook)
        raw_tab = ttk.Frame(notebook)
        cfg0_tab = ttk.Frame(notebook)
        ctrl_tab = ttk.Frame(notebook)
        setup_tab = ttk.Frame(notebook)
        fifo_tab = ttk.Frame(notebook)
        notebook.add(guide_tab, text="Guide")
        notebook.add(raw_tab, text="Raw Transaction")
        notebook.add(cfg0_tab, text="QSPI Config (CFG0)")
        notebook.add(ctrl_tab, text="Control (CTRL)")
        notebook.add(setup_tab, text="Transaction Setup")
        notebook.add(fifo_tab, text="FIFO & Status")

        self._build_guide_tab(guide_tab)
        self._build_raw_tab(raw_tab)
        self._build_cfg0_tab(cfg0_tab)
        self._build_ctrl_tab(ctrl_tab)
        self._build_setup_tab(setup_tab)
        self._build_fifo_tab(fifo_tab)

        result_frame = ttk.LabelFrame(self.root, text="Last Result")
        result_frame.pack(fill="x", padx=10, pady=5)
        self.result_var = tk.StringVar(value="-")
        ttk.Label(result_frame, textvariable=self.result_var, font=MONO_FONT_LG,
                  justify="left").pack(anchor="w", padx=5, pady=5)

        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        log_toolbar = ttk.Frame(log_frame)
        log_toolbar.pack(fill="x", padx=5, pady=(5, 0))
        ttk.Button(log_toolbar, text="Clear Log", command=self.clear_log).pack(side="right")

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, font=MONO_FONT)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

    # ------------------------------------------------------------- Guide ---
    def _build_guide_tab(self, parent):
        canvas = tk.Canvas(parent, height=480, borderwidth=0, highlightthickness=0)
        vscroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_configure(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _on_inner_configure)

        def _on_mousewheel(event):
            delta = -1 * (event.delta // 120) if event.delta else (1 if event.num == 5 else -1)
            canvas.yview_scroll(int(delta), "units")
        def _bind_wheel(_e):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel)
            canvas.bind_all("<Button-5>", _on_mousewheel)
        def _unbind_wheel(_e):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")
        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)

        row = [0]  # mutable counter shared by helpers below

        def title(text, size=12):
            ttk.Label(inner, text=text, font=(UI_FONT[0], size, "bold")).grid(
                row=row[0], column=0, sticky="w", padx=10, pady=(14, 4))
            row[0] += 1

        def body(text):
            ttk.Label(inner, text=text, font=UI_FONT, wraplength=700, justify="left").grid(
                row=row[0], column=0, sticky="w", padx=20, pady=(0, 4))
            row[0] += 1

        def bullet(text):
            ttk.Label(inner, text=f"\u2022 {text}", font=UI_FONT, wraplength=680,
                      justify="left").grid(row=row[0], column=0, sticky="w", padx=25, pady=1)
            row[0] += 1

        def table(columns, col_widths, rows_data):
            tree = ttk.Treeview(inner, columns=columns, show="headings",
                                 height=len(rows_data))
            for i, col in enumerate(columns):
                tree.heading(col, text=col)
                tree.column(col, width=col_widths[i], anchor="w", stretch=False)
            for r in rows_data:
                tree.insert("", "end", values=r)
            tree.grid(row=row[0], column=0, sticky="w", padx=20, pady=(0, 8))
            row[0] += 1

        # ---- Overview ----
        title("QSPI Master -- Reference Guide", size=13)
        body("Reference for qspi_master.sv, mirroring the module README. Covers the UART "
             "framing this GUI uses to talk to the FPGA, the register map, and per-register "
             "bit layouts.")

        title("Features")
        for f in [
            "Full support of all single, dual, and quad modes",
            "Configurable address (3/4 bytes) and data lengths",
            "Adjustable SCK prescaler (minimum 2) and SCK modes (mode 0/mode 3)",
            "32-bit FIFO interface with SCK pause ability when empty/full",
            "Multiple Chip Selects (CSn) pins",
            "Little Endian and Big Endian support",
            "Mode byte (M[7:0]) support for eXecute In Place (XIP) operations",
            "Dual Data Rate (DDR) support",
        ]:
            bullet(f)

        # ---- UART framing ----
        title("UART Frame Protocol (8N1)")
        body("ADDR byte MSB selects the mode: 1 = WRITE, 0 = READ. The 7 low bits select the "
             "register offset. All multi-byte DATA fields are sent high byte first (big-endian).")
        table(
            ["Mode", "Byte Sequence"],
            [90, 420],
            [
                ("Read", "ADDR, ACK, DATA, DATA, DATA, DATA"),
                ("Write", "ADDR, DATA, DATA, DATA, DATA, ACK"),
            ],
        )

        # ---- Register map ----
        title("Register Map")
        table(
            ["Offset", "Register", "Access", "Description"],
            [70, 110, 70, 400],
            [
                (f"0x{CTRL_ADDR:02X}", "QSPI_CTRL", "RW/RO", "Control / status (see bit table below)"),
                (f"0x{CFG0_ADDR:02X}", "QSPI_CFG0", "RW", "Config, packed (see bit table below)"),
                (f"0x{DLEN_ADDR:02X}", "QSPI_DLEN", "RW", "Data length in bytes -> qspi_data_len_i"),
                (f"0x{CMD_ADDR:02X}", "QSPI_CMD", "RW", "Command opcode + XIP mode byte (see bit table below)"),
                (f"0x{QADDR_ADDR:02X}", "QSPI_ADDR", "RW", "Target device address -> qspi_addr_i"),
                (f"0x{DR_ADDR:02X}", "QSPI_DR", "RW", "TX/RX FIFO data word (direction-gated by CFG0.DATA_DIR)"),
                (f"0x{BCNT_ADDR:02X}", "QSPI_BCNT", "RO", "Bytes transferred so far -> qspi_byte_cnt_o"),
                (f"0x{TIMEOUT_ADDR:02X}", "QSPI_TIMEOUT", "RW", "Timeout value -> qspi_timeout_i (units TBD)"),
            ],
        )

        # ---- QSPI_CTRL bits ----
        title(f"QSPI_CTRL (0x{CTRL_ADDR:02X}) Bit Fields")
        table(
            ["Bits", "Field", "Access", "Description"],
            [70, 90, 90, 400],
            [
                ("[31:10]", "RESERVED", "-", "-"),
                ("[9]", "FLUSH", "WO pulse", "Flush FIFO"),
                ("[8:5]", "FIFO_ERR", "RO, W1C", "FIFO error flags"),
                ("[4]", "TIMEOUT", "RO, W1C", "Timeout occurred -> qspi_timeout_o"),
                ("[3]", "BUSY", "RO", "Transaction in progress"),
                ("[2]", "DONE", "RO, W1C", "Transaction complete"),
                ("[1]", "ABORT", "WO pulse", "Abort current transaction"),
                ("[0]", "START", "WO pulse", "Start transaction"),
            ],
        )

        # ---- QSPI_CFG0 bits ----
        title(f"QSPI_CFG0 (0x{CFG0_ADDR:02X}) Bit Fields")
        table(
            ["Bits", "Field", "Access", "Description"],
            [70, 90, 60, 430],
            [
                ("[31:30]", "RESERVED", "-", "-"),
                ("[29:26]", "CSN_SEL", "RW", "Chip-select lines to activate, active HIGH, one bit per CS"),
                ("[25]", "ENDIAN", "RW", "0 = Big Endian, 1 = Little Endian"),
                ("[24]", "DDR", "RW", "Dual Data Rate enable"),
                ("[23]", "CRM", "RW", "Continuous Read Mode enable"),
                ("[22]", "DATA_DIR", "RW", "0 = Read, 1 = Write"),
                ("[21]", "SCK_MODE", "RW", "0 = Mode 0, 1 = Mode 3"),
                ("[20:19]", "DATA_MODE", "RW", "00=None, 01=Single, 10=Dual, 11=Quad"),
                ("[18:17]", "ADDR_MODE", "RW", "Same encoding as DATA_MODE"),
                ("[16:15]", "CMD_MODE", "RW", "Same encoding as DATA_MODE"),
                ("[14:9]", "DUMMY_LEN", "RW", "Dummy cycles, 0-63"),
                ("[8]", "ADDR_LEN", "RW", "0 = 3-byte addressing, 1 = 4-byte addressing"),
                ("[7:0]", "PRESCALER", "RW", "SCK freq = fclk / (prescaler*2+2), min 2"),
            ],
        )

        # ---- QSPI_CMD bits ----
        title(f"QSPI_CMD (0x{CMD_ADDR:02X}) Bit Fields")
        table(
            ["Bits", "Field", "Access", "Description"],
            [70, 90, 90, 400],
            [
                ("[31:16]", "RESERVED", "-", "-"),
                ("[15:8]", "MODE_BYTE", "RW", "XIP mode byte -> qspi_mode_byte_i"),
                ("[7:0]", "CMD", "RW", "Command opcode -> qspi_cmd_i"),
            ],
        )

        # ---- Suggested workflow ----
        title("Suggested Workflow")
        for step in [
            "Connect to the serial port (top bar).",
            "Set up QSPI_CFG0: chip select, endianness, DDR/CRM, data direction, SCK mode, "
            "CMD/ADDR/DATA modes, dummy cycles, address length, and prescaler.",
            "Set QSPI_CMD (opcode + mode byte), QSPI_ADDR (target address), QSPI_DLEN (data "
            "length), and QSPI_TIMEOUT as needed for the transaction.",
            "Press Start QSPI (CTRL tab) to pulse the START bit.",
            "For writes, push data words to QSPI_DR (TX FIFO). For reads, pop from QSPI_DR "
            "(RX FIFO) as they arrive.",
            "Poll CTRL status (BUSY / DONE) and check QSPI_BCNT for bytes transferred.",
            "Clear DONE / TIMEOUT / FIFO_ERR flags on the CTRL tab before starting the next "
            "transaction.",
        ]:
            bullet(step)

        ttk.Label(inner, text="").grid(row=row[0], column=0, pady=10)  # bottom padding

    def _build_raw_tab(self, trans_frame):
        ttk.Label(trans_frame, text="Mode:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.mode_var = tk.StringVar(value="read")
        ttk.Radiobutton(trans_frame, text="Read  (ADDR MSB = 0)", variable=self.mode_var,
                        value="read", command=self._on_mode_change).grid(
            row=0, column=1, padx=5, sticky="w")
        ttk.Radiobutton(trans_frame, text="Write (ADDR MSB = 1)", variable=self.mode_var,
                        value="write", command=self._on_mode_change).grid(
            row=0, column=2, padx=5, sticky="w")

        ttk.Label(trans_frame, text="Address (hex, 00-7F, 7-bit):").grid(
            row=1, column=0, padx=5, pady=5, sticky="w")
        self.addr_var = tk.StringVar(value="00")
        ttk.Entry(trans_frame, textvariable=self.addr_var, width=10).grid(
            row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(trans_frame, text="Write data (hex, 4 bytes, e.g. DEADBEEF):").grid(
            row=2, column=0, padx=5, pady=5, sticky="w")
        self.wdata_var = tk.StringVar(value="00000000")
        self.wdata_entry = ttk.Entry(trans_frame, textvariable=self.wdata_var, width=20)
        self.wdata_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="w")

        self.send_btn = ttk.Button(trans_frame, text="Send", command=self.send_transaction)
        self.send_btn.grid(row=3, column=0, padx=5, pady=10, sticky="w")
        self._action_buttons.append(self.send_btn)

        self._on_mode_change()

    def clear_log(self):
        self.log_text.delete("1.0", "end")

    def _on_mode_change(self):
        if self.mode_var.get() == "write":
            self.wdata_entry.configure(state="normal")
        else:
            self.wdata_entry.configure(state="disabled")

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for btn in self._action_buttons:
            btn.configure(state=state)

    def _reg_frame(self, parent, addr, name, access, desc):
        """Build a LabelFrame with a consistent register header: title is
        'NAME (0xOFFSET)', with a colored access badge (RW/RO/WO) and a
        muted one-line description underneath. Returns the frame; caller
        adds further widgets starting at row=1 (row=0 is the header)."""
        frame = ttk.LabelFrame(parent, text=f"{name}  (0x{addr:02X})")
        frame.pack(fill="x", padx=10, pady=(0, 10))

        header = ttk.Frame(frame)
        header.grid(row=0, column=0, columnspan=10, sticky="w", padx=8, pady=(6, 4))
        ttk.Label(header, text=access, font=UI_FONT_BOLD,
                  foreground=ACCESS_COLORS.get(access, MUTED_COLOR)).pack(side="left")
        ttk.Label(header, text=f"   {desc}", font=UI_FONT, foreground=MUTED_COLOR,
                  wraplength=600, justify="left").pack(side="left")
        return frame

    def _reg_result_vars(self):
        return {
            "dlen": self.dlen_result_var,
            "cmd": self.cmd_result_var,
            "qaddr": self.qaddr_result_var,
            "timeout": self.timeout_result_var,
            "dr": self.dr_result_var,
            "bcnt": self.bcnt_result_var,
        }

    # ------------------------------------------------------- QSPI_CFG0 UI ---
    def _build_cfg0_tab(self, parent):
        frame = self._reg_frame(
            parent, CFG0_ADDR, "QSPI_CFG0", "RW",
            "Config register, packed 32-bit \u2014 sets chip select, endianness, DDR/CRM, "
            "data direction, SCK mode, CMD/ADDR/DATA modes, dummy cycles, address length, "
            "and prescaler.",
        )

        row = 1

        # CSN_SEL [29:26]
        ttk.Label(frame, text="CSN_SEL [29:26]", font=UI_FONT).grid(
            row=row, column=0, padx=8, pady=4, sticky="w")
        csn_frame = ttk.Frame(frame)
        csn_frame.grid(row=row, column=1, columnspan=3, padx=8, pady=4, sticky="w")
        self.csn_vars = [tk.BooleanVar(value=False) for _ in range(CS_NUM)]
        for i, var in enumerate(self.csn_vars):
            ttk.Checkbutton(csn_frame, text=f"CS{i}", variable=var,
                             command=self._update_cfg0_preview).pack(side="left", padx=(0, 8))
        row += 1

        # ENDIAN [25]
        ttk.Label(frame, text="ENDIAN [25]", font=UI_FONT).grid(
            row=row, column=0, padx=8, pady=4, sticky="w")
        self.endian_var = tk.IntVar(value=0)
        endian_frame = ttk.Frame(frame)
        endian_frame.grid(row=row, column=1, columnspan=3, padx=8, pady=4, sticky="w")
        ttk.Radiobutton(endian_frame, text="Big Endian (0)", variable=self.endian_var, value=0,
                         command=self._update_cfg0_preview).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(endian_frame, text="Little Endian (1)", variable=self.endian_var, value=1,
                         command=self._update_cfg0_preview).pack(side="left")
        row += 1

        # DDR [24]
        ttk.Label(frame, text="DDR [24]", font=UI_FONT).grid(
            row=row, column=0, padx=8, pady=4, sticky="w")
        self.ddr_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Enable DDR", variable=self.ddr_var,
                         command=self._update_cfg0_preview).grid(
            row=row, column=1, padx=8, pady=4, sticky="w")
        row += 1

        # CRM [23]
        ttk.Label(frame, text="CRM [23]", font=UI_FONT).grid(
            row=row, column=0, padx=8, pady=4, sticky="w")
        self.crm_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Enable Continuous Read Mode", variable=self.crm_var,
                         command=self._update_cfg0_preview).grid(
            row=row, column=1, padx=8, pady=4, sticky="w")
        row += 1

        # DATA_DIR [22]
        ttk.Label(frame, text="DATA_DIR [22]", font=UI_FONT).grid(
            row=row, column=0, padx=8, pady=4, sticky="w")
        self.data_dir_var = tk.IntVar(value=0)
        dir_frame = ttk.Frame(frame)
        dir_frame.grid(row=row, column=1, columnspan=3, padx=8, pady=4, sticky="w")
        ttk.Radiobutton(dir_frame, text="Read (0)", variable=self.data_dir_var, value=0,
                         command=self._update_cfg0_preview).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(dir_frame, text="Write (1)", variable=self.data_dir_var, value=1,
                         command=self._update_cfg0_preview).pack(side="left")
        row += 1

        # SCK_MODE [21]
        ttk.Label(frame, text="SCK_MODE [21]", font=UI_FONT).grid(
            row=row, column=0, padx=8, pady=4, sticky="w")
        self.sck_mode_var = tk.IntVar(value=0)
        sck_frame = ttk.Frame(frame)
        sck_frame.grid(row=row, column=1, columnspan=3, padx=8, pady=4, sticky="w")
        ttk.Radiobutton(sck_frame, text="Mode 0", variable=self.sck_mode_var, value=0,
                         command=self._update_cfg0_preview).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(sck_frame, text="Mode 3", variable=self.sck_mode_var, value=1,
                         command=self._update_cfg0_preview).pack(side="left")
        row += 1

        # DATA_MODE [20:19]
        ttk.Label(frame, text="DATA_MODE [20:19]", font=UI_FONT).grid(
            row=row, column=0, padx=8, pady=4, sticky="w")
        self.data_mode_var = tk.StringVar(value=MODE_OPTIONS[1])
        ttk.Combobox(frame, textvariable=self.data_mode_var, values=MODE_OPTIONS,
                     state="readonly", width=10).grid(row=row, column=1, padx=8, pady=4, sticky="w")
        self.data_mode_var.trace_add("write", self._update_cfg0_preview)
        row += 1

        # ADDR_MODE [18:17]
        ttk.Label(frame, text="ADDR_MODE [18:17]", font=UI_FONT).grid(
            row=row, column=0, padx=8, pady=4, sticky="w")
        self.addr_mode_var = tk.StringVar(value=MODE_OPTIONS[1])
        ttk.Combobox(frame, textvariable=self.addr_mode_var, values=MODE_OPTIONS,
                     state="readonly", width=10).grid(row=row, column=1, padx=8, pady=4, sticky="w")
        self.addr_mode_var.trace_add("write", self._update_cfg0_preview)
        row += 1

        # CMD_MODE [16:15]
        ttk.Label(frame, text="CMD_MODE [16:15]", font=UI_FONT).grid(
            row=row, column=0, padx=8, pady=4, sticky="w")
        self.cmd_mode_var = tk.StringVar(value=MODE_OPTIONS[1])
        ttk.Combobox(frame, textvariable=self.cmd_mode_var, values=MODE_OPTIONS,
                     state="readonly", width=10).grid(row=row, column=1, padx=8, pady=4, sticky="w")
        self.cmd_mode_var.trace_add("write", self._update_cfg0_preview)
        row += 1

        # DUMMY_LEN [14:9]
        ttk.Label(frame, text="DUMMY_LEN [14:9]", font=UI_FONT).grid(
            row=row, column=0, padx=8, pady=4, sticky="w")
        self.dummy_len_var = tk.IntVar(value=0)
        ttk.Spinbox(frame, from_=0, to=63, textvariable=self.dummy_len_var, width=8,
                    command=self._update_cfg0_preview).grid(
            row=row, column=1, padx=8, pady=4, sticky="w")
        ttk.Label(frame, text="cycles (0-63)", font=UI_FONT, foreground=MUTED_COLOR).grid(
            row=row, column=2, padx=0, pady=4, sticky="w")
        row += 1

        # ADDR_LEN [8]
        ttk.Label(frame, text="ADDR_LEN [8]", font=UI_FONT).grid(
            row=row, column=0, padx=8, pady=4, sticky="w")
        self.addr_len_var = tk.IntVar(value=0)
        alen_frame = ttk.Frame(frame)
        alen_frame.grid(row=row, column=1, columnspan=3, padx=8, pady=4, sticky="w")
        ttk.Radiobutton(alen_frame, text="3-byte (0)", variable=self.addr_len_var, value=0,
                         command=self._update_cfg0_preview).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(alen_frame, text="4-byte (1)", variable=self.addr_len_var, value=1,
                         command=self._update_cfg0_preview).pack(side="left")
        row += 1

        # PRESCALER [7:0]
        ttk.Label(frame, text="PRESCALER [7:0]", font=UI_FONT).grid(
            row=row, column=0, padx=8, pady=4, sticky="w")
        self.prescaler_var = tk.IntVar(value=2)
        ttk.Spinbox(frame, from_=0, to=255, textvariable=self.prescaler_var, width=8,
                    command=self._update_cfg0_preview).grid(
            row=row, column=1, padx=8, pady=4, sticky="w")
        ttk.Label(frame, text="min 2 -- SCK = fclk / (prescaler*2+2)", font=UI_FONT,
                  foreground=MUTED_COLOR).grid(row=row, column=2, columnspan=2, padx=0, pady=4, sticky="w")
        row += 1

        # Optional FPGA clock, for live SCK frequency preview only
        ttk.Label(frame, text="FPGA Clock (Hz, optional)", font=UI_FONT).grid(
            row=row, column=0, padx=8, pady=4, sticky="w")
        self.fclk_var = tk.StringVar(value="")
        fclk_entry = ttk.Entry(frame, textvariable=self.fclk_var, width=14)
        fclk_entry.grid(row=row, column=1, padx=8, pady=4, sticky="w")
        ttk.Label(frame, text="used only to preview SCK freq below", font=UI_FONT,
                  foreground=MUTED_COLOR).grid(row=row, column=2, columnspan=2, padx=0, pady=4, sticky="w")
        self.fclk_var.trace_add("write", self._update_cfg0_preview)
        row += 1

        # Live packed-value preview
        self.cfg0_preview_var = tk.StringVar(value="-")
        ttk.Label(frame, textvariable=self.cfg0_preview_var, font=MONO_FONT,
                  foreground=RESULT_COLOR, justify="left", wraplength=680).grid(
            row=row, column=0, columnspan=4, padx=8, pady=(6, 4), sticky="w")
        row += 1

        # Action buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row, column=0, columnspan=4, padx=8, pady=10, sticky="w")
        self.cfg0_write_btn = ttk.Button(btn_frame, text="Write Config to FPGA",
                                          command=self.write_cfg0)
        self.cfg0_write_btn.pack(side="left", padx=(0, 8))
        self.cfg0_read_btn = ttk.Button(btn_frame, text="Read Config from FPGA",
                                         command=self.read_cfg0)
        self.cfg0_read_btn.pack(side="left")
        self._action_buttons.extend([self.cfg0_write_btn, self.cfg0_read_btn])

        self._update_cfg0_preview()

    def _pack_cfg0(self):
        """Pack current CFG0 tab widget values into a 32-bit register value.
        Returns (value, error_message). error_message is None on success."""
        try:
            csn = 0
            for i, var in enumerate(self.csn_vars):
                if var.get():
                    csn |= (1 << i)
            endian = self.endian_var.get()
            ddr = 1 if self.ddr_var.get() else 0
            crm = 1 if self.crm_var.get() else 0
            data_dir = self.data_dir_var.get()
            sck_mode = self.sck_mode_var.get()
            data_mode = MODE_OPTIONS.index(self.data_mode_var.get())
            addr_mode = MODE_OPTIONS.index(self.addr_mode_var.get())
            cmd_mode = MODE_OPTIONS.index(self.cmd_mode_var.get())
            dummy_len = int(self.dummy_len_var.get())
            addr_len = self.addr_len_var.get()
            prescaler = int(self.prescaler_var.get())
        except (tk.TclError, ValueError):
            return None, "one or more fields have an invalid/empty value."

        if not (0 <= dummy_len <= 63):
            return None, "DUMMY_LEN must be 0-63."
        if not (0 <= prescaler <= 255):
            return None, "PRESCALER must be 0-255."

        value = 0
        value |= (csn & 0xF) << 26
        value |= (endian & 0x1) << 25
        value |= (ddr & 0x1) << 24
        value |= (crm & 0x1) << 23
        value |= (data_dir & 0x1) << 22
        value |= (sck_mode & 0x1) << 21
        value |= (data_mode & 0x3) << 19
        value |= (addr_mode & 0x3) << 17
        value |= (cmd_mode & 0x3) << 15
        value |= (dummy_len & 0x3F) << 9
        value |= (addr_len & 0x1) << 8
        value |= (prescaler & 0xFF)
        return value, None

    def _unpack_cfg0(self, value):
        """Apply a 32-bit CFG0 register value to the tab's widgets."""
        csn = (value >> 26) & 0xF
        endian = (value >> 25) & 0x1
        ddr = (value >> 24) & 0x1
        crm = (value >> 23) & 0x1
        data_dir = (value >> 22) & 0x1
        sck_mode = (value >> 21) & 0x1
        data_mode = (value >> 19) & 0x3
        addr_mode = (value >> 17) & 0x3
        cmd_mode = (value >> 15) & 0x3
        dummy_len = (value >> 9) & 0x3F
        addr_len = (value >> 8) & 0x1
        prescaler = value & 0xFF

        for i, var in enumerate(self.csn_vars):
            var.set(bool(csn & (1 << i)))
        self.endian_var.set(endian)
        self.ddr_var.set(bool(ddr))
        self.crm_var.set(bool(crm))
        self.data_dir_var.set(data_dir)
        self.sck_mode_var.set(sck_mode)
        self.data_mode_var.set(MODE_OPTIONS[data_mode])
        self.addr_mode_var.set(MODE_OPTIONS[addr_mode])
        self.cmd_mode_var.set(MODE_OPTIONS[cmd_mode])
        self.dummy_len_var.set(dummy_len)
        self.addr_len_var.set(addr_len)
        self.prescaler_var.set(prescaler)
        self._update_cfg0_preview()

    @staticmethod
    def _describe_cfg0(value):
        """Human-readable per-field breakdown of a packed CFG0 value."""
        csn = (value >> 26) & 0xF
        endian = (value >> 25) & 0x1
        ddr = (value >> 24) & 0x1
        crm = (value >> 23) & 0x1
        data_dir = (value >> 22) & 0x1
        sck_mode = (value >> 21) & 0x1
        data_mode = (value >> 19) & 0x3
        addr_mode = (value >> 17) & 0x3
        cmd_mode = (value >> 15) & 0x3
        dummy_len = (value >> 9) & 0x3F
        addr_len = (value >> 8) & 0x1
        prescaler = value & 0xFF

        active_cs = ", ".join(f"CS{i}" for i in range(CS_NUM) if csn & (1 << i)) or "none"

        return (
            f"CSN_SEL   [29:26] = {csn:04b}  (active: {active_cs})\n"
            f"ENDIAN    [25]    = {endian}  ({'Little' if endian else 'Big'} Endian)\n"
            f"DDR       [24]    = {ddr}  ({'Enabled' if ddr else 'Disabled'})\n"
            f"CRM       [23]    = {crm}  ({'Enabled' if crm else 'Disabled'})\n"
            f"DATA_DIR  [22]    = {data_dir}  ({'Write' if data_dir else 'Read'})\n"
            f"SCK_MODE  [21]    = {sck_mode}  (Mode {3 if sck_mode else 0})\n"
            f"DATA_MODE [20:19] = {data_mode:02b}  ({MODE_OPTIONS[data_mode]})\n"
            f"ADDR_MODE [18:17] = {addr_mode:02b}  ({MODE_OPTIONS[addr_mode]})\n"
            f"CMD_MODE  [16:15] = {cmd_mode:02b}  ({MODE_OPTIONS[cmd_mode]})\n"
            f"DUMMY_LEN [14:9]  = {dummy_len} cycles\n"
            f"ADDR_LEN  [8]     = {addr_len}  ({'4-byte' if addr_len else '3-byte'} addressing)\n"
            f"PRESCALER [7:0]   = {prescaler}"
        )

    @staticmethod
    def _format_freq(hz):
        if hz >= 1e6:
            return f"{hz / 1e6:.3f} MHz"
        if hz >= 1e3:
            return f"{hz / 1e3:.3f} kHz"
        return f"{hz:.1f} Hz"

    def _update_cfg0_preview(self, *_args):
        value, err = self._pack_cfg0()
        if err:
            self.cfg0_preview_var.set(f"Invalid config: {err}")
            return

        freq_note = ""
        fclk_raw = self.fclk_var.get().strip()
        if fclk_raw:
            try:
                fclk = float(fclk_raw)
                prescaler = value & 0xFF
                sck_freq = fclk / (prescaler * 2 + 2)
                freq_note = f"  |  SCK freq \u2248 {self._format_freq(sck_freq)}"
            except (ValueError, ZeroDivisionError):
                freq_note = "  |  SCK freq: invalid clock value"

        self.cfg0_preview_var.set(f"Packed CFG0: 0x{value:08X}  ({value:032b}){freq_note}")

    def write_cfg0(self):
        if self.busy:
            return
        if not (self.ser and self.ser.is_open):
            self._log("ERROR: not connected.")
            return
        value, err = self._pack_cfg0()
        if err:
            self._log(f"ERROR: {err}")
            return

        wdata = value.to_bytes(4, byteorder="big")
        addr_byte = CFG0_ADDR | 0x80
        self._set_busy(True)
        threading.Thread(target=self._do_write, args=(addr_byte, wdata, "cfg0"),
                          daemon=True).start()

    def read_cfg0(self):
        if self.busy:
            return
        if not (self.ser and self.ser.is_open):
            self._log("ERROR: not connected.")
            return

        addr_byte = CFG0_ADDR & 0x7F
        self._set_busy(True)
        threading.Thread(target=self._do_read, args=(addr_byte, "cfg0"), daemon=True).start()

    # ------------------------------------------------------- QSPI_CTRL UI ---
    def _build_ctrl_tab(self, parent):
        frame = self._reg_frame(
            parent, CTRL_ADDR, "QSPI_CTRL", "RW/RO",
            "Control / status register. START [0], ABORT [1], FLUSH [9] are write-only "
            "pulse bits. BUSY [3] is read-only. DONE [2], TIMEOUT [4], FIFO_ERR [8:5] are "
            "read-only, write-1-to-clear (W1C).",
        )

        pulse_frame = ttk.LabelFrame(frame, text="Pulse commands (write-only)")
        pulse_frame.grid(row=1, column=0, columnspan=3, padx=8, pady=(4, 5), sticky="w")

        self.ctrl_start_btn = ttk.Button(pulse_frame, text="Start QSPI  (bit 0)",
                                          command=self.start_qspi)
        self.ctrl_start_btn.pack(side="left", padx=5, pady=8)

        self.ctrl_abort_btn = ttk.Button(pulse_frame, text="Abort QSPI  (bit 1)",
                                          command=self.abort_qspi)
        self.ctrl_abort_btn.pack(side="left", padx=5, pady=8)

        self.ctrl_flush_btn = ttk.Button(pulse_frame, text="Flush FIFO  (bit 9)",
                                          command=self.flush_fifo)
        self.ctrl_flush_btn.pack(side="left", padx=5, pady=8)

        self._action_buttons.extend([self.ctrl_start_btn, self.ctrl_abort_btn, self.ctrl_flush_btn])

        status_frame = ttk.LabelFrame(frame, text="Status (read-only)")
        status_frame.grid(row=2, column=0, columnspan=3, padx=8, pady=(0, 10), sticky="w")

        self.ctrl_read_btn = ttk.Button(status_frame, text="Read Status",
                                         command=self.read_ctrl)
        self.ctrl_read_btn.grid(row=0, column=0, padx=5, pady=8, sticky="w")

        self.ctrl_clear_btn = ttk.Button(status_frame, text="Clear DONE / TIMEOUT / FIFO_ERR",
                                          command=self.clear_ctrl_flags)
        self.ctrl_clear_btn.grid(row=0, column=1, padx=5, pady=8, sticky="w")

        self._action_buttons.extend([self.ctrl_read_btn, self.ctrl_clear_btn])

        self.ctrl_status_var = tk.StringVar(value="(no status read yet)")
        ttk.Label(status_frame, textvariable=self.ctrl_status_var, font=MONO_FONT,
                  foreground=RESULT_COLOR, justify="left", wraplength=680).grid(
            row=1, column=0, columnspan=3, padx=5, pady=(0, 8), sticky="w")

    @staticmethod
    def _describe_ctrl_status(value):
        fifo_err = (value >> CTRL_FIFO_ERR_LSB) & 0xF
        timeout = (value >> CTRL_TIMEOUT_BIT) & 0x1
        busy = (value >> CTRL_BUSY_BIT) & 0x1
        done = (value >> CTRL_DONE_BIT) & 0x1
        return (
            f"BUSY     [3]   = {busy}  ({'Busy' if busy else 'Idle'})\n"
            f"DONE     [2]   = {done}  ({'Complete (needs clearing)' if done else 'Not done'})\n"
            f"TIMEOUT  [4]   = {timeout}  ({'Timeout occurred (needs clearing)' if timeout else 'No timeout'})\n"
            f"FIFO_ERR [8:5] = {fifo_err:04b}  "
            f"({'Error flag(s) set (needs clearing)' if fifo_err else 'No FIFO errors'})"
        )

    def _send_ctrl_pulse(self, bit, tag):
        if self.busy:
            return
        if not (self.ser and self.ser.is_open):
            self._log("ERROR: not connected.")
            return

        value = 1 << bit
        wdata = value.to_bytes(4, byteorder="big")
        addr_byte = CTRL_ADDR | 0x80
        self._set_busy(True)
        threading.Thread(target=self._do_write, args=(addr_byte, wdata, tag), daemon=True).start()

    def start_qspi(self):
        self._send_ctrl_pulse(CTRL_START_BIT, "ctrl_start")

    def abort_qspi(self):
        self._send_ctrl_pulse(CTRL_ABORT_BIT, "ctrl_abort")

    def flush_fifo(self):
        self._send_ctrl_pulse(CTRL_FLUSH_BIT, "ctrl_flush")

    def clear_ctrl_flags(self):
        # W1C bits: DONE [2], TIMEOUT [4], FIFO_ERR [8:5] -- write 1 to each to clear all at once
        value = (1 << CTRL_DONE_BIT) | (1 << CTRL_TIMEOUT_BIT) | (0xF << CTRL_FIFO_ERR_LSB)
        if self.busy:
            return
        if not (self.ser and self.ser.is_open):
            self._log("ERROR: not connected.")
            return
        wdata = value.to_bytes(4, byteorder="big")
        addr_byte = CTRL_ADDR | 0x80
        self._set_busy(True)
        threading.Thread(target=self._do_write, args=(addr_byte, wdata, "ctrl_clear"),
                          daemon=True).start()

    def read_ctrl(self):
        if self.busy:
            return
        if not (self.ser and self.ser.is_open):
            self._log("ERROR: not connected.")
            return

        addr_byte = CTRL_ADDR & 0x7F
        self._set_busy(True)
        threading.Thread(target=self._do_read, args=(addr_byte, "ctrl"), daemon=True).start()

    # ---------------------------------------------------- Generic 32-bit reg ---
    def _parse_hex32(self, raw, field_name):
        raw = raw.strip()
        try:
            val = int(raw, 16)
        except ValueError:
            self._log(f"ERROR: {field_name} must be valid hex.")
            return None
        if not (0 <= val <= 0xFFFFFFFF):
            self._log(f"ERROR: {field_name} must fit in 32 bits.")
            return None
        return val

    def _parse_hex8(self, raw, field_name):
        raw = raw.strip()
        try:
            val = int(raw, 16)
        except ValueError:
            self._log(f"ERROR: {field_name} must be valid hex.")
            return None
        if not (0 <= val <= 0xFF):
            self._log(f"ERROR: {field_name} must fit in 1 byte (00-FF).")
            return None
        return val

    def _write_reg32(self, addr, value, tag):
        if self.busy:
            return
        if not (self.ser and self.ser.is_open):
            self._log("ERROR: not connected.")
            return
        wdata = value.to_bytes(4, byteorder="big")
        addr_byte = addr | 0x80
        self._set_busy(True)
        threading.Thread(target=self._do_write, args=(addr_byte, wdata, tag), daemon=True).start()

    def _read_reg32(self, addr, tag):
        if self.busy:
            return
        if not (self.ser and self.ser.is_open):
            self._log("ERROR: not connected.")
            return
        addr_byte = addr & 0x7F
        self._set_busy(True)
        threading.Thread(target=self._do_read, args=(addr_byte, tag), daemon=True).start()

    # ------------------------------------------------------ Transaction Setup ---
    def _build_setup_tab(self, parent):
        dlen_frame = self._reg_frame(
            parent, DLEN_ADDR, "QSPI_DLEN", "RW",
            "Number of data bytes for the transaction \u2192 qspi_data_len_i.")
        ttk.Label(dlen_frame, text="Data length in bytes (hex):", font=UI_FONT).grid(
            row=1, column=0, padx=8, pady=5, sticky="w")
        self.dlen_var = tk.StringVar(value="00000000")
        ttk.Entry(dlen_frame, textvariable=self.dlen_var, width=12).grid(
            row=1, column=1, padx=8, pady=5, sticky="w")
        dlen_write_btn = ttk.Button(dlen_frame, text="Write", command=self.write_dlen)
        dlen_write_btn.grid(row=1, column=2, padx=5, pady=5)
        dlen_read_btn = ttk.Button(dlen_frame, text="Read", command=self.read_dlen)
        dlen_read_btn.grid(row=1, column=3, padx=5, pady=5)
        self.dlen_result_var = tk.StringVar(value="-")
        ttk.Label(dlen_frame, textvariable=self.dlen_result_var, font=MONO_FONT,
                  foreground=RESULT_COLOR).grid(row=2, column=0, columnspan=4, padx=8, pady=(0, 8), sticky="w")

        cmd_frame = self._reg_frame(
            parent, CMD_ADDR, "QSPI_CMD", "RW",
            "Command opcode plus XIP mode byte, packed into one register.")
        ttk.Label(cmd_frame, text="CMD opcode (hex byte):", font=UI_FONT).grid(
            row=1, column=0, padx=8, pady=5, sticky="w")
        self.cmd_byte_var = tk.StringVar(value="00")
        ttk.Entry(cmd_frame, textvariable=self.cmd_byte_var, width=6).grid(
            row=1, column=1, padx=8, pady=5, sticky="w")
        ttk.Label(cmd_frame, text="MODE_BYTE / XIP (hex byte):", font=UI_FONT).grid(
            row=1, column=2, padx=8, pady=5, sticky="w")
        self.mode_byte_var = tk.StringVar(value="00")
        ttk.Entry(cmd_frame, textvariable=self.mode_byte_var, width=6).grid(
            row=1, column=3, padx=8, pady=5, sticky="w")
        cmd_write_btn = ttk.Button(cmd_frame, text="Write", command=self.write_cmd)
        cmd_write_btn.grid(row=1, column=4, padx=5, pady=5)
        cmd_read_btn = ttk.Button(cmd_frame, text="Read", command=self.read_cmd)
        cmd_read_btn.grid(row=1, column=5, padx=5, pady=5)
        self.cmd_result_var = tk.StringVar(value="-")
        ttk.Label(cmd_frame, textvariable=self.cmd_result_var, font=MONO_FONT,
                  foreground=RESULT_COLOR).grid(row=2, column=0, columnspan=6, padx=8, pady=(0, 8), sticky="w")

        qaddr_frame = self._reg_frame(
            parent, QADDR_ADDR, "QSPI_ADDR", "RW",
            "Target device address for the transaction \u2192 qspi_addr_i.")
        ttk.Label(qaddr_frame, text="Target address (hex):", font=UI_FONT).grid(
            row=1, column=0, padx=8, pady=5, sticky="w")
        self.qaddr_var = tk.StringVar(value="00000000")
        ttk.Entry(qaddr_frame, textvariable=self.qaddr_var, width=12).grid(
            row=1, column=1, padx=8, pady=5, sticky="w")
        qaddr_write_btn = ttk.Button(qaddr_frame, text="Write", command=self.write_qaddr)
        qaddr_write_btn.grid(row=1, column=2, padx=5, pady=5)
        qaddr_read_btn = ttk.Button(qaddr_frame, text="Read", command=self.read_qaddr)
        qaddr_read_btn.grid(row=1, column=3, padx=5, pady=5)
        self.qaddr_result_var = tk.StringVar(value="-")
        ttk.Label(qaddr_frame, textvariable=self.qaddr_result_var, font=MONO_FONT,
                  foreground=RESULT_COLOR).grid(row=2, column=0, columnspan=4, padx=8, pady=(0, 8), sticky="w")

        timeout_frame = self._reg_frame(
            parent, TIMEOUT_ADDR, "QSPI_TIMEOUT", "RW",
            "Timeout value \u2192 qspi_timeout_i, live-sampled during busy-stall. Units not yet confirmed.")
        ttk.Label(timeout_frame, text="Timeout value (hex, units TBD):", font=UI_FONT).grid(
            row=1, column=0, padx=8, pady=5, sticky="w")
        self.timeout_var = tk.StringVar(value="00000000")
        ttk.Entry(timeout_frame, textvariable=self.timeout_var, width=12).grid(
            row=1, column=1, padx=8, pady=5, sticky="w")
        timeout_write_btn = ttk.Button(timeout_frame, text="Write", command=self.write_timeout)
        timeout_write_btn.grid(row=1, column=2, padx=5, pady=5)
        timeout_read_btn = ttk.Button(timeout_frame, text="Read", command=self.read_timeout)
        timeout_read_btn.grid(row=1, column=3, padx=5, pady=5)
        self.timeout_result_var = tk.StringVar(value="-")
        ttk.Label(timeout_frame, textvariable=self.timeout_result_var, font=MONO_FONT,
                  foreground=RESULT_COLOR).grid(row=2, column=0, columnspan=4, padx=8, pady=(0, 8), sticky="w")

        self._action_buttons.extend([
            dlen_write_btn, dlen_read_btn, cmd_write_btn, cmd_read_btn,
            qaddr_write_btn, qaddr_read_btn, timeout_write_btn, timeout_read_btn,
        ])

    def write_dlen(self):
        val = self._parse_hex32(self.dlen_var.get(), "DATA_LEN")
        if val is None:
            return
        self._write_reg32(DLEN_ADDR, val, "dlen")

    def read_dlen(self):
        self._read_reg32(DLEN_ADDR, "dlen")

    def write_cmd(self):
        cmd = self._parse_hex8(self.cmd_byte_var.get(), "CMD")
        if cmd is None:
            return
        mode = self._parse_hex8(self.mode_byte_var.get(), "MODE_BYTE")
        if mode is None:
            return
        value = (mode << 8) | cmd
        self._write_reg32(CMD_ADDR, value, "cmd")

    def read_cmd(self):
        self._read_reg32(CMD_ADDR, "cmd")

    def write_qaddr(self):
        val = self._parse_hex32(self.qaddr_var.get(), "ADDR")
        if val is None:
            return
        self._write_reg32(QADDR_ADDR, val, "qaddr")

    def read_qaddr(self):
        self._read_reg32(QADDR_ADDR, "qaddr")

    def write_timeout(self):
        val = self._parse_hex32(self.timeout_var.get(), "TIMEOUT_VAL")
        if val is None:
            return
        self._write_reg32(TIMEOUT_ADDR, val, "timeout")

    def read_timeout(self):
        self._read_reg32(TIMEOUT_ADDR, "timeout")

    # ----------------------------------------------------------- FIFO & Status ---
    def _build_fifo_tab(self, parent):
        dr_frame = self._reg_frame(
            parent, DR_ADDR, "QSPI_DR", "RW",
            "TX/RX FIFO data word, direction gated by CFG0.DATA_DIR.")
        ttk.Label(dr_frame, text="Data word (hex):", font=UI_FONT).grid(
            row=1, column=0, padx=8, pady=5, sticky="w")
        self.dr_var = tk.StringVar(value="00000000")
        ttk.Entry(dr_frame, textvariable=self.dr_var, width=12).grid(
            row=1, column=1, padx=8, pady=5, sticky="w")
        dr_push_btn = ttk.Button(dr_frame, text="Push to TX FIFO (Write)", command=self.push_dr)
        dr_push_btn.grid(row=1, column=2, padx=5, pady=5)
        dr_pop_btn = ttk.Button(dr_frame, text="Pop from RX FIFO (Read)", command=self.pop_dr)
        dr_pop_btn.grid(row=1, column=3, padx=5, pady=5)
        self.dr_result_var = tk.StringVar(value="-")
        ttk.Label(dr_frame, textvariable=self.dr_result_var, font=MONO_FONT,
                  foreground=RESULT_COLOR).grid(row=2, column=0, columnspan=4, padx=8, pady=(0, 8), sticky="w")

        bcnt_frame = self._reg_frame(
            parent, BCNT_ADDR, "QSPI_BCNT", "RO",
            "Bytes transferred so far \u2192 qspi_byte_cnt_o.")
        bcnt_read_btn = ttk.Button(bcnt_frame, text="Read Byte Count", command=self.read_bcnt)
        bcnt_read_btn.grid(row=1, column=0, padx=8, pady=5, sticky="w")
        self.bcnt_result_var = tk.StringVar(value="-")
        ttk.Label(bcnt_frame, textvariable=self.bcnt_result_var, font=MONO_FONT,
                  foreground=RESULT_COLOR).grid(row=2, column=0, padx=8, pady=(0, 8), sticky="w")

        self._action_buttons.extend([dr_push_btn, dr_pop_btn, bcnt_read_btn])

    def push_dr(self):
        val = self._parse_hex32(self.dr_var.get(), "DR")
        if val is None:
            return
        self._write_reg32(DR_ADDR, val, "dr_push")

    def pop_dr(self):
        self._read_reg32(DR_ADDR, "dr_pop")

    def read_bcnt(self):
        self._read_reg32(BCNT_ADDR, "bcnt")

    # --------------------------------------------------------- Connection ---
    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])
        self._log(f"Found {len(ports)} port(s): {', '.join(ports) if ports else 'none'}")

    def toggle_connect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None
            self.status_var.set("Disconnected")
            self.status_lbl.configure(foreground="red")
            self.connect_btn.configure(text="Connect")
            self._log("Disconnected from port.")
            return

        port = self.port_var.get()
        if not port:
            self._log("ERROR: no port selected.")
            return
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=int(self.baud_var.get()),
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0,
            )
            self.status_var.set(f"Connected: {port}")
            self.status_lbl.configure(foreground="green")
            self.connect_btn.configure(text="Disconnect")
            self._log(f"Connected to {port} @ {self.baud_var.get()} baud, 8N1.")
        except serial.SerialException as e:
            self._log(f"ERROR: could not open {port}: {e}")

    def _on_close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.root.destroy()

    # ------------------------------------------------------------ Parsing ---
    def _parse_addr(self):
        raw = self.addr_var.get().strip()
        try:
            val = int(raw, 16)
        except ValueError:
            self._log("ERROR: address must be valid hex.")
            return None
        if not (0 <= val <= 0x7F):
            self._log("ERROR: address must be within 0x00-0x7F (7-bit field, MSB is mode flag).")
            return None
        return val

    def _parse_wdata(self):
        raw = self.wdata_var.get().strip().replace(" ", "")
        if len(raw) != 8:
            self._log("ERROR: write data must be exactly 4 bytes (8 hex characters).")
            return None
        try:
            val = bytes.fromhex(raw)
        except ValueError:
            self._log("ERROR: write data must be valid hex.")
            return None
        return val

    # --------------------------------------------------------- Transaction ---
    def send_transaction(self):
        if self.busy:
            return
        if not (self.ser and self.ser.is_open):
            self._log("ERROR: not connected.")
            return

        addr = self._parse_addr()
        if addr is None:
            return

        mode = self.mode_var.get()

        if mode == "write":
            wdata = self._parse_wdata()
            if wdata is None:
                return
            addr_byte = addr | 0x80
            self._set_busy(True)
            threading.Thread(target=self._do_write, args=(addr_byte, wdata), daemon=True).start()
        else:
            addr_byte = addr & 0x7F
            self._set_busy(True)
            threading.Thread(target=self._do_read, args=(addr_byte,), daemon=True).start()

    @staticmethod
    def _bin_str(data_bytes):
        """Format bytes as binary, clearly separated and labeled per byte,
        e.g. b'\\xDE\\xAD' -> 'B0=11011110 B1=10101101'"""
        return " ".join(f"B{i}={b:08b}" for i, b in enumerate(data_bytes))

    def _do_read(self, addr_byte, tag=None):
        try:
            self.ser.reset_input_buffer()
            self.ser.write(bytes([addr_byte]))
            self.result_queue.put(("log", f"TX ADDR: 0x{addr_byte:02X} "
                                           f"({addr_byte:08b}) [READ mode]"))

            response = self.ser.read(5)
            if len(response) < 5:
                self.result_queue.put(("log", f"ERROR: timeout, only received "
                                               f"{len(response)}/5 bytes "
                                               f"(expected 1 ACK + 4 data)."))
                return

            ack_byte, data = response[0], response[1:5]
            bin_str = self._bin_str(data)
            hex_str = " ".join(f"0x{b:02X}" for b in data)
            data_u32 = int.from_bytes(data, byteorder="big")
            self.result_queue.put(("log", f"RX ACK: 0x{ack_byte:02X} ({ack_byte:08b})"))
            self.result_queue.put(("log", f"RX DATA: {hex_str}  |  {bin_str}"))

            result_text = (
                f"Mode: READ\nAddress: 0x{addr_byte:02X}\n"
                f"ACK: 0x{ack_byte:02X} ({ack_byte:08b})\n"
                f"Data (hex): {hex_str}\nData (bin): {bin_str}\n"
                f"Data as 32-bit (high byte first): 0x{data_u32:08X}"
            )
            if tag == "cfg0":
                result_text += f"\n\n-- QSPI_CFG0 field breakdown --\n{self._describe_cfg0(data_u32)}"
                self.result_queue.put(("cfg0_unpack", data_u32))
            elif tag == "ctrl":
                status_desc = self._describe_ctrl_status(data_u32)
                result_text += f"\n\n-- QSPI_CTRL status --\n{status_desc}"
                self.result_queue.put(("ctrl_status", status_desc))
            elif tag == "dlen":
                reg_text = f"DATA_LEN = {data_u32} bytes  (0x{data_u32:08X})"
                result_text += f"\n\n-- QSPI_DLEN --\n{reg_text}"
                self.result_queue.put(("reg_update", ("dlen", reg_text)))
            elif tag == "cmd":
                cmd_byte = data_u32 & 0xFF
                mode_byte = (data_u32 >> 8) & 0xFF
                reg_text = f"CMD = 0x{cmd_byte:02X}   MODE_BYTE = 0x{mode_byte:02X}   (reg = 0x{data_u32:08X})"
                result_text += f"\n\n-- QSPI_CMD --\n{reg_text}"
                self.result_queue.put(("reg_update", ("cmd", reg_text)))
            elif tag == "qaddr":
                reg_text = f"ADDR = 0x{data_u32:08X}  ({data_u32})"
                result_text += f"\n\n-- QSPI_ADDR --\n{reg_text}"
                self.result_queue.put(("reg_update", ("qaddr", reg_text)))
            elif tag == "timeout":
                reg_text = f"TIMEOUT_VAL = {data_u32}  (0x{data_u32:08X})  [units TBD]"
                result_text += f"\n\n-- QSPI_TIMEOUT --\n{reg_text}"
                self.result_queue.put(("reg_update", ("timeout", reg_text)))
            elif tag == "dr_pop":
                reg_text = f"Popped 0x{data_u32:08X}  ({data_u32}) from RX FIFO"
                result_text += f"\n\n-- QSPI_DR (RX FIFO pop) --\n{reg_text}"
                self.result_queue.put(("reg_update", ("dr", reg_text)))
            elif tag == "bcnt":
                reg_text = f"BYTE_CNT = {data_u32} bytes  (0x{data_u32:08X})"
                result_text += f"\n\n-- QSPI_BCNT --\n{reg_text}"
                self.result_queue.put(("reg_update", ("bcnt", reg_text)))
            self.result_queue.put(("result", result_text))
        except serial.SerialException as e:
            self.result_queue.put(("log", f"ERROR: {e}"))
        finally:
            self.result_queue.put(("done", None))

    def _do_write(self, addr_byte, wdata, tag=None):
        try:
            self.ser.reset_input_buffer()

            bin_str = self._bin_str(wdata)
            hex_str = " ".join(f"0x{b:02X}" for b in wdata)
            sent_u32 = int.from_bytes(wdata, byteorder="big")

            # Send ADDR + DATA in a single write() call (one USB/UART burst)
            # instead of two separate calls, to avoid a gap between them
            # caused by the serial adapter's internal buffering/latency timer.
            self.ser.write(bytes([addr_byte]) + wdata)
            self.result_queue.put(("log", f"TX ADDR: 0x{addr_byte:02X} "
                                           f"({addr_byte:08b}) [WRITE mode]"))
            self.result_queue.put(("log", f"TX DATA: {hex_str}  |  {bin_str}"))

            ack = self.ser.read(1)
            if len(ack) < 1:
                self.result_queue.put(("log", "ERROR: timeout waiting for ACK byte."))
                return

            ack_byte = ack[0]
            self.result_queue.put(("log", f"RX ACK: 0x{ack_byte:02X} ({ack_byte:08b})"))

            result_text = (
                f"Mode: WRITE\nAddress: 0x{addr_byte:02X}\n"
                f"Sent data (hex): {hex_str}\nSent data (bin): {bin_str}\n"
                f"Sent as 32-bit (high byte first): 0x{sent_u32:08X}\n"
                f"ACK: 0x{ack_byte:02X} ({ack_byte:08b})"
            )
            if tag == "cfg0":
                result_text += f"\n\n-- QSPI_CFG0 field breakdown --\n{self._describe_cfg0(sent_u32)}"
            elif tag == "ctrl_start":
                result_text += (f"\n\n-- QSPI_CTRL --\nSTART pulse sent (bit {CTRL_START_BIT} = 1, "
                                 f"all other bits 0).")
            elif tag == "ctrl_abort":
                result_text += (f"\n\n-- QSPI_CTRL --\nABORT pulse sent (bit {CTRL_ABORT_BIT} = 1, "
                                 f"all other bits 0).")
            elif tag == "ctrl_flush":
                result_text += (f"\n\n-- QSPI_CTRL --\nFLUSH pulse sent (bit {CTRL_FLUSH_BIT} = 1, "
                                 f"all other bits 0).")
            elif tag == "ctrl_clear":
                result_text += ("\n\n-- QSPI_CTRL --\nW1C write sent: DONE, TIMEOUT, and all "
                                 "FIFO_ERR bits cleared.")
            elif tag == "dlen":
                reg_text = f"Wrote DATA_LEN = {sent_u32} bytes  (0x{sent_u32:08X})"
                result_text += f"\n\n-- QSPI_DLEN --\n{reg_text}"
                self.result_queue.put(("reg_update", ("dlen", reg_text)))
            elif tag == "cmd":
                cmd_byte = sent_u32 & 0xFF
                mode_byte = (sent_u32 >> 8) & 0xFF
                reg_text = f"Wrote CMD = 0x{cmd_byte:02X}   MODE_BYTE = 0x{mode_byte:02X}   (reg = 0x{sent_u32:08X})"
                result_text += f"\n\n-- QSPI_CMD --\n{reg_text}"
                self.result_queue.put(("reg_update", ("cmd", reg_text)))
            elif tag == "qaddr":
                reg_text = f"Wrote ADDR = 0x{sent_u32:08X}  ({sent_u32})"
                result_text += f"\n\n-- QSPI_ADDR --\n{reg_text}"
                self.result_queue.put(("reg_update", ("qaddr", reg_text)))
            elif tag == "timeout":
                reg_text = f"Wrote TIMEOUT_VAL = {sent_u32}  (0x{sent_u32:08X})  [units TBD]"
                result_text += f"\n\n-- QSPI_TIMEOUT --\n{reg_text}"
                self.result_queue.put(("reg_update", ("timeout", reg_text)))
            elif tag == "dr_push":
                reg_text = f"Pushed 0x{sent_u32:08X}  ({sent_u32}) to TX FIFO"
                result_text += f"\n\n-- QSPI_DR (TX FIFO push) --\n{reg_text}"
                self.result_queue.put(("reg_update", ("dr", reg_text)))
            self.result_queue.put(("result", result_text))
        except serial.SerialException as e:
            self.result_queue.put(("log", f"ERROR: {e}"))
        finally:
            self.result_queue.put(("done", None))

    # ------------------------------------------------------------- Queue ---
    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.result_queue.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "result":
                    self.result_var.set(payload)
                elif kind == "cfg0_unpack":
                    self._unpack_cfg0(payload)
                elif kind == "ctrl_status":
                    self.ctrl_status_var.set(payload)
                elif kind == "reg_update":
                    reg_tag, text = payload
                    self._reg_result_vars()[reg_tag].set(text)
                elif kind == "done":
                    self._set_busy(False)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        self.log_text.see("end")


if __name__ == "__main__":
    root = tk.Tk()
    app = UartFpgaGui(root)
    root.mainloop()