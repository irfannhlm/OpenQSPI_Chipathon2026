"""Scoreboards.

FlashGolden    - byte-accurate model of the flash array as far as the test has
                 established it (erase -> 0xFF, program -> AND-semantics).
QspiScoreboard - compares predicted vs observed QSPI transactions (shape and
                 TX data), and checks observed read data / ID commands against
                 the golden flash state.
"""

from pyuvm import ConfigDB, uvm_scoreboard, uvm_tlm_analysis_fifo

# S25FL128S opcodes (3-byte addressing variants used by the competition spec)
CMD_WRR = 0x01
CMD_PP = 0x02
CMD_READ = 0x03
CMD_WRDI = 0x04
CMD_RDSR1 = 0x05
CMD_WREN = 0x06
CMD_RDSR2 = 0x07
CMD_FAST_READ = 0x0B
CMD_P4E = 0x20
CMD_CLSR = 0x30
CMD_QPP = 0x32
CMD_RDCR = 0x35
CMD_DOR = 0x3B
CMD_QOR = 0x6B
CMD_REMS = 0x90
CMD_RDID = 0x9F
CMD_RES = 0xAB
CMD_DIOR = 0xBB
CMD_SE = 0xD8
CMD_RESET = 0xF0

READ_CMDS = {CMD_READ, CMD_FAST_READ, CMD_DOR, CMD_QOR, CMD_DIOR, 0xEB}
PROGRAM_CMDS = {CMD_PP, CMD_QPP}

SECTOR_SIZE = 64 * 1024  # SE (0xD8) on a uniform 64KB sector
JEDEC_ID = bytes([0x01, 0x20, 0x18])  # S25FL128S: Infineon/Spansion, 128Mb
ELECTRONIC_SIG = 0x17


class FlashGolden:
    """Tracks flash array content where the testbench has made it knowable."""

    def __init__(self):
        self.mem = {}  # addr -> byte (only known locations)
        self.wel = False

    def erase(self, addr):
        base = addr & ~(SECTOR_SIZE - 1)
        for a in range(base, base + SECTOR_SIZE):
            self.mem[a] = 0xFF

    def program(self, addr, data):
        page = addr & ~0xFF
        for i, b in enumerate(data):
            a = page | ((addr + i) & 0xFF)  # PP wraps within the 256B page
            old = self.mem.get(a)
            self.mem[a] = (old & b) if old is not None else None

    def read(self, addr, n):
        return [self.mem.get(addr + i) for i in range(n)]


class QspiScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.expected_fifo = uvm_tlm_analysis_fifo("expected_fifo", self)
        self.actual_fifo = uvm_tlm_analysis_fifo("actual_fifo", self)
        self.golden = FlashGolden()
        try:
            self.waive_known = ConfigDB().get(self, "", "WAIVE_KNOWN_ISSUES")
        except Exception:
            self.waive_known = True
        self.errors = 0
        self.compared = 0

    def err(self, msg):
        self.errors += 1
        self.logger.error(f"scoreboard: {msg}")

    async def run_phase(self):
        while True:
            expected = await self.expected_fifo.get()
            actual = await self.actual_fifo.get()
            self.compared += 1
            self.compare(expected, actual)

    def compare(self, exp, act):
        tag = f"xfer #{self.compared}"

        # --- shape ---
        if exp.cmd != act.cmd:
            self.err(f"{tag}: command mismatch: sent 0x{fmt(act.cmd)} != programmed 0x{fmt(exp.cmd)}")
        if exp.addr != act.addr:
            self.err(f"{tag}: address mismatch: wire 0x{fmt(act.addr)} != programmed 0x{fmt(exp.addr)}")
        if exp.mode_byte is not None and exp.mode_byte != act.mode_byte:
            self.err(f"{tag}: mode byte mismatch: wire {fmt(act.mode_byte)} != {fmt(exp.mode_byte)}")
        exp_edges = exp.expected_edges()
        incomplete = act.sck_edges != exp_edges
        if exp.aborted:
            pass  # software abort: partial transaction is the expected outcome
        elif incomplete:
            if self.waive_known and exp.dlen > 4 and act.sck_edges == exp_edges - 1:
                self.logger.warning(
                    f"[KI-1] {tag}: SCK edge count {act.sck_edges} == expected-1 "
                    f"(known qspi_master clock-pause bug)"
                )
            elif exp.sck_mode == 1 and act.sck_edges == exp_edges + 1:
                self.err(
                    f"{tag}: SCK edge count {act.sck_edges} != expected {exp_edges} "
                    f"(mode-3 return-to-idle edge; DUT emits one extra rising edge)"
                )
            else:
                self.err(f"{tag}: SCK edge count {act.sck_edges} != expected {exp_edges}")

        # --- write data on the wire ---
        if exp.dir_write and exp.data_lanes:
            if exp.data != act.data:
                self.err(
                    f"{tag}: TX data mismatch:\n"
                    f"    wire     : {act.data.hex()}\n"
                    f"    programmed: {exp.data.hex()}"
                )

        # --- flash-state bookkeeping / read-back checks (use wire truth) ---
        cmd = act.cmd
        if cmd == CMD_WREN:
            self.golden.wel = True
        elif cmd == CMD_WRDI:
            self.golden.wel = False
        elif cmd in (CMD_WRR, CMD_CLSR, CMD_RESET):
            self.golden.wel = False  # WRR consumes WEL; others don't affect the array
        elif cmd == CMD_SE:
            if self.golden.wel and act.addr is not None:
                self.golden.erase(act.addr)
                self.golden.wel = False
            else:
                self.err(f"{tag}: SE issued without WEL set (flash will ignore it)")
        elif cmd in PROGRAM_CMDS:
            if not self.golden.wel or act.addr is None:
                self.err(f"{tag}: PP/QPP issued without WEL set (flash will ignore it)")
            elif incomplete:
                # flash discards a program whose bit count is cut short (KI-1);
                # mirror that: memory unchanged, WEL still set
                self.logger.warning(
                    f"[KI-1] {tag}: program transaction incomplete on the wire; "
                    f"flash ignores it (memory unchanged)"
                )
            else:
                self.golden.program(act.addr, act.data)
                self.golden.wel = False
        elif cmd in READ_CMDS and act.addr is not None:
            golden = self.golden.read(act.addr, len(act.data))
            shown = 0
            mismatches = 0
            for i, (g, a) in enumerate(zip(golden, act.data)):
                if g is not None and g != a:
                    mismatches += 1
                    if shown < 4:
                        self.err(
                            f"{tag}: read data mismatch at 0x{act.addr + i:06X}: "
                            f"flash returned 0x{a:02X}, golden model has 0x{g:02X}"
                        )
                        shown += 1
            if mismatches > shown:
                self.err(f"{tag}: ... plus {mismatches - shown} more read data mismatch(es)")
        elif cmd == CMD_RDID:
            if act.data[: len(JEDEC_ID)] != JEDEC_ID[: len(act.data)]:
                self.err(f"{tag}: RDID returned {act.data.hex()}, expected prefix {JEDEC_ID.hex()}")
        elif cmd == CMD_REMS:
            expected = bytes([0x01, ELECTRONIC_SIG] * ((len(act.data) + 1) // 2))[: len(act.data)]
            if act.data != expected:
                self.err(f"{tag}: REMS returned {act.data.hex()}, expected {expected.hex()}")
        elif cmd == CMD_RES:
            if any(b != ELECTRONIC_SIG for b in act.data):
                self.err(f"{tag}: RES returned {act.data.hex()}, expected 0x{ELECTRONIC_SIG:02X}")

    def check_phase(self):
        if self.expected_fifo.can_get():
            self.err("predicted transaction(s) never observed on the QSPI bus")
        if self.actual_fifo.can_get():
            self.err("observed transaction(s) never predicted")
        assert self.errors == 0, f"{self.errors} scoreboard mismatch(es) over {self.compared} xfers"
        assert self.compared > 0, "scoreboard compared nothing - environment is miswired"


def fmt(v):
    return f"{v:X}" if v is not None else "None"
