import math
import os
import random
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
        log.info(f" SIMULATION SCOREBOARD: {self.passed} PASSED, {self.failed} FAILED")
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

    # FIFO Interface
    dut.fifo_wdata_i.value = 0
    dut.fifo_push_i.value = 0
    dut.fifo_pop_i.value = 0

    # Reset the DUT and wait power up
    await Timer(1, unit="us")
    dut.rst_ni.value = 1

    dut._log.info("Waiting for all 3 Flash models to Power-Up...")
    await Timer(STARTUP_TIME*1000, unit="ms")

async def fifo_push_data(dut, data):
    """Pushes a 32-bit word into the QSPI Master's FIFO."""
    dut.fifo_wdata_i.value = data
    dut.fifo_push_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.fifo_push_i.value = 0
    await RisingEdge(dut.clk_i)

async def fifo_pop_data(dut, num_words=1):
    """Pops a 32-bit word from the QSPI Master's FIFO."""
    fifo_data = []
    for _ in range(num_words):
        fifo_data.append(int(dut.fifo_rdata_o.value))
        dut.fifo_pop_i.value = 1
        await RisingEdge(dut.clk_i)
        dut.fifo_pop_i.value = 0
        await RisingEdge(dut.clk_i)
        await Timer(500, unit="ns")
    return fifo_data

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

    await fifo_push_data(dut, wdata)

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
        
    await RisingEdge(dut.clk_i)
    read_data = await fifo_pop_data(dut, num_words=data_len)  # Pop the data from FIFO
    return read_data[0] if read_data else 0  # Return the first word or 0 if empty


async def qspi_read_transaction(dut, cs_mask, cmd, cmd_mode, addr, addr_mode, addr_len, dummy_len, data_mode, data_len=4, ddr=False):
    """Helper coroutine to fire a read transaction to the QSPI Master."""
    dut.qspi_csn_sel_i.value   = cs_mask
    dut.qspi_cmd_i.value       = cmd
    dut.qspi_cmd_mode_i.value  = cmd_mode
    dut.qspi_addr_i.value      = addr
    dut.qspi_addr_mode_i.value = addr_mode
    dut.qspi_addr_len_i.value  = addr_len
    dut.qspi_dummy_len_i.value = dummy_len
    dut.qspi_data_mode_i.value = data_mode
    dut.qspi_data_dir_i.value  = 0 # READ
    dut.qspi_data_len_i.value  = data_len
    dut.qspi_ddr_i.value       = 1 if ddr else 0
    
    dut.qspi_start_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.qspi_start_i.value = 0
    
    result_list = []
    reader_task = cocotb.start_soon(delayed_rx_fifo_reader(dut, num_words=math.ceil(data_len / 4), result_list=result_list))

    while dut.qspi_done_o.value == 0:
        await RisingEdge(dut.clk_i)
        
    await reader_task  # Ensure the reader task has completed

    return result_list

async def delayed_rx_fifo_reader(dut, num_words, result_list):
    """A robust reader that randomly stalls, forcing the hardware to handle FIFO limits."""
    words_popped = 0
    
    while words_popped < num_words:
        if dut.fifo_empty_o.value != 0: 
            await RisingEdge(dut.clk_i)
            continue
            
        # Randomly simulate a distracted CPU (10% chance to sleep)
        # This allows the Verilog hardware FIFO to fill up naturally and trigger a clock pause
        if random.random() < 0.1:
            sleep_time = random.randint(1, 4)
            dut._log.info(f"    [RX CPU] CPU distracted for {sleep_time}us... Letting FIFO fill!")
            await Timer(sleep_time, unit="us")
            
        # Wake up and calculate a random burst to pop
        words_left = num_words - words_popped
        burst_size = random.randint(1, min(16, words_left))
        
        # Realign to clock edge
        await RisingEdge(dut.clk_i)

        popped_in_burst = 0
        while popped_in_burst < burst_size:
            # Only pop if we actually have data
            if dut.fifo_empty_o.value == 0:
                data = int(dut.fifo_rdata_o.value)
                result_list.append(data)

                # dut._log.info(f"    [RX] Popped Word {words_popped+1}/{num_words}: 0x{data:08X}")
                
                # Pulse the pop signal
                dut.fifo_pop_i.value = 1
                await RisingEdge(dut.clk_i)
                dut.fifo_pop_i.value = 0
                await RisingEdge(dut.clk_i)
                
                words_popped += 1
                popped_in_burst += 1

                # Have a random delay between pops
                for i in range(1, random.randint(5, 30)):
                    await RisingEdge(dut.clk_i)

            else:
                # FIFO is empty, break the burst early and loop back
                break


async def delayed_tx_fifo_writer(dut, data_words):
    """Pushes half the data, lets the FIFO drain to EMPTY, waits, then pushes the rest."""
    half = len(data_words) // 2
    
    # Push first half
    for i in range(half):
        dut.fifo_wdata_i.value = data_words[i]
        dut.fifo_push_i.value = 1
        await RisingEdge(dut.clk_i)
        dut.fifo_push_i.value = 0
        
    dut._log.info("    [TX] Half data pushed! Letting FIFO drain to EMPTY to test Clock Pause...")
    await Timer(random.randint(1, 3), unit="us")
    dut._log.info("    [TX] Pushing remaining data...")
    
    # Push second half
    for i in range(half, len(data_words)):
        dut.fifo_wdata_i.value = data_words[i]
        dut.fifo_push_i.value = 1
        await RisingEdge(dut.clk_i)
        dut.fifo_push_i.value = 0

def load_golden_data_from_mem(file_path, endian="big"):
    """
    Parses a Verilog .mem file and returns a dictionary of memory sectors.
    Key: Base Address (int)
    Value: List of packed 32-bit words
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Golden memory file not found: {file_path}")
        
    memory_blocks = {}
    current_base_addr = 0
    current_bytes = []
    
    def pack_and_save():
        if not current_bytes:
            return
            
        # Pad with zeros if the block doesn't end cleanly on a 4-byte boundary
        while len(current_bytes) % 4 != 0:  
            current_bytes.append(0x00)
            
        words = []
        for i in range(0, len(current_bytes), 4):
            # Extract the 4-byte chunk
            chunk = current_bytes[i : i+4]
            
            if endian == "little":
                # Little Endian: Byte 0 goes to the LSB [7:0]
                word = (chunk[3] << 24) | (chunk[2] << 16) | \
                       (chunk[1] << 8)  | chunk[0]
            else:
                # Big Endian (Default): Byte 0 goes to the MSB [31:24]
                word = (chunk[0] << 24) | (chunk[1] << 16) | \
                       (chunk[2] << 8)  | chunk[3]
                       
            words.append(word)
            
        memory_blocks[current_base_addr] = words

    with open(file_path, 'r') as f:
        for line in f:
            line = line.split('//')[0].strip()
            if not line:
                continue
                
            tokens = line.split()
            for token in tokens:
                if token.startswith('@'):
                    pack_and_save()
                    current_base_addr = int(token[1:], 16)
                    current_bytes = []
                else:
                    current_bytes.append(int(token, 16))
                    
    pack_and_save()
    return memory_blocks

def get_expected_words(golden_dict, target_addr, num_words, total_bytes, endian="big"):
    """
    Searches the sparse memory dictionary for the target address.
    Calculates the internal word offset, extracts the slice, and masks
    the final word if total_bytes is not word-aligned.
    """
    for base_addr, words in golden_dict.items():
        block_byte_len = len(words) * 4
        
        if base_addr <= target_addr < (base_addr + block_byte_len):
            word_offset = (target_addr - base_addr) // 4
            expected_slice = words[word_offset : word_offset + num_words].copy() # Copy to avoid mutating original
            
            if len(expected_slice) < num_words:
                raise ValueError(f"Requested {num_words} words, but only {len(expected_slice)} remain in block @0x{base_addr:06X}")
                
            # --- THE NON-ALIGNED PADDING FIX ---
            # Calculate how many bytes in the very last word are actually "valid"
            valid_bytes_in_last_word = total_bytes % 4
            
            # If it's not perfectly aligned (0), we need to mask the last word
            if valid_bytes_in_last_word != 0:
                last_word_idx = num_words - 1
                original_last_word = expected_slice[last_word_idx]
                
                if endian == "big":
                    # Keep the top N bytes. 
                    # 1 byte  = 0xFF000000
                    # 2 bytes = 0xFFFF0000
                    # 3 bytes = 0xFFFFFF00
                    shift_amount = (4 - valid_bytes_in_last_word) * 8
                    mask = (0xFFFFFFFF << shift_amount) & 0xFFFFFFFF
                else:
                    # Keep the bottom N bytes.
                    # 1 byte  = 0x000000FF
                    # 2 bytes = 0x0000FFFF
                    # 3 bytes = 0x00FFFFFF
                    shift_amount = valid_bytes_in_last_word * 8
                    mask = (1 << shift_amount) - 1
                    
                expected_slice[last_word_idx] = original_last_word & mask
                
            return expected_slice
            
    raise ValueError(f"Target address 0x{target_addr:06X} not found in Golden Memory!")


async def test_s25fl_read_modes(dut):
    """Test Normal, Fast, Dual, and Quad reads for the S25FL series flash memories."""
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)
    
    s25fl_mask = 0b001

    scoreboard = Scoreboard()
    
    # S25FL QUAD MODE ENABLE ROUTINE
    # Send Write Enable (0x06)
    dut._log.info("Enabling Quad Mode for S25FL...")
    await qspi_write_command(dut, cs_mask=s25fl_mask, cmd=0x06)
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    # Send Read Status Register (0x05) to verify WEL bit is set
    dut._log.info("Verifying Write Enable Latch (WEL) bit is set in Status Register 1...")
    status_reg = await qspi_read_register(dut, cs_mask=s25fl_mask, cmd=0x05, data_len=1)
    dut._log.info(f"Status Register 1 value: 0x{status_reg:02X}")
    if ((status_reg>>24) & 0x02) == 0:
        raise ValueError("Failed to set Write Enable Latch (WEL) bit in Status Register!")
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    # Send Write Register (0x01) with QE bit set (0x0002 -> CR1[1] = 1)
    dut._log.info("WEL bit is set. Proceeding to set Quad Enable (QE) bit in Configuration Register 1...")
    await qspi_write_register(dut, cs_mask=s25fl_mask, cmd=0x01, wdata=(0x0002_0000), data_len=2)
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    # Loop until the WIP bit clears in Status Register 1 (0x05)
    dut._log.info("Waiting for Write-In-Progress (WIP) bit to clear in Status Register 1...")
    while True:
        status_reg = await qspi_read_register(dut, cs_mask=s25fl_mask, cmd=0x05, data_len=1)
        dut._log.info(f"Status Register 1 value: 0x{status_reg:02X}")
        if ((status_reg>>24) & 0x01) == 0:
            break
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)
    dut._log.info("WIP bit cleared. Quad Enable (QE) bit should now be set in Configuration Register 1.")

    # Send Read Configuration Register 1 (0x35) to verify QE bit is set
    dut._log.info("Verifying Quad Enable (QE) bit is set in Configuration Register 1...")
    config_reg = await qspi_read_register(dut, cs_mask=s25fl_mask, cmd=0x35, data_len=1)
    dut._log.info(f"Configuration Register 1 value: 0x{config_reg:04X}")
    if ((config_reg>>24) & 0x02) == 0:
        raise ValueError("Failed to set Quad Enable (QE) bit in Configuration Register 1!")
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    dut._log.info("QE bit is set. Proceeding to test read modes...")

    # Modes: (Name, Cmd, CmdMode, AddrMode, AddrLen, DummyLen, DataMode)
    # Note: data_mode values => 1: Single, 2: Dual, 3: Quad
    read_modes = [
        ("Normal Read (0x03)",      0x03, 1, 1, 0, 0, 1, False), # (1-1-1)
        ("Fast Read (0x0B)",        0x0B, 1, 1, 0, 8, 1, False), # (1-1-1)
        ("Dual Output Read (0x3B)", 0x3B, 1, 1, 0, 8, 2, False), # (1-1-2)
        ("Quad Output Read (0x6B)", 0x6B, 1, 1, 0, 8, 3, False), # (1-1-4)
        ("Dual I/O Read (0xBB)",    0xBB, 1, 2, 0, 4, 2, False), # (1-2-2)
        ("Quad I/O Read (0xEB)",    0xEB, 1, 3, 0, 6, 3, False), # (1-4-4)
        ("DDR Fast Read (0x0D)",    0x0D, 1, 1, 0, 5, 1, True), # (1-1-1) DDR
        ("DDR Dual I/O Read (0xBD)",0xBD, 1, 2, 0, 6, 2, True), # (1-2-2) DDR
        ("DDR Quad I/O Read (0xED)",0xED, 1, 3, 0, 7, 3, True), # (1-4-4) DDR
    ]

    dut._log.info("Loading Golden Data from s25fl128s.mem...")
    golden_memory_dict = load_golden_data_from_mem("s25fl128s.mem")
        
    for mode_name, cmd, cmd_mode, addr_mode, addr_len, dummy, data_mode, ddr in read_modes:
        
        
        try:
            target_address = 0x000000 
            test_data_len = random.randint(128, 500)  # Random length between 128 and 500 bytes
            expected_words = math.ceil(test_data_len / 4)
            
            # Fetch the golden slice from our dictionary
            expected_list = get_expected_words(golden_memory_dict, target_address, expected_words, test_data_len)

            dut._log.info(f" -> Executing {mode_name} with random length: {test_data_len} Bytes ({expected_words} Words)...")

            # Issue the Hardware Read
            result_list = await qspi_read_transaction(
                dut=dut, 
                cs_mask=s25fl_mask, 
                cmd=cmd, 
                cmd_mode=cmd_mode, 
                addr=target_address,
                addr_mode=addr_mode, 
                addr_len=addr_len,
                dummy_len=dummy, 
                data_mode=data_mode,
                data_len=test_data_len,
                ddr=ddr
            )

            dut._log.info(f"    [RX] Received {len(result_list)} Words from FIFO. Verifying against Golden Data...")            

            # --- AUTOMATED SCOREBOARD VERIFICATION ---
            if len(result_list) != expected_words:
                 raise ValueError(f"FIFO Pop Mismatch! Expected {expected_words} words, got {len(result_list)}.")
                 
            for i in range(expected_words):
                dut._log.info(f"    [VERIFY] Word {i}: Expected 0x{expected_list[i]:08X}, Got 0x{result_list[i]:08X}")
                if result_list[i] != expected_list[i]:
                    raise ValueError(f"DATA MISMATCH at Word {i}! Expected 0x{expected_list[i]:08X}, Got 0x{result_list[i]:08X}")

            dut._log.info(f"    Test {mode_name} PASSED!")

            scoreboard.record("S25FL", mode_name, passed=True)

        except Exception as e:
            dut._log.error(f"    [!] FAILED: {str(e)}")
            scoreboard.record("S25FL", mode_name, passed=False, error_msg=str(e))

        
        # Let the bus rest between transactions to ensure CSn deselect times are met
        await Timer(500, unit="ns")
            
    # Print the Final Verdict
    scoreboard.report(dut._log)

@cocotb.test()
async def tb_qspi_master(dut):
    """Top-level testbench for the QSPI Master"""
    await init_qspi_master(dut)
    
    await test_s25fl_read_modes(dut)