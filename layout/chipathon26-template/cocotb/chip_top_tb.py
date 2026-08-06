# SPDX-FileCopyrightText: © 2025 Project Template Contributors
# SPDX-License-Identifier: Apache-2.0

import os
import random
import shutil
import logging
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.queue import Queue
from cocotb.triggers import Timer, Edge, RisingEdge, FallingEdge, ClockCycles
from cocotb_tools.runner import get_runner

from a09_tb_func import *

sim = os.getenv("SIM", "icarus")
pdk_root = os.getenv("PDK_ROOT", Path("~/.ciel").expanduser())
pdk = os.getenv("PDK", "gf180mcuD")
scl = os.getenv("SCL", "gf180mcu_fd_sc_mcu7t5v0")
gl = os.getenv("GL", False)
slot = os.getenv("SLOT", "workshop")

async def set_defaults(dut):
    """Set default values for DUT inputs."""
    dut.uart_rx_i.value = 1
    dut.clk_i.value = 0
    dut.rst_ni.value = 1

async def enable_power(dut):
    dut.VDD.value = 1
    dut.VSS.value = 0

async def start_clock(clock, freq=50e6):
    """Start the clock @ freq MHz"""
    c = Clock(clock, 1e9 // freq, "ns")
    cocotb.start_soon(c.start())

async def reset(reset, active_low=True, time_ns=1000):
    """Reset dut"""
    cocotb.log.info("Reset asserted...")

    reset.value = not active_low
    await Timer(time_ns, "ns")
    reset.value = active_low

    cocotb.log.info("Reset deasserted.")

async def start_up(dut, flash_setup_time_us=3000):
    """Startup sequence"""
    await set_defaults(dut)
    if gl:
        await enable_power(dut)
    await start_clock(dut.clk_i)
    await reset(dut.rst_ni, time_ns=15000) 

    rx_queue = Queue()
    cocotb.start_soon(uart_rx_monitor(dut, rx_queue))

    # Wait for flash setup time
    cocotb.log.info(f"Waiting for flash setup time: {flash_setup_time_us} us...")
    await Timer(flash_setup_time_us, unit="us")
    await RisingEdge(dut.clk_i)

    return rx_queue


@cocotb.test(timeout_time=1, timeout_unit="ms")
async def test_csr_read_write(dut):
    """Sanity test reading and writing to CSRs via UART."""
    logger = logging.getLogger("my_testbench")
    logger.info("Startup sequence...")

    rx_queue = await start_up(dut, flash_setup_time_us=10)

    # Example CSR address and data
    test_addr = QSPI_TIMEOUT
    test_data = 0xDEADBEEF

    await csr_write(dut, rx_queue, test_addr, test_data)
    read_data = await csr_read(dut, rx_queue, test_addr)
    assert read_data == test_data, f"CSR Read/Write Mismatch: wrote 0x{test_data:08X}, read 0x{read_data:08X}"

    logger.info("Done!")

# @cocotb.test(timeout_time=5, timeout_unit="ms")
async def test_qspi_rdid(dut):
    """Test standard QSPI Read ID (RDID 0x9F) sequence."""
    logger = logging.getLogger("my_testbench")
    logger.info("Startup sequence...")

    rx_queue = await start_up(dut)

    logger.info("Starting SPI RDID (0x9F) Test...")

    for i in range(1):  # Test both flash chips (CS0 and CS1)
        logger.info(f"Testing RDID for the flash chip (CS{i})...")

        # Setup CFG0: Single CMD, Single Data, Direction=Read, No Address, No Dummies
        cfg0 = build_cfg0(cmd_mode=1, data_mode=1, data_dir=0, cs_num=i, prescaler=1)
        await csr_write(dut, rx_queue, QSPI_CFG0, cfg0)

        # Setup Command (0x9F) and Data Length (3 bytes for standard JEDEC ID)
        await csr_write(dut, rx_queue, QSPI_CMD, 0x9F)
        await csr_write(dut, rx_queue, QSPI_DLEN, 3)

        # Pulse START in QSPI_CTRL
        await csr_write(dut, rx_queue, QSPI_CTRL, 0x01) 

        # Wait for completion
        await qspi_wait_idle(dut, rx_queue)

        # Pop data from FIFO
        rdid_data = await csr_read(dut, rx_queue, QSPI_DR)
        
        logger.info(f"RDID Raw Data Received: 0x{rdid_data:08X}")

@cocotb.test(timeout_time=10, timeout_unit="ms")
async def test_qspi_program_read(dut):
    """Test standard Page Program (0x02) followed by Normal Read (0x03)."""
    logger = logging.getLogger("my_testbench")
    logger.info("Startup sequence...")

    rx_queue = await start_up(dut)

    target_addr = 0x001000  # Example 24-bit flash address
    target_data = 0xCAFEBABE
    
    # --- PHASE 1: Write Enable (0x06) ---
    logger.info("--- Phase 1: Sending Write Enable (0x06) ---")
    cfg0_we = build_cfg0(cmd_mode=1, prescaler=1) # Command only
    await csr_write(dut, rx_queue, QSPI_CFG0, cfg0_we)
    await csr_write(dut, rx_queue, QSPI_CMD, 0x06)
    await csr_write(dut, rx_queue, QSPI_DLEN, 0)
    
    await csr_write(dut, rx_queue, QSPI_CTRL, 0x01)
    await qspi_wait_idle(dut, rx_queue)

    # --- PHASE 2: Page Program (0x02) ---
    logger.info(f"--- Phase 2: Page Program (0x02) to Addr 0x{target_addr:06X} ---")
    # Single CMD, Single ADDR, Single DATA, Write direction (data_dir=1), 3-byte addr (addr_len=0)
    cfg0_prog = build_cfg0(cmd_mode=1, addr_mode=1, data_mode=1, data_dir=1, addr_len=0, prescaler=1)
    await csr_write(dut, rx_queue, QSPI_CFG0, cfg0_prog)
    await csr_write(dut, rx_queue, QSPI_CMD, 0x02)
    await csr_write(dut, rx_queue, QSPI_ADDR, target_addr)
    await csr_write(dut, rx_queue, QSPI_DLEN, 4) # Writing 4 bytes
    
    # Push data into TX FIFO
    await csr_write(dut, rx_queue, QSPI_DR, target_data)
    
    await csr_write(dut, rx_queue, QSPI_CTRL, 0x01)
    await qspi_wait_idle(dut, rx_queue)

    # Poll flash until it's ready
    await flash_poll_busy(dut, rx_queue, prescaler=1)

    # --- PHASE 3: Normal Read (0x03) ---
    logger.info(f"--- Phase 3: Normal Read (0x03) from Addr 0x{target_addr:06X} ---")
    # Single CMD, Single ADDR, Single DATA, Read direction (data_dir=0)
    cfg0_read = build_cfg0(cmd_mode=1, addr_mode=1, data_mode=1, data_dir=0, addr_len=0, prescaler=1)
    await csr_write(dut, rx_queue, QSPI_CFG0, cfg0_read)
    await csr_write(dut, rx_queue, QSPI_CMD, 0x03)
    await csr_write(dut, rx_queue, QSPI_ADDR, target_addr)
    await csr_write(dut, rx_queue, QSPI_DLEN, 4)
    
    await csr_write(dut, rx_queue, QSPI_CTRL, 0x01)
    await qspi_wait_idle(dut, rx_queue)

    # Pop data from RX FIFO
    read_data = await csr_read(dut, rx_queue, QSPI_DR)
    logger.info(f"Read Data Received: 0x{read_data:08X}")
    
    assert read_data != 0xFFFFFFFF, "Read data is all 1's, indicating a failed read or unprogrammed flash."
    assert read_data == target_data, f"Data Mismatch: wrote 0x{target_data:08X}, read 0x{read_data:08X}"


def chip_top_runner():
    proj_path = Path(__file__).resolve().parent
    sim_build_dir = proj_path / "sim_build"
    if sim_build_dir.exists():
        shutil.rmtree(sim_build_dir)

    sdf_corner = "max_ss_125C_4v50"
    top_macro = "a09_chipathon26_top"

    sources = []
    defines = {f"SLOT_{slot.upper()}": True}
    includes = [proj_path / "../src/"]

    rtl_dir = proj_path / "../../../rtl/"
    mem_dir = proj_path / "../../../sim/srcs/"

    build_args = []
    plusargs = []
    sdf_paths = []

    if gl:
        # SCL models
        sources.append(Path(pdk_root) / pdk / "libs.ref" / scl / "verilog" / f"{scl}.v")
        sources.append(Path(pdk_root) / pdk / "libs.ref" / scl / "verilog" / "primitives.v")

        # We use the powered netlist
        sources.append(proj_path / f"../final/pnl/chip_top.pnl.v")
        sources.append(proj_path / f"../macros/{top_macro}/final/pnl/{top_macro}.pnl.v")

        defines["FUNCTIONAL"] = True
        defines["USE_POWER_PINS"] = True
        defines["GL_SIM"] = True

        top_sdf = proj_path / f"../final/sdf/{sdf_corner}/chip_top__{sdf_corner}.sdf"
        macro_sdf = proj_path / f"../macros/{top_macro}/final/sdf/{sdf_corner}/{top_macro}__{sdf_corner}.sdf"

        if top_sdf.exists():
            sdf_paths.append(top_sdf)
            defines.pop("FUNCTIONAL", None) # Turn off functional for timing simulation
        if macro_sdf.exists():
            sdf_paths.append(macro_sdf)

    else:
        defines["USE_POWER_PINS"] = True

        sources.append(proj_path / "../src/chip_top.sv")
        sources.append(proj_path / "../src/chip_core.sv")
        sources.append(proj_path / f"../macros/{top_macro}/{top_macro}.sv")
        sources.append(rtl_dir / "qspi_master.sv")
        sources.append(rtl_dir / "fifo.sv")
        sources.append(rtl_dir / "uart_simple.sv")
        sources.append(rtl_dir / "apb_qspi.sv")
        sources.append(rtl_dir / "uart_to_apb.sv")

    sources += [
        # IO pad models
        Path(pdk_root) / pdk / "libs.ref/gf180mcu_fd_io/verilog/gf180mcu_fd_io.v",
        Path(pdk_root) / pdk / "libs.ref/gf180mcu_fd_io/verilog/gf180mcu_ws_io.v",
        
        # SRAM macros
        Path(pdk_root) / pdk / "libs.ref/gf180mcu_fd_ip_sram/verilog/gf180mcu_fd_ip_sram__sram512x8m8wm1.v",
        
        # Custom IP
        proj_path / "../ip/gf180mcu_ws_ip__id/vh/gf180mcu_ws_ip__id.v",
        proj_path / "../ip/gf180mcu_ws_ip__logo/vh/gf180mcu_ws_ip__logo.v",

        # Memory models
        mem_dir / "23LC1024/23LC1024.v",
        mem_dir / "MX25L51245G/MX25L51245G.v",
        mem_dir / "S25FL128S/s25fl128s.v",
        mem_dir / "W25QxxNE_Family_v1.0n/W25QxxNExxIx_v1.0n.v",

        # Testbench
        proj_path / f"chip_top_tb.sv",
    ]

    if sim == "icarus":
        # For debugging
        # build_args += ["-Winfloop", "-pfileline=1"]
        pass

    if sim == "verilator":
        build_args += ["--timing", "--trace", "--trace-fst", "--trace-structs"]

    if sim == "questa":
        # vlog compilation options
        build_args += ["-mfcu", "-incr", "+acc", "-timescale", "1ns/1ps"]

        if gl:
            # vsim runtime simulation options
            plusargs += [
                "-t", "1ps",               # Ensure 1ps resolution for SDF delays
                "-suppress", "3448,2718,2685", # Suppress specific warnings
                "+multisource_int_delays", # Enable multisource interconnect handling
                "+sdf_verbose",            # Verbose SDF annotation output
                "+specify",                # Enable specify block timing checks
                "+transport_int_delays",   # Transport delay mode for interconnects
                "+transport_path_delays",  # Transport delay mode for gate paths
            ]
            
            # Map SDF files to target module hierarchy
            if len(sdf_paths) > 0 and sdf_paths[0].exists():
                plusargs += ["-sdfmax", f"/chip_top_tb/i_chip_top={sdf_paths[0]}"]


    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="chip_top_tb",
        defines=defines,
        always=True,
        includes=includes,
        build_args=build_args,
        waves=True,
    )

    build_dir = proj_path / "sim_build"
    wildcards = ["*.mem", "*.TXT", "*.txt", "*.bin"]
    
    for pattern in wildcards:
        for filepath in mem_dir.rglob(pattern):
            shutil.copy(filepath, build_dir)
            print(f"Wildcard Match: Copied {filepath.name} to sim_build.")
        
    runner.test(
        hdl_toplevel="chip_top_tb",
        test_module="chip_top_tb,",
        plusargs=plusargs,
        waves=True,
    )


if __name__ == "__main__":
    chip_top_runner()
