import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge

CLOCK_FREQ = 50e6  # 50 MHz
STARTUP_TIME = 4e-3  # 4ms; exceeds the MX25L tVSL power-up gate

class Scoreboard:
    """Tracks passed/failed transactions to provide a summary at the end of the simulation."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = {}

    def record(self, target_name, mode_name, passed, error_msg=""):
        if target_name not in self.results:
            self.results[target_name] = []
            
        self.results[target_name].append({
            "mode": mode_name, 
            "passed": passed, 
            "error": error_msg
        })
        
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    def report(self, log):
        log.info("==================================================")
        log.info(f" 🏆 SIMULATION SCOREBOARD: {self.passed} PASSED, {self.failed} FAILED")
        log.info("==================================================")
        for target, tests in self.results.items():
            log.info(f" {target}:")
            for test in tests:
                if test['passed']:
                    log.info(f"   [PASS] {test['mode']}")
                else:
                    log.info(f"   [FAIL] {test['mode']} - {test['error']}")
        log.info("==================================================")


async def init_qspi_master(dut):
    """Initialize the QSPI Master DUT with default values"""
    cocotb.start_soon(Clock(dut.clk_i, 1e9 / CLOCK_FREQ, unit="ns").start())
    
    # Core Control
    dut.rst_ni.value = 0
    dut.qspi_start_i.value = 0
    dut.qspi_abort_i.value = 0

    # Configuration Registers
    dut.qspi_timeout_i.value = int(CLOCK_FREQ*1e-3) # 1ms timeout
    dut.qspi_prescaler_i.value = 0
    dut.qspi_addr_len_i.value = 0
    dut.qspi_dummy_len_i.value = 0
    dut.qspi_data_len_i.value = 0
    dut.qspi_cmd_mode_i.value = 0
    dut.qspi_addr_mode_i.value = 0
    dut.qspi_data_mode_i.value = 0
    dut.qspi_csn_sel_i.value = 0
    dut.qspi_sck_mode_i.value = 0
    dut.qspi_data_dir_i.value = 0
    dut.qspi_crm_i.value = 0
    dut.qspi_ddr_i.value = 0
    dut.qspi_endian_i.value = 0

    # Data & Payloads
    dut.qspi_cmd_i.value = 0
    dut.qspi_addr_i.value = 0
    dut.qspi_mode_byte_i.value = 0
    dut.qspi_wdata_i.value = 0

    # FIFO Interface
    dut.fifo_empty_i.value = 1  
    dut.fifo_full_i.value = 0   

    # Reset the DUT and wait power up
    await Timer(1, unit="us")
    dut.rst_ni.value = 1

    dut._log.info("Waiting for all 3 Flash models to Power-Up...")
    await Timer(STARTUP_TIME*1000, unit="ms")


async def qspi_write_command(dut, cs_mask, cmd):
    """
    Fires a standalone 8-bit command with NO address and NO data.
    Perfect for Write Enable (0x06), Write Disable (0x04), or Reset Enable (0x66).
    """
    dut.qspi_csn_sel_i.value   = cs_mask
    dut.qspi_cmd_i.value       = cmd
    dut.qspi_cmd_mode_i.value  = 1 # 1 Line SPI
    dut.qspi_addr_mode_i.value = 0 # Skip Address
    dut.qspi_dummy_len_i.value = 0 # Skip Dummy
    dut.qspi_data_mode_i.value = 0 # Skip Data
    dut.qspi_data_len_i.value  = 0
    
    # Fire the Start Pulse
    dut.qspi_start_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.qspi_start_i.value = 0
    
    # Wait for completion
    while dut.qspi_done_o.value == 0:
        await RisingEdge(dut.clk_i)


async def qspi_write_register(dut, cs_mask, cmd, wdata, data_len=1):
    """
    Fires a command followed immediately by a data write phase.
    Perfect for Write Status Register (0x01, 0x31).
    """
    dut.qspi_csn_sel_i.value   = cs_mask
    dut.qspi_cmd_i.value       = cmd
    dut.qspi_cmd_mode_i.value  = 1 # 1 Line SPI
    dut.qspi_addr_mode_i.value = 0 # Skip Address
    dut.qspi_dummy_len_i.value = 0 # Skip Dummy
    dut.qspi_data_mode_i.value = 1 # 1 Line SPI for Data
    dut.qspi_data_dir_i.value  = 1 # 1 = WRITE
    dut.qspi_data_len_i.value  = data_len
    dut.qspi_wdata_i.value     = wdata # The payload to send
    
    # Fire the Start Pulse
    dut.qspi_start_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.qspi_start_i.value = 0
    
    # Wait for completion
    while dut.qspi_done_o.value == 0:
        await RisingEdge(dut.clk_i)


async def qspi_read_register(dut, cs_mask, cmd, data_len=1):
    """
    Fires a command followed by a data read phase.
    Perfect for Read Status Register (0x05) to check the BUSY bit.
    """
    dut.qspi_csn_sel_i.value   = cs_mask
    dut.qspi_cmd_i.value       = cmd
    dut.qspi_cmd_mode_i.value  = 1 # 1 Line SPI
    dut.qspi_addr_mode_i.value = 0 # Skip Address
    dut.qspi_dummy_len_i.value = 0 # Skip Dummy
    dut.qspi_data_mode_i.value = 1 # 1 Line SPI for Data
    dut.qspi_data_dir_i.value  = 0 # 0 = READ
    dut.qspi_data_len_i.value  = data_len
    
    # Fire the Start Pulse
    dut.qspi_start_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.qspi_start_i.value = 0
    
    # Wait for completion
    while dut.qspi_done_o.value == 0:
        await RisingEdge(dut.clk_i)
        
    return int(dut.qspi_rdata_o.value)


async def qspi_read_transaction(dut, cs_mask, cmd, cmd_mode, addr, addr_mode, dummy_len, data_mode, data_len=4):
    """Helper coroutine to fire a read transaction to the QSPI Master."""
    dut.qspi_csn_sel_i.value   = cs_mask
    dut.qspi_cmd_i.value       = cmd
    dut.qspi_cmd_mode_i.value  = cmd_mode
    dut.qspi_addr_i.value      = addr
    dut.qspi_addr_mode_i.value = addr_mode
    dut.qspi_dummy_len_i.value = dummy_len
    dut.qspi_data_mode_i.value = data_mode
    dut.qspi_data_dir_i.value  = 0 # READ
    dut.qspi_data_len_i.value  = data_len
    
    dut.qspi_start_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.qspi_start_i.value = 0
    
    while dut.qspi_done_o.value == 0:
        await RisingEdge(dut.clk_i)
        
    return int(dut.qspi_rdata_o.value)


async def test_flash_read_modes(dut):
    """Test Normal, Fast, Dual, and Quad reads across all 3 Flash models."""
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)
    
    scoreboard = Scoreboard()

    # Define our test targets
    targets = [
        {"name": "Infineon", "mask": 1}, 
        {"name": "Winbond",  "mask": 2}, 
        {"name": "Macronix", "mask": 4}  
    ]
    
    # Modes: (Name, Cmd, CmdMode, AddrMode, DummyLen, DataMode)
    # Note: data_mode values => 1: Single, 2: Dual, 3: Quad
    read_modes = [
        ("Normal Read (0x03)",      0x03, 1, 1, 0, 1), # (1-1-1)
        ("Fast Read (0x0B)",        0x0B, 1, 1, 8, 1), # (1-1-1) + 8 dummy cycles
        ("Dual Output Read (0x3B)", 0x3B, 1, 1, 8, 2), # (1-1-2)
        ("Quad Output Read (0x6B)", 0x6B, 1, 1, 8, 3), # (1-1-4)
        ("Dual I/O Read (0xBB)",    0xBB, 1, 2, 4, 2), # (1-2-2)
        ("Quad I/O Read (0xEB)",    0xEB, 1, 3, 6, 3)  # (1-4-4)
    ]

    for target in targets:
        dut._log.info("==================================================")
        dut._log.info(f" TARGET: {target['name']} (CS Mask: {target['mask']})")
        dut._log.info("==================================================")
        
        for mode_name, cmd, cmd_mode, addr_mode, dummy, data_mode in read_modes:
            dut._log.info(f" -> Executing {mode_name}...")
            
            try:
                # Issue the Read
                read_data = await qspi_read_transaction(
                    dut=dut, 
                    cs_mask=target['mask'], 
                    cmd=cmd, 
                    cmd_mode=cmd_mode, 
                    addr=0x000000, 
                    addr_mode=addr_mode, 
                    dummy_len=dummy, 
                    data_mode=data_mode,
                    data_len=4  
                )
                
                hex_str = f"0x{read_data:08X}"
                try:
                    ascii_str = read_data.to_bytes(4, byteorder='big').decode('ascii', errors='replace')
                except Exception:
                    ascii_str = "????"

                dut._log.info(f"    Result: {hex_str} (ASCII: '{ascii_str}')")
                
                # Perform Checks
                if read_data == 0:
                    raise ValueError("Returned all zeros (0x00000000).")
                if read_data == 0xFFFFFFFF:
                    raise ValueError("Returned all FFs (Floating Bus). Quad Enable (QE) bit might be missing!")

                # If we got here, the transaction was mathematically successful
                scoreboard.record(target['name'], mode_name, passed=True)

            except Exception as e:
                # Catch failures so we can continue testing other modes/chips
                dut._log.error(f"    [!] FAILED: {str(e)}")
                scoreboard.record(target['name'], mode_name, passed=False, error_msg=str(e))
            
            # Let the bus rest between transactions to ensure CSn deselect times are met
            await Timer(500, unit="ns")
            
    # Print the Final Verdict
    scoreboard.report(dut._log)


@cocotb.test()
async def tb_qspi_master(dut):
    """Top-level testbench for the QSPI Master"""
    await init_qspi_master(dut)
    
    # Run the Flash Read Modes test (Now with Scoreboard!)
    await test_flash_read_modes(dut)