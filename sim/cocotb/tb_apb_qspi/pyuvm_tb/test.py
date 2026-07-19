"""pyuvm tests for the apb_qspi wrapper.

Run all four via the Makefile (WSL) or run.py (Windows); select one with
COCOTB_TESTCASE=<TestClassName>.
"""

import os

import cocotb
import pyuvm
from cocotb.queue import Queue
from cocotb.triggers import Timer
from pyuvm import ConfigDB, uvm_test

from agent_env import QspiEnv
from bfm import ApbBfm
from sequences import AllCommandsSeq, CsrComplianceSeq, FlashDataSeq, SpiModesSeq


class QspiBaseTest(uvm_test):
    SEQ = None

    def build_phase(self):
        self.bfm = ApbBfm(cocotb.top)
        ConfigDB().set(None, "*", "BFM", self.bfm)
        ConfigDB().set(None, "*", "SHAPE_Q", Queue())
        # debug/behavior knobs (env vars so no source edits needed)
        ConfigDB().set(None, "*", "WAIVE_KNOWN_ISSUES", os.environ.get("WAIVERS", "1") == "1")
        ConfigDB().set(None, "*", "FIFO_PROBE", os.environ.get("FIFO_PROBE", "0") == "1")
        self.env = QspiEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        await self.bfm.startup()
        seq = self.SEQ("seq")
        await seq.start(self.env.agent.seqr)
        await Timer(5, unit="us")  # let monitors/scoreboard drain
        self.drop_objection()


@pyuvm.test(timeout_time=20, timeout_unit="ms")
class ApbComplianceTest(QspiBaseTest):
    """APB protocol compliance: reset values, readback, W1C, FIFO errors,
    stall-while-busy. The ApbMonitor asserts bus rules in every test."""

    SEQ = CsrComplianceSeq


@pyuvm.test(timeout_time=40, timeout_unit="ms")
class SpiComplianceTest(QspiBaseTest):
    """SPI protocol compliance across x1/x2/x4 lane combinations, SPI mode 0
    and mode 3, and prescaler variation."""

    SEQ = SpiModesSeq


@pyuvm.test(timeout_time=100, timeout_unit="ms")
class AllCommandsTest(QspiBaseTest):
    """Every flash command the competition spec requires, run end to end
    against the S25FL128S model."""

    SEQ = AllCommandsSeq


@pyuvm.test(timeout_time=100, timeout_unit="ms")
class FlashModelTest(QspiBaseTest):
    """Randomized program/read data integrity against the flash model."""

    SEQ = FlashDataSeq
