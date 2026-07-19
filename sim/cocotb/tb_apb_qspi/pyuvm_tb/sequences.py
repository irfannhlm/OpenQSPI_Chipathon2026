"""Sequences: CSR-level helpers, a flash-command library built on them, and
the four top-level test sequences (APB compliance, SPI compliance, all spec
commands, flash data integrity)."""

import logging
import math
import random

from cocotb.triggers import Timer
from pyuvm import uvm_sequence

import regs
import scoreboards as sb
from seq_items import ApbItem, ApbKind

LOG = logging.getLogger("qspi_seq")

DONE_POLL_LIMIT = 2000  # x 2us pacing = 4ms cap per transfer
WIP_POLL_LIMIT = 1000  # x 20us pacing = 20ms cap per program/erase


class QspiBaseSeq(uvm_sequence):
    """APB access + full-transaction helpers shared by all sequences."""

    def soft_init(self):
        """Soft-check mode: collect failures, keep running, assert at the end
        so a single run gathers evidence for every command."""
        self.fails = []

    def check(self, cond, msg):
        if not hasattr(self, "fails"):
            self.fails = []
        if not cond:
            self.fails.append(msg)
            LOG.error(f"seq check failed: {msg}")

    def final_check(self):
        fails = getattr(self, "fails", [])
        assert not fails, f"{len(fails)} sequence check(s) failed: {fails}"

    async def wr(self, addr, data):
        item = ApbItem(kind=ApbKind.WRITE, addr=addr, data=data)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    async def rd(self, addr):
        item = ApbItem(kind=ApbKind.READ, addr=addr)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    async def xfer(
        self,
        cmd,
        cmd_mode=1,
        addr=None,
        addr_mode=0,
        addr4=0,
        dummy=0,
        data_mode=0,
        dlen=0,
        dir_write=0,
        wdata=b"",
        mode_byte=0,
        crm=0,
        prescaler=0,
        sck_mode=0,
        endian=0,
    ):
        """Run one complete QSPI transaction through the CSR interface.
        Returns read-back bytes for reads, b"" for writes/command-only."""
        cfg = regs.pack_cfg0(
            prescaler=prescaler,
            addr_len4=addr4,
            dummy=dummy,
            cmd_mode=cmd_mode,
            addr_mode=addr_mode if addr is not None else 0,
            data_mode=data_mode,
            sck_mode=sck_mode,
            dir_write=dir_write,
            crm=crm,
            endian=endian,
        )
        await self.wr(regs.CFG0, cfg)
        await self.wr(regs.DLEN, dlen)
        await self.wr(regs.CMD, ((mode_byte & 0xFF) << 8) | (cmd & 0xFF))
        if addr is not None:
            await self.wr(regs.ADDR, addr)

        if dir_write and dlen:
            assert len(wdata) >= dlen, "wdata shorter than dlen"
            for w in regs.bytes_to_words(wdata[:dlen], endian):
                await self.wr(regs.DR, w)

        await self.wr(regs.CTRL, regs.CTRL_START)

        # wait for completion
        ctrl = 0
        for _ in range(DONE_POLL_LIMIT):
            ctrl = (await self.rd(regs.CTRL)).rdata
            if ctrl & regs.CTRL_DONE:
                break
            await Timer(2, unit="us")
        else:
            raise RuntimeError(f"transfer cmd=0x{cmd:02X} never set DONE (CTRL=0x{ctrl:08X})")

        fifo_err = (ctrl >> regs.CTRL_FIFO_ERR_SHIFT) & 0xF
        assert fifo_err == 0, f"unexpected FIFO_ERR=0x{fifo_err:X} after cmd 0x{cmd:02X}"
        await self.wr(regs.CTRL, regs.CTRL_W1C_ALL)

        data = b""
        if not dir_write and data_mode and dlen:
            words = []
            for i in range(math.ceil(dlen / 4)):
                w = (await self.rd(regs.DR)).rdata
                if w is None:
                    self.check(
                        False,
                        f"DR pop {i + 1}/{math.ceil(dlen / 4)} after cmd 0x{cmd:02X} "
                        f"returned X (FIFO underflow - word never pushed)",
                    )
                    w = 0
                words.append(w)
            # underflow shows up in FIFO_ERR as an RX-empty pop
            ctrl = (await self.rd(regs.CTRL)).rdata
            fifo_err = (ctrl >> regs.CTRL_FIFO_ERR_SHIFT) & 0xF
            if fifo_err:
                self.check(
                    False, f"FIFO_ERR=0x{fifo_err:X} while popping read data of cmd 0x{cmd:02X}"
                )
                await self.wr(regs.CTRL, regs.CTRL_W1C_ALL)
            data = regs.words_to_bytes(words, dlen, endian)

        await Timer(200, unit="ns")  # CSn deselect gap
        return data

    # --- flash command library (S25FL128S, 3-byte addressing) ---

    async def cmd_only(self, opcode):
        await self.xfer(opcode)

    async def read_reg(self, opcode, nbytes=1, dummy=0):
        return await self.xfer(opcode, dummy=dummy, data_mode=1, dlen=nbytes)

    async def rdsr1(self):
        return (await self.read_reg(sb.CMD_RDSR1))[0]

    async def poll_wip(self):
        for _ in range(WIP_POLL_LIMIT):
            if (await self.rdsr1()) & 0x01 == 0:
                return
            await Timer(20, unit="us")
        raise RuntimeError("flash WIP never cleared")

    async def ensure_qe(self):
        """Set the Quad Enable bit (CR1[1]) via WRR if not already set.
        Returns True when QE is confirmed set."""
        cr = (await self.read_reg(sb.CMD_RDCR))[0]
        if cr & 0x02:
            return True
        await self.cmd_only(sb.CMD_WREN)
        await self.xfer(sb.CMD_WRR, data_mode=1, dlen=2, dir_write=1, wdata=bytes([0x00, 0x02]))
        await self.poll_wip()
        cr = (await self.read_reg(sb.CMD_RDCR))[0]
        self.check(cr & 0x02, f"QE bit did not set via WRR (RDCR=0x{cr:02X})")
        return bool(cr & 0x02)

    async def flash_read(self, opcode, addr, nbytes, addr_mode=1, dummy=0, data_mode=1, **kw):
        return await self.xfer(
            opcode, addr=addr, addr_mode=addr_mode, dummy=dummy,
            data_mode=data_mode, dlen=nbytes, **kw
        )

    async def flash_program(self, opcode, addr, data, data_mode=1):
        await self.cmd_only(sb.CMD_WREN)
        await self.xfer(
            opcode, addr=addr, addr_mode=1, data_mode=data_mode,
            dlen=len(data), dir_write=1, wdata=data
        )
        await self.poll_wip()

    async def sector_erase(self, addr):
        await self.cmd_only(sb.CMD_WREN)
        await self.xfer(sb.CMD_SE, addr=addr, addr_mode=1)
        await self.poll_wip()


class CsrComplianceSeq(QspiBaseSeq):
    """APB protocol compliance: reset values, random write/readback, W1C
    semantics, FIFO error reporting, and pready stall-while-busy."""

    async def body(self):
        rng = random.Random(0xC0FFEE)

        # reset values
        for off in (regs.CFG0, regs.DLEN, regs.CMD, regs.ADDR, regs.TIMEOUT):
            v = (await self.rd(off)).rdata
            assert v == 0, f"reg 0x{off:02X} reset value 0x{v:08X} != 0"
        ctrl = (await self.rd(regs.CTRL)).rdata
        assert ctrl & (regs.CTRL_BUSY | regs.CTRL_DONE | regs.CTRL_FIFO_ERR_MASK) == 0

        # random write/readback (registers store the full 32-bit word)
        for _ in range(30):
            off = rng.choice([regs.CFG0, regs.DLEN, regs.CMD, regs.ADDR, regs.TIMEOUT])
            val = rng.getrandbits(32)
            await self.wr(off, val)
            got = (await self.rd(off)).rdata
            assert got == val, f"reg 0x{off:02X}: wrote 0x{val:08X}, read 0x{got:08X}"

        # BCNT is read-only: write must not stick
        await self.wr(regs.BCNT, 0xDEADBEEF)
        got = (await self.rd(regs.BCNT)).rdata
        assert got != 0xDEADBEEF, "BCNT accepted a write (should be read-only)"

        # FIFO error: read DR while empty in read direction -> RX_EMPTY
        await self.wr(regs.CFG0, regs.pack_cfg0(dir_write=0))
        await self.wr(regs.CTRL, regs.CTRL_FLUSH)
        await self.rd(regs.DR)
        err = ((await self.rd(regs.CTRL)).rdata >> regs.CTRL_FIFO_ERR_SHIFT) & 0xF
        assert err == regs.FIFO_ERR_RX_EMPTY, f"expected RX_EMPTY error, got 0x{err:X}"
        await self.wr(regs.CTRL, regs.CTRL_W1C_ALL)

        # FIFO error: read DR in write direction -> WRONG_DIR
        await self.wr(regs.CFG0, regs.pack_cfg0(dir_write=1))
        await self.rd(regs.DR)
        err = ((await self.rd(regs.CTRL)).rdata >> regs.CTRL_FIFO_ERR_SHIFT) & 0xF
        assert err == regs.FIFO_ERR_WRONG_DIR, f"expected WRONG_DIR error, got 0x{err:X}"
        await self.wr(regs.CTRL, regs.CTRL_W1C_ALL)

        # FIFO error: push 64 words (fills), 65th -> TX_FULL
        for i in range(64):
            await self.wr(regs.DR, i)
        await self.wr(regs.DR, 0xFFFF_FFFF)
        err = ((await self.rd(regs.CTRL)).rdata >> regs.CTRL_FIFO_ERR_SHIFT) & 0xF
        assert err == regs.FIFO_ERR_TX_FULL, f"expected TX_FULL error, got 0x{err:X}"
        await self.wr(regs.CTRL, regs.CTRL_W1C_ALL)
        await self.wr(regs.CTRL, regs.CTRL_FLUSH)

        # config writes stall (pready wait states) while a transfer is busy
        await self.wr(regs.CFG0, regs.pack_cfg0(prescaler=4, cmd_mode=1, addr_mode=1, data_mode=1))
        await self.wr(regs.DLEN, 16)
        await self.wr(regs.CMD, sb.CMD_READ)
        await self.wr(regs.ADDR, 0)
        await self.wr(regs.CTRL, regs.CTRL_START)
        busy = (await self.rd(regs.CTRL)).rdata & regs.CTRL_BUSY
        assert busy, "BUSY not set right after START"
        item = await self.wr(regs.DLEN, 16)  # config write while busy must stall
        assert item.wait_states > 0, "config write while BUSY did not stall pready"
        for _ in range(DONE_POLL_LIMIT):
            if (await self.rd(regs.CTRL)).rdata & regs.CTRL_DONE:
                break
            await Timer(2, unit="us")
        await self.wr(regs.CTRL, regs.CTRL_W1C_ALL)
        for _ in range(4):  # drain the 16-byte read
            await self.rd(regs.DR)

        # restore a clean state
        await self.wr(regs.TIMEOUT, 0)
        await self.wr(regs.CTRL, regs.CTRL_FLUSH)
        self.final_check()


class SpiModesSeq(QspiBaseSeq):
    """SPI protocol compliance across every supported lane/mode combination,
    with per-mode variations: SPI mode 3, endianness, 4-byte addressing (via
    the flash's 4B opcodes), non-word-aligned length; plus one FIFO-full SCK
    pause test and one software abort test. Data content at address 0 is
    unknown, so variants are cross-checked against the base read of the same
    location; shape/address checks live in the monitor + scoreboard."""

    async def run_read_variants(self, name, opcode, opcode4, addr_mode, dummy, data_mode):
        base = await self.flash_read(
            opcode, 0x000000, 8, addr_mode=addr_mode, dummy=dummy, data_mode=data_mode
        )
        LOG.info(f"{name}: {base.hex()}")

        # SCK mode variation (mode 3: CPOL=1, CPHA=1)
        v = await self.flash_read(
            opcode, 0x000000, 8, addr_mode=addr_mode, dummy=dummy, data_mode=data_mode, sck_mode=1
        )
        self.check(v == base, f"{name} mode3: {v.hex()} != base {base.hex()}")

        # endian variation (DR packing only; wire data identical)
        v = await self.flash_read(
            opcode, 0x000000, 8, addr_mode=addr_mode, dummy=dummy, data_mode=data_mode, endian=1
        )
        self.check(v == base, f"{name} little-endian: {v.hex()} != base {base.hex()}")

        # address length variation (4-byte opcode + addr_len=1)
        if opcode4 is not None:
            v = await self.flash_read(
                opcode4, 0x000000, 8, addr_mode=addr_mode, dummy=dummy,
                data_mode=data_mode, addr4=1
            )
            self.check(v == base, f"{name} 4B-addr: {v.hex()} != base {base.hex()}")

        # non-word-aligned length (partial final DR word)
        v = await self.flash_read(
            opcode, 0x000000, 7, addr_mode=addr_mode, dummy=dummy, data_mode=data_mode
        )
        self.check(v == base[:7], f"{name} dlen=7: {v.hex()} != base[:7] {base[:7].hex()}")

    async def _start_read(self, dlen, prescaler=0):
        """Configure and START a x1 READ without waiting for completion."""
        await self.wr(regs.CFG0, regs.pack_cfg0(
            prescaler=prescaler, cmd_mode=1, addr_mode=1, data_mode=1))
        await self.wr(regs.DLEN, dlen)
        await self.wr(regs.CMD, sb.CMD_READ)
        await self.wr(regs.ADDR, 0)
        await self.wr(regs.CTRL, regs.CTRL_START)

    async def pause_test(self):
        """Read more than the FIFO holds (64 words) without popping: the DUT
        must pause SCK on FIFO-full at a word boundary and resume when
        software drains, with an exact total edge count (scoreboard checks)."""
        dlen = 264  # 66 words; FIFO full pauses the byte-259 boundary
        await self._start_read(dlen)
        await Timer(150, unit="us")  # transfer fills the FIFO and hits the pause
        busy = (await self.rd(regs.CTRL)).rdata & regs.CTRL_BUSY
        self.check(busy, "pause test: transfer should still be in flight while FIFO is full")

        words = []
        for _ in range(64):  # drain the full FIFO; transfer resumes
            words.append((await self.rd(regs.DR)).rdata)
        for _ in range(DONE_POLL_LIMIT):
            if (await self.rd(regs.CTRL)).rdata & regs.CTRL_DONE:
                break
            await Timer(2, unit="us")
        else:
            raise RuntimeError("pause test: transfer never completed after draining FIFO")
        for _ in range(2):  # remaining words
            words.append((await self.rd(regs.DR)).rdata)

        ctrl = (await self.rd(regs.CTRL)).rdata
        fifo_err = (ctrl >> regs.CTRL_FIFO_ERR_SHIFT) & 0xF
        self.check(fifo_err == 0, f"pause test: FIFO_ERR=0x{fifo_err:X} during paced drain")
        await self.wr(regs.CTRL, regs.CTRL_W1C_ALL)
        data = regs.words_to_bytes([w if w is not None else 0 for w in words], dlen)
        LOG.info(f"pause test read {dlen}B, first 8: {data[:8].hex()}")
        await Timer(200, unit="ns")

    async def abort_test(self):
        """Abort a slow read mid-flight: DONE must still assert, the partial
        wire transaction is accepted (predictor marks it aborted)."""
        await self._start_read(64, prescaler=4)
        await Timer(10, unit="us")  # well inside the ~41us transfer
        await self.wr(regs.CTRL, regs.CTRL_ABORT)
        for _ in range(DONE_POLL_LIMIT):
            if (await self.rd(regs.CTRL)).rdata & regs.CTRL_DONE:
                break
            await Timer(1, unit="us")
        else:
            raise RuntimeError("abort test: DONE never asserted after ABORT")
        await self.wr(regs.CTRL, regs.CTRL_W1C_ALL)
        await self.wr(regs.CTRL, regs.CTRL_FLUSH)  # discard partial RX words
        await Timer(200, unit="ns")

    async def body(self):
        self.soft_init()

        # (name, opcode, 4-byte opcode, addr_mode, dummy, data_mode)
        modes = [
            ("READ 1-1-1", sb.CMD_READ, 0x13, 1, 0, 1),
            ("FAST_READ 1-1-1", sb.CMD_FAST_READ, 0x0C, 1, 8, 1),
            ("DOR 1-1-2", sb.CMD_DOR, 0x3C, 1, 8, 2),
            ("DIOR 1-2-2", sb.CMD_DIOR, 0xBC, 2, 4, 2),
        ]
        quad_modes = [
            ("QOR 1-1-4", sb.CMD_QOR, 0x6C, 1, 8, 3),
            ("QIOR 1-4-4", 0xEB, 0xEC, 3, 6, 3),
        ]

        # prescaler coverage (base mode only)
        data = await self.flash_read(sb.CMD_READ, 0x000000, 8, prescaler=3)
        LOG.info(f"READ presc3: {data.hex()}")

        # address integrity probe: nonzero mid/low address bytes so a dropped
        # or zeroed address byte can't hide (scoreboard compares wire address)
        data = await self.flash_read(sb.CMD_READ, 0x000102, 8)
        LOG.info(f"READ @0x000102: {data.hex()}")

        for mode in modes:
            await self.run_read_variants(*mode)

        if await self.ensure_qe():
            for mode in quad_modes:
                await self.run_read_variants(*mode)
        else:
            LOG.error("skipping quad modes: QE could not be set")

        await self.pause_test()
        await self.abort_test()

        self.final_check()


class AllCommandsSeq(QspiBaseSeq):
    """Every command required by the competition spec, end to end against the
    S25FL128S model, with data checks where the result is deterministic."""

    SECTOR = 0x040000

    async def body(self):
        self.soft_init()

        # WREN / WRDI observable through RDSR1.WEL
        await self.cmd_only(sb.CMD_WREN)
        self.check((await self.rdsr1()) & 0x02, "WEL did not set after WREN")
        await self.cmd_only(sb.CMD_WRDI)
        self.check(not (await self.rdsr1()) & 0x02, "WEL did not clear after WRDI")

        # ID commands (values fixed by the flash model; stay within the bytes
        # the model actually drives - beyond them SO floats)
        rdid = await self.read_reg(sb.CMD_RDID, nbytes=4)
        self.check(rdid[:3] == sb.JEDEC_ID, f"RDID returned {rdid.hex()}")
        rems = await self.flash_read(sb.CMD_REMS, 0x000000, 2)
        self.check(rems == bytes([0x01, 0x17]), f"REMS returned {rems.hex()}")
        res = await self.read_reg(sb.CMD_RES, nbytes=1, dummy=24)
        self.check(res[0] == 0x17, f"RES returned 0x{res[0]:02X}")

        # status/config register reads
        sr2 = await self.read_reg(sb.CMD_RDSR2)
        cr = await self.read_reg(sb.CMD_RDCR)
        LOG.info(f"RDSR2=0x{sr2[0]:02X} RDCR=0x{cr[0]:02X}")

        # x1-only flow first (not blocked by QE): SE + erased read-back
        await self.sector_erase(self.SECTOR)
        data = await self.flash_read(sb.CMD_READ, self.SECTOR, 16)
        self.check(data == b"\xff" * 16, f"post-erase read: {data.hex()}")

        # PP + READ
        pattern_a = bytes(range(0xA0, 0xB0))
        await self.flash_program(sb.CMD_PP, self.SECTOR, pattern_a)
        data = await self.flash_read(sb.CMD_READ, self.SECTOR, len(pattern_a))
        self.check(data == pattern_a, f"PP/READ mismatch: {data.hex()} != {pattern_a.hex()}")

        # WRR (sets QE), then QPP + QOR if quad is available
        if await self.ensure_qe():
            pattern_b = bytes((~b) & 0xFF for b in pattern_a)
            await self.flash_program(sb.CMD_QPP, self.SECTOR + 0x100, pattern_b, data_mode=3)
            data = await self.flash_read(
                sb.CMD_QOR, self.SECTOR + 0x100, len(pattern_b), dummy=8, data_mode=3
            )
            self.check(data == pattern_b, f"QPP/QOR mismatch: {data.hex()} != {pattern_b.hex()}")
        else:
            LOG.error("skipping QPP/QOR: QE could not be set")

        # CLSR and software RESET
        await self.cmd_only(sb.CMD_CLSR)
        await self.cmd_only(sb.CMD_RESET)
        await Timer(50, unit="us")  # tRPH recovery
        rdid = await self.read_reg(sb.CMD_RDID, nbytes=3)
        self.check(rdid == sb.JEDEC_ID, f"RDID after RESET returned {rdid.hex()}")

        self.final_check()


class FlashDataSeq(QspiBaseSeq):
    """Randomized program/read data integrity against the flash model, in x1
    and x4, cross-checked by the golden memory model in the scoreboard."""

    SECTOR = 0x050000

    async def body(self):
        self.soft_init()
        rng = random.Random(0x5EED)
        await self.sector_erase(self.SECTOR)

        # x1 rounds (not blocked by QE)
        for i in range(2):
            base = self.SECTOR + i * 0x200
            pat = bytes(rng.getrandbits(8) for _ in range(32))
            await self.flash_program(sb.CMD_PP, base, pat)
            got = await self.flash_read(sb.CMD_READ, base, len(pat))
            self.check(got == pat, f"x1 round {i}: {got.hex()} != {pat.hex()}")

        # x4 rounds
        if await self.ensure_qe():
            for i in range(2):
                base = self.SECTOR + i * 0x200 + 0x100
                pat4 = bytes(rng.getrandbits(8) for _ in range(32))
                await self.flash_program(sb.CMD_QPP, base, pat4, data_mode=3)
                got = await self.flash_read(sb.CMD_QOR, base, len(pat4), dummy=8, data_mode=3)
                self.check(got == pat4, f"x4 round {i}: {got.hex()} != {pat4.hex()}")
        else:
            LOG.error("skipping x4 rounds: QE could not be set")

        self.final_check()
