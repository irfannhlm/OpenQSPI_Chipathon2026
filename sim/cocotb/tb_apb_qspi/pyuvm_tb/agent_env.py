"""Agent and environment for the apb_qspi pyuvm testbench."""

from pyuvm import uvm_agent, uvm_env, uvm_sequencer

from driver import ApbDriver
from monitors import ApbMonitor, QspiMonitor
from predictor import QspiPredictor
from qspi_coverage import QspiCoverage
from scoreboards import QspiScoreboard


class ApbAgent(uvm_agent):
    def build_phase(self):
        self.seqr = uvm_sequencer("seqr", self)
        self.driver = ApbDriver("driver", self)
        self.monitor = ApbMonitor("monitor", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.seqr.seq_item_export)


class QspiEnv(uvm_env):
    def build_phase(self):
        self.agent = ApbAgent("agent", self)
        self.qspi_monitor = QspiMonitor("qspi_monitor", self)
        self.predictor = QspiPredictor("predictor", self)
        self.scoreboard = QspiScoreboard("scoreboard", self)
        self.coverage = QspiCoverage("coverage", self)

    def connect_phase(self):
        # APB traffic feeds the predictor (CSR shadow + expectation builder)
        self.agent.monitor.ap.connect(self.predictor.analysis_export)
        # predictions and observations meet in the scoreboard
        self.predictor.expected_ap.connect(self.scoreboard.expected_fifo.analysis_export)
        self.qspi_monitor.ap.connect(self.scoreboard.actual_fifo.analysis_export)
        # observed transactions also feed functional coverage
        self.qspi_monitor.ap.connect(self.coverage.analysis_export)
