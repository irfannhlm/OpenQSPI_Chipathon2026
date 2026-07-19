"""Predictor: shadows apb_qspi CSR state from the APB transfer stream and, on
each START, emits the expected QSPI transaction (shape + TX payload) to both
the scoreboard (for comparison) and the QSPI monitor (as decode shape)."""

import math

import regs
from pyuvm import ConfigDB, uvm_analysis_port, uvm_subscriber

from seq_items import ApbKind, QspiXfer


class QspiPredictor(uvm_subscriber):
    def build_phase(self):
        self.expected_ap = uvm_analysis_port("expected_ap", self)
        self.shape_q = ConfigDB().get(self, "", "SHAPE_Q")
        self.shadow = {regs.CFG0: 0, regs.DLEN: 0, regs.CMD: 0, regs.ADDR: 0, regs.TIMEOUT: 0}
        self.pending_tx = []  # DR words pushed while DATA_DIR=write
        self.crm_locked = False  # mirrors qspi_master's crm_active register
        self.last_xfer = None  # most recently predicted transaction (for abort marking)

    def write(self, item):
        if item.kind != ApbKind.WRITE:
            return
        off = item.addr & 0xFF
        if off in self.shadow:
            self.shadow[off] = item.data
        elif off == regs.DR:
            cfg = regs.unpack_cfg0(self.shadow[regs.CFG0])
            if cfg["dir_write"]:
                self.pending_tx.append(item.data)
        elif off == regs.CTRL:
            if item.data & regs.CTRL_FLUSH:
                self.pending_tx.clear()
            if item.data & regs.CTRL_ABORT and self.last_xfer is not None:
                # mark in-flight transaction; monitor/scoreboard share this object
                self.last_xfer.aborted = True
            if item.data & regs.CTRL_START:
                self._predict()

    def _predict(self):
        cfg = regs.unpack_cfg0(self.shadow[regs.CFG0])
        xfer = QspiXfer()
        xfer.sck_mode = cfg["sck_mode"]
        xfer.endian = cfg["endian"]
        xfer.dir_write = cfg["dir_write"]

        # command phase: skipped entirely when CRM is locked in
        xfer.has_cmd = not self.crm_locked
        if xfer.has_cmd:
            if cfg["cmd_mode"] == 0:
                # FSM still passes through COMMAND for one SCK cycle, tristated
                xfer.dead_cmd_cycle = True
                xfer.cmd = None
            else:
                xfer.cmd = self.shadow[regs.CMD] & 0xFF
                xfer.cmd_lanes = regs.lanes(cfg["cmd_mode"])

        # address phase
        if cfg["addr_mode"] != 0:
            xfer.addr_bytes = 4 if cfg["addr_len4"] else 3
            mask = (1 << (8 * xfer.addr_bytes)) - 1
            xfer.addr = self.shadow[regs.ADDR] & mask
            xfer.addr_lanes = regs.lanes(cfg["addr_mode"])

        # mode byte phase: only when CRM requested or already locked
        if self.crm_locked or cfg["crm"]:
            xfer.mode_byte = (self.shadow[regs.CMD] >> 8) & 0xFF

        xfer.dummy = cfg["dummy"]

        # data phase
        if cfg["data_mode"] != 0:
            xfer.data_lanes = regs.lanes(cfg["data_mode"])
            xfer.dlen = self.shadow[regs.DLEN]
            if cfg["dir_write"]:
                nwords = math.ceil(xfer.dlen / 4)
                words, self.pending_tx = self.pending_tx[:nwords], self.pending_tx[nwords:]
                if len(words) < nwords:
                    self.logger.warning(
                        f"START with only {len(words)}/{nwords} TX words pushed (underrun expected)"
                    )
                xfer.data = regs.words_to_bytes(words, xfer.dlen, cfg["endian"])

        # CRM state update mirrors: crm_active <= qspi_crm_i at transfer done
        self.crm_locked = bool(cfg["crm"])

        self.logger.info(f"predicted {xfer}")
        self.last_xfer = xfer
        self.shape_q.put_nowait(xfer)
        self.expected_ap.write(xfer)
