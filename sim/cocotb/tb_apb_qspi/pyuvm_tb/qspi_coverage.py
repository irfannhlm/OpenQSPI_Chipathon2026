"""Functional coverage on the observed QSPI transaction stream.

Samples every transaction the QSPI monitor decodes off the wire (ground
truth, not intent), via cocotb-coverage coverpoints. The database is
cumulative across all tests in one simulation run; each test's report_phase
logs the running totals and rewrites sim_build/coverage.xml / coverage.yml.

Optional dependency: `pip install cocotb-coverage`. Without it the
environment still runs; coverage sampling is skipped with one warning.
"""

from pyuvm import uvm_subscriber

import scoreboards as sb

try:
    from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db

    HAVE_COCOTB_COVERAGE = True
except ImportError:  # keep the env usable on machines without the package
    HAVE_COCOTB_COVERAGE = False

# opcode -> label for the spec command set (plus QIOR 0xEB used by the tests)
CMD_NAMES = {
    sb.CMD_WRR: "WRR", sb.CMD_PP: "PP", sb.CMD_READ: "READ", sb.CMD_WRDI: "WRDI",
    sb.CMD_RDSR1: "RDSR1", sb.CMD_WREN: "WREN", sb.CMD_RDSR2: "RDSR2",
    sb.CMD_FAST_READ: "FAST_READ", sb.CMD_P4E: "P4E", sb.CMD_CLSR: "CLSR",
    sb.CMD_QPP: "QPP", sb.CMD_RDCR: "RDCR", sb.CMD_DOR: "DOR", sb.CMD_QOR: "QOR",
    sb.CMD_REMS: "REMS", sb.CMD_RDID: "RDID", sb.CMD_RES: "RES",
    sb.CMD_DIOR: "DIOR", sb.CMD_SE: "SE", sb.CMD_RESET: "RESET", 0xEB: "QIOR",
    # 4-byte addressing variants exercised by SpiComplianceTest
    0x13: "READ4", 0x0C: "FAST_READ4", 0x3C: "DOR4", 0xBC: "DIOR4",
    0x6C: "QOR4", 0xEC: "QIOR4",
}

CMD_BINS = sorted(set(CMD_NAMES.values())) + ["other", "none"]
DLEN_BINS = ["0", "1", "2-4", "5-8", "9-32", "33-256", ">256"]
DUMMY_BINS = ["0", "1-7", "8", ">8"]
DIR_BINS = ["none", "RD", "WR"]


def _cmd(x):
    if x.cmd is None:
        return "none"
    return CMD_NAMES.get(x.cmd, "other")


def _dlen_bucket(x):
    n = x.dlen if x.data_lanes else 0
    for hi, label in ((0, "0"), (1, "1"), (4, "2-4"), (8, "5-8"),
                      (32, "9-32"), (256, "33-256")):
        if n <= hi:
            return label
    return ">256"


def _dummy_bucket(x):
    if x.dummy == 0:
        return "0"
    if x.dummy < 8:
        return "1-7"
    if x.dummy == 8:
        return "8"
    return ">8"


def _dir(x):
    if x.data_lanes == 0:
        return "none"
    return "WR" if x.dir_write else "RD"


if HAVE_COCOTB_COVERAGE:

    @CoverPoint("qspi.cmd", xf=_cmd, bins=CMD_BINS)
    @CoverPoint("qspi.cmd_lanes", xf=lambda x: x.cmd_lanes if x.cmd is not None else 0,
                bins=[0, 1, 2, 4])
    @CoverPoint("qspi.addr_bytes", xf=lambda x: x.addr_bytes, bins=[0, 3, 4])
    @CoverPoint("qspi.addr_lanes", xf=lambda x: x.addr_lanes if x.addr_bytes else 0,
                bins=[0, 1, 2, 4])
    @CoverPoint("qspi.dir", xf=_dir, bins=DIR_BINS)
    @CoverPoint("qspi.data_lanes", xf=lambda x: x.data_lanes, bins=[0, 1, 2, 4])
    @CoverPoint("qspi.dlen", xf=_dlen_bucket, bins=DLEN_BINS)
    @CoverPoint("qspi.dummy", xf=_dummy_bucket, bins=DUMMY_BINS)
    @CoverPoint("qspi.sck_mode", xf=lambda x: x.sck_mode, bins=[0, 1])
    @CoverPoint("qspi.endian", xf=lambda x: x.endian, bins=[0, 1])
    @CoverPoint("qspi.aborted", xf=lambda x: x.aborted, bins=[False, True])
    @CoverPoint("qspi.mode_phase", xf=lambda x: x.mode_byte is not None,
                bins=[False, True])  # True only once CRM tests exist
    @CoverCross("qspi.dirXdata_lanes", items=["qspi.dir", "qspi.data_lanes"],
                ign_bins=[("none", 1), ("none", 2), ("none", 4),
                          ("RD", 0), ("WR", 0)])
    @CoverCross("qspi.dirXdlen", items=["qspi.dir", "qspi.dlen"],
                ign_bins=[("none", "1"), ("none", "2-4"), ("none", "5-8"),
                          ("none", "9-32"), ("none", "33-256"), ("none", ">256"),
                          ("RD", "0"), ("WR", "0")])
    def _sample(x):
        pass

else:

    def _sample(x):
        pass


class QspiCoverage(uvm_subscriber):
    """Subscribes to the QSPI monitor's analysis port and samples coverage."""

    def build_phase(self):
        self.sampled = 0
        if not HAVE_COCOTB_COVERAGE:
            self.logger.warning(
                "cocotb-coverage not installed - functional coverage disabled "
                "(pip install cocotb-coverage)")

    def write(self, xfer):
        _sample(xfer)
        self.sampled += 1

    def report_phase(self):
        if not HAVE_COCOTB_COVERAGE:
            return
        self.logger.info(f"coverage: {self.sampled} transactions sampled this test")
        coverage_db.report_coverage(self.logger.info, bins=False)
        # cumulative across all tests in this vvp run; last test wins the file
        coverage_db.export_to_xml(filename="coverage.xml")
        coverage_db.export_to_yaml(filename="coverage.yml")
