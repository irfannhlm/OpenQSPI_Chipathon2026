"""APB bus functional model for the apb_qspi testbench.

Drives the DUT's APB pins with spec-shaped transfers (setup phase, access
phase, pready wait states) and owns clock/reset/flash-power-up bring-up.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer

CLOCK_PERIOD_NS = 20  # 50 MHz
FLASH_POWERUP_US = 320  # S25FL128S tPU = 300 us (1ps timescale model)
APB_TIMEOUT_CYCLES = 100_000  # give up if pready never rises (DUT deadlock guard)

# module-level state shared across tests in one vvp run: sim time persists,
# so the flash stays powered between cocotb tests (its RSTNeg never toggles)
_flash_powered = False


class ApbBfm:
    def __init__(self, dut):
        self.dut = dut

    async def startup(self):
        """Clock + DUT reset + (first time only) flash power-up wait."""
        global _flash_powered
        dut = self.dut

        # cocotb cancels all tasks between tests, including the clock driver,
        # so each test must start its own
        cocotb.start_soon(Clock(dut.clk_i, CLOCK_PERIOD_NS, unit="ns").start())

        # flash exits reset at t0 and powers up in the background
        dut.flash_rstn_i.value = 1

        # idle APB inputs, reset DUT
        dut.psel_i.value = 0
        dut.penable_i.value = 0
        dut.pwrite_i.value = 0
        dut.paddr_i.value = 0
        dut.pwdata_i.value = 0
        dut.rst_ni.value = 0
        await ClockCycles(dut.clk_i, 10)
        dut.rst_ni.value = 1
        await ClockCycles(dut.clk_i, 10)

        if not _flash_powered:
            await Timer(FLASH_POWERUP_US, unit="us")
            _flash_powered = True

    async def write(self, addr, data):
        """One APB write. Returns the number of wait states endured."""
        dut = self.dut
        await RisingEdge(dut.clk_i)
        dut.psel_i.value = 1
        dut.penable_i.value = 0
        dut.pwrite_i.value = 1
        dut.paddr_i.value = addr
        dut.pwdata_i.value = data
        await RisingEdge(dut.clk_i)
        dut.penable_i.value = 1

        ws = 0
        while True:
            await ReadOnly()
            ready = int(dut.pready_o.value)
            await RisingEdge(dut.clk_i)
            if ready:
                break
            ws += 1
            if ws > APB_TIMEOUT_CYCLES:
                raise RuntimeError(f"APB write to 0x{addr:02X} stuck: pready never rose")

        dut.psel_i.value = 0
        dut.penable_i.value = 0
        dut.pwrite_i.value = 0
        return ws

    async def read(self, addr):
        """One APB read. Returns (rdata, wait_states)."""
        dut = self.dut
        await RisingEdge(dut.clk_i)
        dut.psel_i.value = 1
        dut.penable_i.value = 0
        dut.pwrite_i.value = 0
        dut.paddr_i.value = addr
        await RisingEdge(dut.clk_i)
        dut.penable_i.value = 1

        ws = 0
        while True:
            await ReadOnly()
            ready = int(dut.pready_o.value)
            try:
                rdata = int(dut.prdata_o.value)
            except ValueError:
                rdata = None  # X/Z, e.g. reading QSPI_DR from a never-written FIFO slot
            await RisingEdge(dut.clk_i)
            if ready:
                break
            ws += 1
            if ws > APB_TIMEOUT_CYCLES:
                raise RuntimeError(f"APB read from 0x{addr:02X} stuck: pready never rose")

        dut.psel_i.value = 0
        dut.penable_i.value = 0
        return rdata, ws
