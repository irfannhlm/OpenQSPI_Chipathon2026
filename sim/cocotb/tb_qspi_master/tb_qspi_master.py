import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge

@cocotb.test()
async def test_triple_flash_jedec_id(dut):
    """Test Read JEDEC ID across Infineon, Winbond, and Macronix flashes"""
    
    # 1. Start Clock (50 MHz)
    cocotb.start_soon(Clock(dut.clk_i, 20, units="ns").start())
    
    # 2. INITIALIZE ALL PINS TO SAFE DEFAULTS
    # This prevents 'X' (Unknown) and 'Z' (Floating) states from breaking the FSM
    
    # Core Control
    dut.rst_ni.value = 0
    dut.qspi_start_i.value = 0
    dut.qspi_abort_i.value = 0
    
    # Configuration Registers
    dut.qspi_timeout_i.value = 0
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
    
    # FIFO Interface (Crucial to prevent stalling)
    dut.fifo_empty_i.value = 1  # TX FIFO is empty
    dut.fifo_full_i.value = 0   # RX FIFO has plenty of space

    # 3. Apply Reset
    await Timer(1, units="us")
    dut.rst_ni.value = 1
    
    # 4. Wait for Flash Power-up (tVSL)
    dut._log.info("Waiting for all 3 Flash models to Power-Up...")
    await Timer(1.5, units="ms")
    
    # 5. Configure QSPI Master for JEDEC ID (0x9F)
    await RisingEdge(dut.clk_i)
    dut.qspi_prescaler_i.value = 0  # Half Max Speed (25 MHz)    
    dut.qspi_sck_mode_i.value  = 0    
    dut.qspi_cmd_i.value       = 0x9F # Read JEDEC ID
    dut.qspi_cmd_mode_i.value  = 1    # Single SPI
    dut.qspi_addr_mode_i.value = 0    # Skip Address
    dut.qspi_dummy_len_i.value = 0    # Skip Dummy
    dut.qspi_data_mode_i.value = 1    # Single SPI Data
    dut.qspi_data_dir_i.value  = 0    # 0 = Read direction
    dut.qspi_data_len_i.value  = 3    # 3 Bytes payload
    
    # 6. Define our test targets (Name, CS_BITMASK)
    targets = [
        ("Infineon", 1), # 0b001
        ("Winbond",  2), # 0b010
        ("Macronix", 4)  # 0b100
    ]
    
    read_ids = []

    # 7. Execute the transaction for each chip
    for name, cs_mask in targets:
        dut.qspi_csn_sel_i.value = cs_mask
        dut._log.info(f"--- Requesting JEDEC ID from {name} (CS Mask: {cs_mask}) ---")
        
        # Fire Start Pulse
        dut.qspi_start_i.value = 1
        await RisingEdge(dut.clk_i)
        dut.qspi_start_i.value = 0
        
        # Wait for Master FSM to finish
        while dut.qspi_done_o.value == 0:
            await RisingEdge(dut.clk_i)
            
        # Capture and log data
        jedec_id = int(dut.qspi_rdata_o.value)
        read_ids.append(jedec_id)
        
        dut._log.info(f"-> {name} Responded with ID: 0x{jedec_id:06X}")
        
        # Let the bus rest between transactions
        await Timer(500, units="ns") 
        
    # 8. Safety Assertions
    for i, id_val in enumerate(read_ids):
        assert id_val != 0, f"FAIL: Chip {targets[i][0]} returned 0x000000. MISO might be disconnected."
        assert id_val != 0xFFFFFF, f"FAIL: Chip {targets[i][0]} returned 0xFFFFFF. MISO might be floating (Z)."
        
    assert len(set(read_ids)) == 3, "FAIL: Collision detected! Multiple chips returned the same ID."
    
    dut._log.info("SUCCESS: All 3 chips independently verified on the shared SPI bus!")