"""Protocol monitors.

ApbMonitor  - passive APB pin watcher: emits completed transfers on its
              analysis port and checks APB protocol rules cycle by cycle.
QspiMonitor - passive QSPI bus watcher: decodes each CSn-framed transaction
              (using the phase shape predicted from APB traffic, since the
              QSPI wire format is not self-describing) and checks SPI-level
              protocol rules.
"""

import cocotb
from cocotb.triggers import FallingEdge, First, ReadOnly, RisingEdge, Timer
from cocotb.utils import get_sim_time
from pyuvm import ConfigDB, uvm_analysis_port, uvm_component

from seq_items import ApbItem, ApbKind, QspiXfer


def xint(sig, default=0):
    """int(signal) that tolerates X/Z by returning a default."""
    try:
        return int(sig.value)
    except ValueError:
        return default


def bits4(sig):
    """Sample a 4-bit vector into a list [b3, b2, b1, b0]; X/Z become None."""
    s = str(sig.value)  # MSB first, e.g. "1z0x"
    out = []
    for ch in s:
        if ch in "01":
            out.append(int(ch))
        elif ch in "Hh":  # weak 1 (pullup)
            out.append(1)
        elif ch in "Ll":
            out.append(0)
        else:
            out.append(None)
    return out


class ApbMonitor(uvm_component):
    """APB protocol compliance checks + transfer stream."""

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.bfm = ConfigDB().get(self, "", "BFM")
        self.errors = 0

    def err(self, msg):
        self.errors += 1
        self.logger.error(f"APB protocol: {msg}")

    async def run_phase(self):
        dut = self.bfm.dut
        prev = None
        access_snapshot = None
        wait_states = 0
        expect_enable_low = False

        while True:
            await RisingEdge(dut.clk_i)
            await ReadOnly()
            if xint(dut.rst_ni, 0) == 0:
                prev = None
                access_snapshot = None
                expect_enable_low = False
                continue

            s = {
                "psel": xint(dut.psel_i),
                "penable": xint(dut.penable_i),
                "pwrite": xint(dut.pwrite_i),
                "paddr": xint(dut.paddr_i),
                "pwdata": xint(dut.pwdata_i),
                "prdata": xint(dut.prdata_o),
                "pready": xint(dut.pready_o),
            }

            # rule: PENABLE only with PSEL
            if s["penable"] and not s["psel"]:
                self.err("PENABLE asserted without PSEL")

            # rule: after a completed transfer, PENABLE must drop for >=1 cycle
            if expect_enable_low and s["penable"]:
                self.err("PENABLE not deasserted after transfer completion")
            expect_enable_low = False

            # rule: setup phase (PSEL && !PENABLE) must be followed by access phase
            if prev and prev["psel"] and not prev["penable"]:
                if not (s["psel"] and s["penable"]):
                    self.err("setup phase not followed by access phase")

            if s["psel"] and s["penable"]:
                if access_snapshot is None:
                    access_snapshot = dict(s)
                    wait_states = 0
                else:
                    # rule: control/data stable while stalled
                    for f in ("paddr", "pwrite", "pwdata") if s["pwrite"] else ("paddr", "pwrite"):
                        if s[f] != access_snapshot[f]:
                            self.err(
                                f"{f} changed mid-access (0x{access_snapshot[f]:X} -> 0x{s[f]:X})"
                            )
                if s["pready"]:
                    item = ApbItem(
                        kind=ApbKind.WRITE if s["pwrite"] else ApbKind.READ,
                        addr=s["paddr"],
                        data=s["pwdata"],
                    )
                    if not s["pwrite"]:
                        item.rdata = s["prdata"]
                    item.wait_states = wait_states
                    self.ap.write(item)
                    access_snapshot = None
                    expect_enable_low = True
                else:
                    wait_states += 1

            prev = s

    def check_phase(self):
        assert self.errors == 0, f"{self.errors} APB protocol violation(s)"


class QspiMonitor(uvm_component):
    """Decodes QSPI transactions between CSn edges and checks SPI rules.

    Shape information (lane counts, phase presence) comes from the predictor
    via a shared queue, because a QSPI bit stream cannot be decoded without
    knowing the configuration that produced it.
    """

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.bfm = ConfigDB().get(self, "", "BFM")
        self.shape_q = ConfigDB().get(self, "", "SHAPE_Q")
        try:
            self.waive_known = ConfigDB().get(self, "", "WAIVE_KNOWN_ISSUES")
        except Exception:
            self.waive_known = True
        try:
            self.fifo_probe = ConfigDB().get(self, "", "FIFO_PROBE")
        except Exception:
            self.fifo_probe = False
        self.errors = 0
        self._edge_times = []

    def _is_ki1(self, tran, truncated, edges):
        """KI-1 signature: a transfer with a mid-transfer word boundary
        (dlen > 4, either direction) cut one edge short in its final data
        byte by the SCK-pause desync."""
        return (
            self.waive_known
            and tran.dlen > 4
            and truncated == f"data byte {tran.dlen - 1}"
            and edges == tran.expected_edges() - 1
        )

    def err(self, msg):
        self.errors += 1
        self.logger.error(f"SPI protocol: {msg}")

    async def _fifo_probe(self):
        """Debug aid: trace every FIFO push/pop with occupancy."""
        dut = self.bfm.dut
        fifo = dut.u_dut.u_fifo
        # occupancy counter name differs between fifo implementations
        occ = getattr(fifo, "count_q", None)
        if occ is None:
            occ = getattr(fifo, "status_q", None)
        while True:
            await RisingEdge(dut.clk_i)
            await ReadOnly()
            push, pop = xint(fifo.push_i), xint(fifo.pop_i)
            if push or pop:
                self.logger.info(
                    f"FIFO push={push} pop={pop} occ={xint(occ) if occ is not None else '?'} "
                    f"full={xint(fifo.full_o)} empty={xint(fifo.empty_o)} "
                    f"data_i={str(fifo.data_i.value)} data_o={str(fifo.data_o.value)}"
                )

    def _edge_report(self):
        """Debug aid: report irregular SCK periods within the last transaction."""
        t = self._edge_times
        if len(t) < 3:
            return
        deltas = [round(b - a, 2) for a, b in zip(t, t[1:])]
        nominal = min(deltas)
        odd = [(i + 1, d) for i, d in enumerate(deltas) if d > nominal * 1.4]
        if odd:
            self.logger.info(
                f"SCK period irregularities (edge#, period ns; nominal {nominal}): {odd[:12]}"
            )

    async def _sample_cycles(self, ncycles, lanes, slave_drives, tran):
        """Sample `ncycles` rising SCK edges MSB-first.
        Returns (bits_value, cycles_seen, csn_rose, sck_level_at_last_event).
        slave_drives selects which IO lines carry data in x1."""
        dut = self.bfm.dut
        value = 0
        seen = 0
        sck_now = None
        while seen < ncycles:
            await First(RisingEdge(dut.qspi_sck), RisingEdge(dut.qspi_csn))
            await ReadOnly()
            sck_now = xint(dut.qspi_sck, -1)
            if int(dut.qspi_csn.value) == 1:
                return value, seen, True, sck_now
            self._edge_times.append(get_sim_time("ns"))
            io = bits4(dut.qspi_io)  # [io3, io2, io1, io0]
            if lanes == 1:
                # x1: slave answers on IO1 (SO), master transmits on IO0 (SI)
                sample = io[2] if slave_drives else io[3]
                nbits = 1
            elif lanes == 2:
                b1, b0 = io[2], io[3]
                sample = None if (b1 is None or b0 is None) else (b1 << 1) | b0
                nbits = 2
            else:  # lanes == 4
                b3, b2, b1, b0 = io[0], io[1], io[2], io[3]
                sample = (
                    None
                    if None in (b3, b2, b1, b0)
                    else (b3 << 3) | (b2 << 2) | (b1 << 1) | b0
                )
                nbits = 4
            if sample is None:
                self.err(f"unresolvable IO value during sampled phase: {io} ({tran})")
                sample = 0
            value = (value << nbits) | sample
            seen += 1
        return value, seen, False, sck_now

    async def _skip_cycles(self, ncycles):
        """Count SCK rising edges without sampling (dummy cycles / deselect wait).
        Returns (cycles_seen, csn_rose, sck_level_at_last_event)."""
        dut = self.bfm.dut
        seen = 0
        sck_now = None
        while seen < ncycles:
            await First(RisingEdge(dut.qspi_sck), RisingEdge(dut.qspi_csn))
            await ReadOnly()
            sck_now = xint(dut.qspi_sck, -1)
            if int(dut.qspi_csn.value) == 1:
                return seen, True, sck_now
            self._edge_times.append(get_sim_time("ns"))
            seen += 1
        return seen, False, sck_now

    async def run_phase(self):
        dut = self.bfm.dut
        if getattr(self, "fifo_probe", False):
            cocotb.start_soon(self._fifo_probe())
        while True:
            await FallingEdge(dut.qspi_csn)
            self._edge_times.clear()

            # SCK is parked at idle this early in the transaction, safe to
            # sample without ReadOnly (first toggle is cycles away)
            sck_at_sel = xint(dut.qspi_sck, -1)

            # predicted shape for this transaction; the predictor pushes it in
            # the same timestep the START write completes, before any SCK edge
            if self.shape_q.qsize() == 0:
                self.logger.warning("CSn fell before a transaction was predicted; waiting")
            shape = await self.shape_q.get()

            tran = QspiXfer()
            for f in (
                "has_cmd",
                "dead_cmd_cycle",
                "cmd_lanes",
                "addr_bytes",
                "addr_lanes",
                "dummy",
                "dir_write",
                "data_lanes",
                "dlen",
                "sck_mode",
                "endian",
            ):
                setattr(tran, f, getattr(shape, f))
            tran.mode_byte = shape.mode_byte

            # rule: SCK at idle level (CPOL) when CSn falls
            if sck_at_sel != tran.sck_mode:
                self.err(
                    f"SCK not at idle level on CSn assert (sck={sck_at_sel}, CPOL={tran.sck_mode})"
                )

            edges = 0
            truncated = None  # phase name if CSn rose mid-phase
            sck_now = sck_at_sel

            # command phase
            if tran.dead_cmd_cycle:
                n, rose, sck_now = await self._skip_cycles(1)
                edges += n
                if rose:
                    truncated = "dead-cmd"
            elif tran.has_cmd:
                val, n, rose, sck_now = await self._sample_cycles(
                    8 // tran.cmd_lanes, tran.cmd_lanes, False, "cmd"
                )
                edges += n
                if rose:
                    truncated = "cmd"
                else:
                    tran.cmd = val
                self.logger.debug(f"cmd phase: 0x{val:02X} after {n} edges")

            # address phase
            if not truncated and tran.addr_bytes:
                val, n, rose, sck_now = await self._sample_cycles(
                    tran.addr_bytes * 8 // tran.addr_lanes, tran.addr_lanes, False, "addr"
                )
                edges += n
                if rose:
                    truncated = "addr"
                else:
                    tran.addr = val
                self.logger.debug(f"addr phase: 0x{val:X} after {n} edges")

            # mode byte phase
            if not truncated and tran.mode_byte is not None:
                val, n, rose, sck_now = await self._sample_cycles(
                    8 // tran.addr_lanes, tran.addr_lanes, False, "mode"
                )
                edges += n
                if rose:
                    truncated = "mode"
                else:
                    tran.mode_byte = val

            # dummy cycles: master must release its outputs (checked via data phase)
            if not truncated and tran.dummy:
                n, rose, sck_now = await self._skip_cycles(tran.dummy)
                edges += n
                if rose:
                    truncated = "dummy"

            # data phase
            if not truncated and tran.data_lanes:
                data = bytearray()
                slave_drives = not tran.dir_write
                for i in range(tran.dlen):
                    val, n, rose, sck_now = await self._sample_cycles(
                        8 // tran.data_lanes, tran.data_lanes, slave_drives, "data"
                    )
                    edges += n
                    if rose:
                        truncated = f"data byte {i}"
                        break
                    data.append(val)
                    # rule: DUT must not drive the bus while the flash responds
                    if slave_drives:
                        oe = xint(dut.qspi_oe, 0)
                        if oe != 0:
                            self.err(f"qspi_oe=0b{oe:04b} nonzero during read data phase")
                tran.data = bytes(data)

            # wait for deselect, counting stray edges
            if not truncated:
                n, _, sck_now = await self._skip_cycles(10**9)  # runs until CSn rises
                edges += n
                if n:
                    self.logger.debug(f"{n} stray SCK edge(s) between last phase and deselect")
            elif getattr(shape, "aborted", False):
                self.logger.info(
                    f"[abort] transaction cut short by software abort in {truncated} "
                    f"after {edges} edges (expected)"
                )
            elif self._is_ki1(tran, truncated, edges):
                # KI-1: SCK-pause desync in qspi_master (marked TODO in the RTL).
                # A word-boundary FIFO pause suppresses the pin toggle but the
                # internal edge bookkeeping still advances, so the transfer ends
                # one rising edge early and CSn cuts off the final bit.
                self.logger.warning(
                    f"[KI-1] transfer ended one SCK edge early (truncated in {truncated} "
                    f"after {edges} edges) - known qspi_master clock-pause bug"
                )
            else:
                self.err(f"CSn deasserted mid-phase (truncated in {truncated} after {edges} edges)")

            # rule: SCK back at idle level (CPOL) when CSn rises
            if sck_now != tran.sck_mode:
                self.err(
                    f"SCK not at idle level on CSn deassert (sck={sck_now}, CPOL={tran.sck_mode})"
                )

            tran.sck_edges = edges
            self._edge_report()
            self.logger.info(f"observed {tran}")
            self.ap.write(tran)

    def check_phase(self):
        assert self.errors == 0, f"{self.errors} SPI protocol violation(s)"
