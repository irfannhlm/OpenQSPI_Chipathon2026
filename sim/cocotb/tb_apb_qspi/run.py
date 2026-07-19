"""Windows-friendly runner (no make needed): python run.py [-t TEST] [--waves]

Equivalent to the Makefile flow; uses cocotb's Python runner with icarus.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

from cocotb_tools.runner import get_runner

TB_DIR = Path(__file__).parent.resolve()
RTL = TB_DIR / ".." / ".." / ".." / "rtl"
FLASH = TB_DIR / ".." / ".." / "srcs" / "S25FL128S"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-t", "--test", help="run a single test class (e.g. ApbComplianceTest)")
    ap.add_argument("--waves", action="store_true", help="dump apb_qspi_waves.vcd")
    args = ap.parse_args()

    build_dir = TB_DIR / "sim_build"
    runner = get_runner("icarus")
    runner.build(
        sources=[
            TB_DIR / "tb_apb_qspi.sv",
            RTL / "fifo.sv",
            RTL / "qspi_master.sv",
            RTL / "apb_qspi.sv",
            FLASH / "s25fl128s.v",
        ],
        hdl_toplevel="tb_apb_qspi",
        defines={"SPEEDSIM": ""},
        includes=[RTL, FLASH],
        build_args=["-pfileline=1", "-Wno-timescale"],
        build_dir=str(build_dir),
        always=True,
        waves=args.waves,
        timescale=("1ns", "1ps"),
    )

    # flash model reads its .mem preload from the working directory
    for mem in FLASH.glob("*.mem"):
        shutil.copy(mem, build_dir / mem.name)

    # the cocotb runner serializes this process's sys.path into the simulator
    # subprocess's PYTHONPATH; putting pyuvm_tb first also keeps our test.py
    # ahead of the python stdlib's own `test` package
    sys.path.insert(0, str(TB_DIR / "pyuvm_tb"))

    results = runner.test(
        hdl_toplevel="tb_apb_qspi",
        test_module="test",
        testcase=args.test,
        waves=args.waves,
        build_dir=str(build_dir),
        test_dir=str(build_dir),
    )
    print(f"results: {results}")


if __name__ == "__main__":
    sys.exit(main())
