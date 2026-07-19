"""Sequence items and transaction records for the apb_qspi pyuvm testbench."""

import enum

from pyuvm import uvm_sequence_item


class ApbKind(enum.Enum):
    READ = 0
    WRITE = 1


class ApbItem(uvm_sequence_item):
    """One APB transfer. For reads, the driver fills in .rdata.
    .wait_states is filled in by the driver for both directions."""

    def __init__(self, name="apb_item", kind=ApbKind.WRITE, addr=0, data=0):
        super().__init__(name)
        self.kind = kind
        self.addr = addr
        self.data = data  # wdata for writes
        self.rdata = None  # filled by driver on reads
        self.wait_states = 0  # filled by driver

    def __str__(self):
        if self.kind == ApbKind.WRITE:
            return f"APB WR [0x{self.addr:02X}] <= 0x{self.data:08X} (ws={self.wait_states})"
        rd = f"0x{self.rdata:08X}" if self.rdata is not None else "?"
        return f"APB RD [0x{self.addr:02X}] => {rd} (ws={self.wait_states})"


class QspiXfer:
    """A QSPI flash transaction, either predicted from APB traffic or decoded
    off the wire by the QSPI monitor. Plain record, not a sequence item."""

    def __init__(self):
        # shape
        self.has_cmd = True  # False when CRM is locked (command phase skipped)
        self.dead_cmd_cycle = False  # cmd_mode==0 while command phase not skipped
        self.cmd = None  # 8-bit opcode (None if no command phase)
        self.cmd_lanes = 1
        self.addr_bytes = 0  # 0 (skipped) / 3 / 4
        self.addr = None
        self.addr_lanes = 1
        self.mode_byte = None  # None if MODE phase absent
        self.dummy = 0  # dummy cycles
        self.dir_write = 0
        self.data_lanes = 0  # 0: no data phase
        self.dlen = 0  # data bytes
        self.sck_mode = 0  # CPOL/CPHA (0: mode 0, 1: mode 3)
        self.endian = 0
        self.aborted = False  # set by predictor when software aborts mid-flight
        # payload
        self.data = b""  # write: predicted/monitored tx bytes; read: monitored rx bytes
        # monitor-only observations
        self.sck_edges = None  # rising edges counted while CSn low
        self.protocol_errors = []

    def expected_edges(self):
        """Rising SCK edges this transaction should produce (SDR)."""
        edges = 0
        if self.dead_cmd_cycle:
            edges += 1
        elif self.has_cmd and self.cmd is not None:
            edges += 8 // self.cmd_lanes
        if self.addr_bytes:
            edges += self.addr_bytes * 8 // self.addr_lanes
        if self.mode_byte is not None:
            edges += 8 // self.addr_lanes
        edges += self.dummy
        if self.data_lanes:
            edges += self.dlen * 8 // self.data_lanes
        return edges

    def __str__(self):
        cmd = f"0x{self.cmd:02X}" if self.cmd is not None else "--"
        addr = f"0x{self.addr:X}" if self.addr is not None else "--"
        d = self.data.hex() if self.data else ""
        return (
            f"QSPI cmd={cmd}@x{self.cmd_lanes} addr={addr}({self.addr_bytes}B)@x{self.addr_lanes} "
            f"mode={self.mode_byte} dummy={self.dummy} "
            f"{'WR' if self.dir_write else 'RD'} dlen={self.dlen}@x{self.data_lanes} "
            f"sckmode={self.sck_mode} data={d[:64]}{'...' if len(d) > 64 else ''}"
        )
