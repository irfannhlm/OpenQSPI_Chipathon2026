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

        await Timer(100, unit="ns")
        await RisingEdge(dut.clk_i)
    return fifo_data


async def qspi_write_command(dut, cs_mask, cmd, qpi=False):
    """
    Fires a standalone 8-bit command with NO address and NO data.
    Perfect for Write Enable (0x06), Write Disable (0x04), or Reset Enable (0x66).
    """
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    dut.qspi_csn_sel_i.value   = cs_mask
    dut.qspi_cmd_i.value       = cmd
    dut.qspi_cmd_mode_i.value  = 3 if qpi else 1 # 4 Line QPI or 1 Line SPI
    dut.qspi_addr_mode_i.value = 0 # Skip Address
    dut.qspi_dummy_len_i.value = 0 # Skip Dummy
    dut.qspi_data_mode_i.value = 0 # Skip Data
    dut.qspi_data_len_i.value  = 0

    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

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
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    dut.qspi_csn_sel_i.value   = cs_mask
    dut.qspi_cmd_i.value       = cmd
    dut.qspi_cmd_mode_i.value  = 1 # 1 Line SPI
    dut.qspi_addr_mode_i.value = 0 # Skip Address
    dut.qspi_dummy_len_i.value = 0 # Skip Dummy
    dut.qspi_data_mode_i.value = 1 # 1 Line SPI for Data
    dut.qspi_data_dir_i.value  = 1 # 1 = WRITE
    dut.qspi_data_len_i.value  = data_len

    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

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
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    dut.qspi_csn_sel_i.value   = cs_mask
    dut.qspi_cmd_i.value       = cmd
    dut.qspi_cmd_mode_i.value  = 1 # 1 Line SPI
    dut.qspi_addr_mode_i.value = 0 # Skip Address
    dut.qspi_dummy_len_i.value = 0 # Skip Dummy
    dut.qspi_data_mode_i.value = 1 # 1 Line SPI for Data
    dut.qspi_data_dir_i.value  = 0 # 0 = READ
    dut.qspi_data_len_i.value  = data_len

    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

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
            dut._log.info(f"        [RX CPU] CPU distracted for {sleep_time}us... Letting FIFO fill!")
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

                dut._log.info(f"        [RX] Popped Word {words_popped+1}/{num_words}: 0x{data:08X}")
                
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


async def delayed_tx_fifo_writer(dut, data_words, num_words=1):
    words_pushed = 0
    total_words = num_words
    dut.fifo_push_i.value = 0

    # Small delay and align to clock edge
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    while words_pushed < total_words:
        await RisingEdge(dut.clk_i)
        
        if dut.fifo_full_o.value != 0:
            continue
            
        if random.random() < 0.1:
            sleep_time = random.randint(1, 4)
            dut._log.info(f"        [TX CPU] CPU stall for {sleep_time}us... Starving the QSPI Master!")
            await Timer(sleep_time, unit="us")
            continue
            
        words_left = total_words - words_pushed
        burst_size = random.randint(1, min(16, words_left))

        # Realign to clock edge
        await RisingEdge(dut.clk_i)
        
        pushed_in_burst = 0
        while pushed_in_burst < burst_size:
            if dut.fifo_full_o.value == 0:
                # Apply data and drive PUSH High
                dut.fifo_wdata_i.value = data_words[words_pushed]
                dut.fifo_push_i.value = 1
                await RisingEdge(dut.clk_i)

                dut._log.info(f"        [TX] Pushed Word {words_pushed+1}/{total_words}: 0x{data_words[words_pushed]:08X}")
                
                # Drive PUSH Low AND YIELD
                dut.fifo_push_i.value = 0
                await RisingEdge(dut.clk_i)
                
                words_pushed += 1
                pushed_in_burst += 1

                # Have a random delay between pushes
                for i in range(1, random.randint(5, 30)):
                    await RisingEdge(dut.clk_i)
            else:
                break


async def qspi_read_transaction(dut, cs_mask, cmd, cmd_mode, addr, addr_mode, addr_len, dummy_len, data_mode, data_len, ddr=False):
    """Helper coroutine to fire a read transaction to the QSPI Master."""
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

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
    dut.qspi_sck_mode_i.value  = 0 # Mode 1
    dut.qspi_endian_i.value    = 0  # Big Endian

    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    dut.qspi_start_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.qspi_start_i.value = 0
    
    result_list = []
    reader_task = cocotb.start_soon(delayed_rx_fifo_reader(dut, num_words=math.ceil(data_len / 4), result_list=result_list))

    while dut.qspi_done_o.value == 0:
        await RisingEdge(dut.clk_i)
        
    await reader_task  # Ensure the reader task has completed

    return result_list


async def qspi_write_transaction(dut, cs_mask, cmd, cmd_mode, addr, addr_mode, addr_len, data_mode, data_len, data_words, ddr=False):
    """Fires a flexible QSPI write transaction utilizing the delayed TX writer."""
    dut.qspi_csn_sel_i.value   = cs_mask
    dut.qspi_cmd_i.value       = cmd
    dut.qspi_cmd_mode_i.value  = cmd_mode
    dut.qspi_addr_i.value      = addr
    dut.qspi_addr_mode_i.value = addr_mode
    dut.qspi_addr_len_i.value  = addr_len
    dut.qspi_dummy_len_i.value = 0 # Writes rarely have dummy cycles
    dut.qspi_data_mode_i.value = data_mode
    dut.qspi_data_dir_i.value  = 1 # 1 = WRITE
    dut.qspi_data_len_i.value  = data_len
    dut.qspi_ddr_i.value       = 1 if ddr else 0

    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)
    
    # Launch parallel delayed writer
    writer_task = cocotb.start_soon(delayed_tx_fifo_writer(dut, data_words, num_words=math.ceil(data_len / 4)))
    
    # Start Pulse
    dut.qspi_start_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.qspi_start_i.value = 0
    
    while dut.qspi_done_o.value == 0:
        await RisingEdge(dut.clk_i)
        
    await writer_task


async def qspi_custom_transaction(dut, cs_mask=0, cmd_mode=0, addr_mode=0, data_mode=0, addr_len=0, dummy_len=0, data_len=0, 
                                  data_dir=0, prescaler=0, sck_mode=0, timeout=int(CLOCK_FREQ*1e-3), crm=False, ddr=False, endian="big",
                                  cmd=0, addr=0, mode_byte=0xa5, data_words=[], manual_fifo=False):
    """Fires a fully flexible QSPI transaction to the DUT."""
    dut.qspi_timeout_i.value = timeout # 1ms default
    dut.qspi_prescaler_i.value = prescaler
    dut.qspi_addr_len_i.value = addr_len
    dut.qspi_dummy_len_i.value = dummy_len
    dut.qspi_data_len_i.value = data_len
    dut.qspi_cmd_mode_i.value = cmd_mode
    dut.qspi_addr_mode_i.value = addr_mode
    dut.qspi_data_mode_i.value = data_mode
    dut.qspi_csn_sel_i.value = cs_mask
    dut.qspi_sck_mode_i.value = sck_mode
    dut.qspi_data_dir_i.value = data_dir
    dut.qspi_crm_i.value = 1 if crm else 0
    dut.qspi_ddr_i.value = 1 if ddr else 0
    dut.qspi_endian_i.value = 1 if endian == "little" else 0

    dut.qspi_cmd_i.value = cmd
    dut.qspi_addr_i.value = addr
    dut.qspi_mode_byte_i.value = mode_byte

    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    if not manual_fifo:
        if data_dir == 0 and data_len > 0:
            # Launch parallel delayed writer for TX
            writer_task = cocotb.start_soon(delayed_tx_fifo_writer(dut, data_words, num_words=math.ceil(data_len / 4)))
        elif data_dir == 1 and data_words:
            # Prepare a list to collect RX data
            result_list = []
            reader_task = cocotb.start_soon(delayed_rx_fifo_reader(dut, num_words=math.ceil(data_len / 4), result_list=result_list))

    # Fire the Start Pulse
    dut.qspi_start_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.qspi_start_i.value = 0
    
    # Wait for completion
    while dut.qspi_done_o.value == 0:
        await RisingEdge(dut.clk_i)

    if not manual_fifo:
        if data_dir == 0 and data_len > 0:
            await reader_task  # Ensure the reader task has completed
            return result_list
        elif data_dir == 1 and data_words:
            await writer_task  # Ensure the writer task has completed
            return None
    

async def qspi_poll_wip_bit(dut, cs_mask, status_cmd=0x05, poll_interval_ns=1000, timeout_s=10e-3, verbose=True):
    """Polls the WIP/BUSY bit in the Status Register until it clears or a timeout occurs."""
    dut._log.info("Polling WIP/BUSY bit in Status Register...")
    elapsed_time = 0

    # Poll status register with infinite reading
    poll_task = cocotb.start_soon(qspi_custom_transaction(dut, cs_mask=cs_mask, cmd=status_cmd, data_len=0xFFFF_FFFF, 
                                                        cmd_mode=1, addr_mode=0, addr_len=0, dummy_len=0, data_mode=1, data_dir=0,
                                                        manual_fifo=True, timeout=int(CLOCK_FREQ*timeout_s*10)))
    
    # Wait until first FIFO full
    while dut.fifo_full_o.value == 0:
        await RisingEdge(dut.clk_i)

    while True:
        status_reg = await fifo_pop_data(dut, num_words=1) # Pop the status register value from FIFO
        status_reg = status_reg[0] if status_reg else 0
        if verbose:
            dut._log.info(f"Status Register value: {status_reg>>24:08b}")
        if ((status_reg>>24) & 0x01) == 0:
            # abort the polling task
            dut.qspi_abort_i.value = 1
            await RisingEdge(dut.clk_i)
            dut.qspi_abort_i.value = 0
            await RisingEdge(dut.clk_i)

            await poll_task # Ensure the polling task has completed

            if verbose:
                dut._log.info("WIP/BUSY bit cleared. Operation complete.")
            break

        await Timer(poll_interval_ns, unit="ns")
        await RisingEdge(dut.clk_i)

        elapsed_time += poll_interval_ns * 1e-9
        if elapsed_time >= timeout_s:
            raise TimeoutError(f"WIP/BUSY bit did not clear within {timeout_s*1000:.2f} ms!")

    while dut.fifo_empty_o.value == 0:
        await fifo_pop_data(dut, num_words=1)  # Clear any remaining data in FIFO


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
                raise ValueError(f"Requested {num_words} words, but only {len(expected_slice)} remain in block @0x{base_addr:08X}")
                
            valid_bytes_in_last_word = total_bytes % 4
            
            if valid_bytes_in_last_word != 0:
                last_word_idx = num_words - 1
                original_last_word = expected_slice[last_word_idx]
                
                if endian == "big":
                    # Keep the top N bytes. 
                    shift_amount = (4 - valid_bytes_in_last_word) * 8
                    mask = (0xFFFFFFFF << shift_amount) & 0xFFFFFFFF
                else:
                    # Keep the bottom N bytes.
                    shift_amount = valid_bytes_in_last_word * 8
                    mask = (1 << shift_amount) - 1
                    
                expected_slice[last_word_idx] = original_last_word & mask
                
            return expected_slice
            
    raise ValueError(f"Target address 0x{target_addr:08X} not found in Golden Memory!")


def load_raw_payload_from_any_file(file_path, endian="big"):
    """
    Reads ANY file (text, binary, firmware, etc.) as raw bytes.
    Packs those bytes into a flat list of 32-bit words for the TX FIFO.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Payload file not found: {file_path}")
        
    # Read the entire file as an array of raw bytes (0-255)
    with open(file_path, 'rb') as f:
        raw_bytes = list(f.read())
                
    # Pad to 4-byte alignment so our 32-bit RTL register doesn't complain
    while len(raw_bytes) % 4 != 0:
        raw_bytes.append(0x00)
        
    words = []
    
    # Pack into 32-bit words applying the hardware Endianness rules
    for i in range(0, len(raw_bytes), 4):
        chunk = raw_bytes[i : i+4]
        
        if endian == "little":
            # Byte 0 lands in LSB [7:0]
            word = (chunk[3] << 24) | (chunk[2] << 16) | (chunk[1] << 8) | chunk[0]
        else:
            # Big Endian (Default): Byte 0 lands in MSB [31:24]
            word = (chunk[0] << 24) | (chunk[1] << 16) | (chunk[2] << 8) | chunk[3]
            
        words.append(word)
        
    return words


async def s25fl_quad_enable_routine(dut, cs_mask):
    """Routine to enable Quad Mode for the S25FL series flash memories."""

    # Send Write Enable (0x06)
    dut._log.info("Enabling Quad Mode for S25FL...")
    await qspi_write_command(dut, cs_mask=cs_mask, cmd=0x06)
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    # Send Read Status Register (0x05) to verify WEL bit is set
    dut._log.info("Verifying Write Enable Latch (WEL) bit is set in Status Register 1...")
    status_reg = await qspi_read_register(dut, cs_mask=cs_mask, cmd=0x05, data_len=1)
    dut._log.info(f"Status Register 1 value: {status_reg>>24:08b}")
    if ((status_reg>>24) & 0x02) == 0:
        raise ValueError("Failed to set Write Enable Latch (WEL) bit in Status Register!")
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    # Send Write Register (0x01) with QE bit set (0x0002 -> CR1[1] = 1)
    dut._log.info("WEL bit is set. Proceeding to set Quad Enable (QE) bit in Configuration Register 1...")
    await qspi_write_register(dut, cs_mask=cs_mask, cmd=0x01, wdata=(0x0002_0000), data_len=2)
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    # Loop until the WIP bit clears in Status Register 1 (0x05)
    dut._log.info("Waiting for Write-In-Progress (WIP) bit to clear in Status Register 1...")
    await qspi_poll_wip_bit(dut, cs_mask=cs_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=5e-3)
    dut._log.info("WIP bit cleared. Quad Enable (QE) bit should now be set in Configuration Register 1.")

    # Send Read Configuration Register 1 (0x35) to verify QE bit is set
    dut._log.info("Verifying Quad Enable (QE) bit is set in Configuration Register 1...")
    config_reg = await qspi_read_register(dut, cs_mask=cs_mask, cmd=0x35, data_len=1)
    dut._log.info(f"Configuration Register 1 value: {config_reg>>24:08b}")
    if ((config_reg>>24) & 0x02) == 0:
        raise ValueError("Failed to set Quad Enable (QE) bit in Configuration Register 1!")
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)


async def w25q_quad_enable_routine(dut, cs_mask):
    """Routine to enable Quad Mode for the W25Q series flash memories."""
    dut._log.info("Enabling Quad Mode for W25Q...")

    # Send Write Enable (0x06)
    await qspi_write_command(dut, cs_mask=cs_mask, cmd=0x06)
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    # Send Read Status Register (0x05) to verify WEL bit is set
    dut._log.info("Verifying Write Enable Latch (WEL) bit is set in Status Register 1...")
    status_reg = await qspi_read_register(dut, cs_mask=cs_mask, cmd=0x05, data_len=1)
    dut._log.info(f"Status Register 1 value: {status_reg>>24:08b}")
    if ((status_reg>>24) & 0x02) == 0:
        raise ValueError("Failed to set Write Enable Latch (WEL) bit in Status Register!")
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    # Send Write Status Register 2 (0x31) with QE bit set (0x02 -> CR1[1] = 1)
    dut._log.info("WEL bit is set. Proceeding to set Quad Enable (QE) bit in Status Register 2...")
    await qspi_write_register(dut, cs_mask=cs_mask, cmd=0x31, wdata=(0x0200_0000), data_len=1)
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    # Loop until the WIP bit clears in Status Register 1 (0x05)
    dut._log.info("Waiting for BUSY bit to clear in Status Register 1...")
    await qspi_poll_wip_bit(dut, cs_mask=cs_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=5e-3)
    dut._log.info("BUSY bit cleared. Quad Enable (QE) bit should now be set in Status Register 2.")

    # Send Read Status Register 2 (0x35) to verify QE bit is set
    dut._log.info("Verifying Quad Enable (QE) bit is set in Status Register 2...")
    status_reg2 = await qspi_read_register(dut, cs_mask=cs_mask, cmd=0x35, data_len=1)
    dut._log.info(f"Status Register 2 value: {status_reg2>>24:08b}")
    if ((status_reg2>>24) & 0x02) == 0:
        raise ValueError("Failed to set Quad Enable (QE) bit in Status Register 2!")
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)
    
    dut._log.info("Quad Enable (QE) bit is successfully set in Status Register 2 for W25Q series flash.")
    

async def mx25l_quad_enable_routine(dut, cs_mask):
    """Routine to enable Quad Mode for the MX25L series flash memories."""
    dut._log.info("Enabling Quad Mode for MX25L...")

    # Send Write Enable (0x06)
    await qspi_write_command(dut, cs_mask=cs_mask, cmd=0x06)
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    # Send Read Status Register (0x05) to verify WEL bit is set
    dut._log.info("Verifying Write Enable Latch (WEL) bit is set in Status Register...")
    status_reg = await qspi_read_register(dut, cs_mask=cs_mask, cmd=0x05, data_len=1)
    dut._log.info(f"Status Register value: {status_reg>>24:08b}")
    if ((status_reg>>24) & 0x02) == 0:
        raise ValueError("Failed to set Write Enable Latch (WEL) bit in Status Register!")
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    # Send Write Status Register (0x01) with QE bit set (0x02 -> CR1[1] = 1)
    dut._log.info("WEL bit is set. Proceeding to set Quad Enable (QE) bit in Status Register...")
    await qspi_write_register(dut, cs_mask=cs_mask, cmd=0x01, wdata=(0x4000_0000), data_len=1)
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    # Loop until the WIP bit clears in Status Register (0x05)
    dut._log.info("Waiting for BUSY bit to clear in Status Register...")
    await qspi_poll_wip_bit(dut, cs_mask=cs_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=5e-3)
    dut._log.info("BUSY bit cleared. Quad Enable (QE) bit should now be set in Status Register.")

    # Send Read Status Register (0x05) to verify QE bit is set
    dut._log.info("Verifying Quad Enable (QE) bit is set in Status Register...")
    status_reg2 = await qspi_read_register(dut, cs_mask=cs_mask, cmd=0x05, data_len=1)
    dut._log.info(f"Status Register value: {status_reg2>>24:08b}")
    if ((status_reg2>>24) & 0x40) == 0:
        raise ValueError("Failed to set Quad Enable (QE) bit in Status Register!")
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)
    
    dut._log.info("Quad Enable (QE) bit is successfully set in Status Register for MX25L series flash.")


@cocotb.test()
async def test_all_flash_id(dut):
    """Test the Read ID command (0x9F) for all supported flash devices."""
    await init_qspi_master(dut)

    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)
    
    scoreboard = Scoreboard()
    
    # Flash Devices: (Name, CS Mask, Expected ID)
    flash_devices = [
        ("S25FL128S", 0b001, 0x012018), # Manufacturer: 0x01, Memory Type: 0x20, Capacity: 0x18
        ("W25Q65NE",  0b010, 0xEF8517), # Manufacturer: 0xEF, JEDEC ID: 0x8517
        ("MX25L51245G", 0b100, 0xC2201A) # Manufacturer: 0xC2, Memory Type: 0x20, Capacity: 0x1A
    ]
    
    for device_name, cs_mask, expected_id in flash_devices:
        try:
            dut._log.info(f" -> Reading ID from {device_name}...")
            read_id = await qspi_read_register(dut, cs_mask=cs_mask, cmd=0x9F, data_len=3)
            read_id = (read_id >> 8)
            dut._log.info(f"    [ID] Read ID: 0x{read_id:06X}, Expected ID: 0x{expected_id:06X}")
            
            if read_id != expected_id:
                raise ValueError(f"ID Mismatch! Expected 0x{expected_id:06X}, Got 0x{read_id:06X}")
                
            dut._log.info(f"    {device_name} ID Verification PASSED!")
            scoreboard.record(device_name, "Read ID", passed=True)
            
        except Exception as e:
            dut._log.error(f"    [!] FAILED for {device_name}: {str(e)}")
            scoreboard.record(device_name, "Read ID", passed=False, error_msg=str(e))
        
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)
        
    scoreboard.report(dut._log)


@cocotb.test()
async def test_s25fl_read_modes(dut):
    """Test Normal, Fast, Dual, and Quad reads for the S25FL series flash memories."""
    await init_qspi_master(dut)

    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)
    
    s25fl_mask = 0b001
    scoreboard = Scoreboard()

    dut._log.info("Loading Golden Data from s25fl128s.mem...")
    golden_memory_dict = load_golden_data_from_mem("s25fl128s.mem")
    
    # S25FL QUAD MODE ENABLE ROUTINE
    await s25fl_quad_enable_routine(dut, cs_mask=s25fl_mask)
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
        
    for mode_name, cmd, cmd_mode, addr_mode, addr_len, dummy, data_mode, ddr in read_modes:
        
        try:
            target_address = 0x000000 
            test_data_len = 300
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


# STILL NOT WORKING
async def test_s25fl_write_modes(dut):
    """Test standard and Quad Page Program writes on a known empty sector."""
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)
    
    s25fl_mask = 0b001
    scoreboard = Scoreboard()
    
    dut._log.info("Loading Raw Payload Pool...")
    payload_pool = load_raw_payload_from_any_file("ReadMe.TXT", endian="big")

    # Enable Quad Mode for S25FL
    await s25fl_quad_enable_routine(dut, cs_mask=s25fl_mask)
    
    # Start at a known empty sector
    current_addr = 0x050000 
    
    dut._log.info(f"Commencing Write Tests starting at known empty address: 0x{current_addr:08X}...")

    # Write Modes: (Name, Cmd, CmdMode, AddrMode, AddrLen, DataMode)
    write_modes = [
        ("Page Program (0x02)", 0x02, 1, 1, 0, 1), # (1-1-1)
        ("Quad Page Program (0x32)",     0x32, 1, 1, 0, 3)  # (1-1-4)
    ]
    
    for mode_name, cmd, cmd_mode, addr_mode, addr_len, data_mode in write_modes:
        
        test_data_len = random.randint(64, 256)  # Random length between 64 and 256 bytes
        expected_words = math.ceil(test_data_len / 4)
        
        dut._log.info(f" -> Executing {mode_name} with {test_data_len} Bytes...")
        
        try:
            await Timer(10, unit="us")
            await RisingEdge(dut.clk_i)

            # Sector Erase (0xD8) before every program
            dut._log.info("    Sending Write Enable (0x06) command...")
            await qspi_write_command(dut, cs_mask=s25fl_mask, cmd=0x06)
            await Timer(500, unit="ns")
            await RisingEdge(dut.clk_i)

            dut._log.info("    Verifying Write Enable Latch (WEL) bit is set in Status Register 1...")
            status_reg = await qspi_read_register(dut, cs_mask=s25fl_mask, cmd=0x05, data_len=1)
            dut._log.info(f"    Status Register 1 value: {status_reg>>24:08b}")
            if ((status_reg>>24) & 0x02) == 0:
                raise ValueError("Failed to set Write Enable Latch (WEL) bit in Status Register!")
            dut._log.info("    WEL bit is set. Proceeding to write data...")

            dut._log.info(f"    Erasing Sector at 0x{current_addr:08X} with Sector Erase (0xD8) command...")
            await qspi_custom_transaction(
                dut=dut,
                cs_mask=s25fl_mask,
                cmd=0xD8, # Sector Eras
                cmd_mode=1,
                addr=current_addr,
                addr_mode=1,
                addr_len=0,
                dummy_len=0,
                data_mode=0,
                data_len=0,
                ddr=False
            )

            # Wait for Write-In-Progress (WIP) bit to clear
            dut._log.info("    Waiting for Write-In-Progress (WIP) bit to clear in Status Register 1...")
            await qspi_poll_wip_bit(dut, cs_mask=s25fl_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=15e-3)
            dut._log.info("    WIP bit cleared. Sector erased successfully.")

            # Check E_ERR flag in Status Register 1 to ensure the program was successful
            dut._log.info("    Verifying Program completed successfully by checking Status Register 1...")
            status_reg = await qspi_read_register(dut, cs_mask=s25fl_mask, cmd=0x05, data_len=1)
            dut._log.info(f"    Status Register 1 value: {status_reg>>24:08b}")
            if ((status_reg>>24) & 0x20) != 0:
                raise ValueError("Program failed! E_ERR bit is set in Status Register 1.")


            # Write Enable (WREN) must be sent before EVERY write/program command
            dut._log.info("    Sending Write Enable (0x06) command...")
            await qspi_write_command(dut, cs_mask=s25fl_mask, cmd=0x06)
            await Timer(500, unit="ns")
            await RisingEdge(dut.clk_i)

            # Send Read Status Register (0x05) to verify WEL bit is set
            dut._log.info("    Verifying Write Enable Latch (WEL) bit is set in Status Register 1...")
            status_reg = await qspi_read_register(dut, cs_mask=s25fl_mask, cmd=0x05, data_len=1)
            dut._log.info(f"    Status Register 1 value: {status_reg>>24:08b}")
            if ((status_reg>>24) & 0x02) == 0:
                raise ValueError("Failed to set Write Enable Latch (WEL) bit in Status Register!")
            dut._log.info("    WEL bit is set. Proceeding to write data...")
            
            await Timer(500, unit="ns")
            await RisingEdge(dut.clk_i)
            
            # Start the Write Transaction
            await qspi_write_transaction(
                dut=dut,
                cs_mask=s25fl_mask,
                cmd=cmd,
                cmd_mode=cmd_mode,
                addr=current_addr,
                addr_mode=addr_mode,
                addr_len=addr_len,
                data_mode=data_mode,
                data_len=test_data_len,
                data_words=payload_pool,
                ddr=False
            )
            
            # Wait for Write-In-Progress (WIP) bit to clear
            dut._log.info("    Waiting for Write-In-Progress (WIP) bit to clear in Status Register 1...")
            await qspi_poll_wip_bit(dut, cs_mask=s25fl_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=5e-3)
            dut._log.info("    WIP bit cleared. Write operation completed successfully.")

            # Check P_Error flag in Status Register 1 to ensure the program was successful
            dut._log.info("    Verifying Program completed successfully by checking Status Register 1...")
            status_reg = await qspi_read_register(dut, cs_mask=s25fl_mask, cmd=0x05, data_len=1)
            dut._log.info(f"    Status Register 1 value: {status_reg>>24:08b}")
            if ((status_reg>>24) & 0x40) != 0:
                raise ValueError("Program failed! P_Error bit is set in Status Register 1.")

            # Wait some time before reading back
            await Timer(10, unit="us")
            await RisingEdge(dut.clk_i)

            # VERIFICATION: Read the data back
            dut._log.info(f"    Verifying Written Data at 0x{current_addr:08X}...")
            readback_list = await qspi_read_transaction(
                dut=dut, 
                cs_mask=s25fl_mask, 
                cmd=0x03, # Fast Read
                cmd_mode=1, addr=current_addr, addr_mode=1, addr_len=0, dummy_len=0, data_mode=1, 
                data_len=test_data_len, ddr=False
            )

            dummy_dict = {current_addr: payload_pool}
            expected_list = get_expected_words(
                golden_dict=dummy_dict, 
                target_addr=current_addr, 
                num_words=expected_words,
                total_bytes=test_data_len, 
                endian="big"
            )
                
            # Compare what we told it to write against what we read back
            for i in range(expected_words):
                if readback_list[i] != expected_list[i]:
                    raise ValueError(f"WRITE CORRUPTION at Word {i}! Wrote 0x{payload_pool[i]:08X}, Read 0x{readback_list[i]:08X}")
                    
            dut._log.info("    Write and Readback perfectly MATCH!")
            scoreboard.record("S25FL Write", mode_name, passed=True)
            
            # Advance address for next loop so we don't overwrite the data we just successfully wrote
            current_addr += test_data_len

            await Timer(10, unit="us")
            await RisingEdge(dut.clk_i)

        except Exception as e:
            dut._log.error(f"    [!] FAILED: {str(e)}")
            scoreboard.record("S25FL Write", mode_name, passed=False, error_msg=str(e))
            
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)
    scoreboard.report(dut._log)


@cocotb.test()
async def test_w25q_write_read(dut):
    """Test a full write and readback cycle on the W25Q series flash memories.
    1. Do a full 256-byte Page Program (0x02) write to a known empty sector.
    2. Read back data using all supported read modes (Normal, Fast, Dual, Quad, DDR, QPI variant) and verify against the original payload.
    3. Do a random length write using all supported write modes (Page Program, Quad Page Program, QPI variant) and verify readback.
    """
    await init_qspi_master(dut)

    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)
    
    w25q_mask = 0b010
    scoreboard = Scoreboard()

    skip_all_reads = int(os.environ.get("SKIP_ALL_READS", "0"))
    skip_random_writes = int(os.environ.get("SKIP_RANDOM_WRITES", "0"))
    
    dut._log.info("Loading Raw Payload Pool...")
    payload_pool = load_raw_payload_from_any_file("ReadMe.TXT", endian="big")

    # Start at a known empty sector
    current_addr = 0x000000

    # ENABLE QUAD MODE for W25Q
    await w25q_quad_enable_routine(dut, cs_mask=w25q_mask)
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    # PAGE PROGRAM (0x02) INIT WRITE TEST
    dut._log.info(f"Commencing Write Tests starting at known empty address: 0x{current_addr:08X}...")
    try:
        test_data_len = 256  # Full Page Program
        expected_words = math.ceil(test_data_len / 4)
        
        dut._log.info(f" -> Executing Page Program (0x02) with {test_data_len} Bytes...")
        
        await Timer(10, unit="us")
        await RisingEdge(dut.clk_i)

        # Sector Erase (0x20) before every program
        dut._log.info("    Sending Write Enable (0x06) command...")
        await qspi_write_command(dut, cs_mask=w25q_mask, cmd=0x06)
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)

        dut._log.info(f"    Erasing Sector at 0x{current_addr:08X} with Sector Erase (0x20) command...")
        await qspi_custom_transaction(dut, cs_mask=w25q_mask, cmd=0x20, addr=current_addr)

        # Wait for BUSY bit to clear (15ms timeout for SE)
        dut._log.info("    Waiting for BUSY bit to clear in Status Register 1...")
        await qspi_poll_wip_bit(dut, cs_mask=w25q_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=15e-3)
        dut._log.info("    BUSY bit cleared. Sector erased successfully.")

        # Send Write Enable (WREN) before the Page Program
        dut._log.info("    Sending Write Enable (0x06) command...")
        await qspi_write_command(dut, cs_mask=w25q_mask, cmd=0x06)
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)

        # Start the Write Transaction
        await qspi_write_transaction(
            dut=dut,
            cs_mask=w25q_mask,
            cmd=0x02, # Page Program
            cmd_mode=1,
            addr=current_addr,
            addr_mode=1,
            addr_len=0,
            data_mode=1,
            data_len=test_data_len,
            data_words=payload_pool,
            ddr=False
        )

        # Wait for BUSY bit to clear
        dut._log.info("    Waiting for BUSY bit to clear in Status Register 1...")
        await qspi_poll_wip_bit(dut, cs_mask=w25q_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=5e-3)
        dut._log.info("    BUSY bit cleared. Write operation completed successfully.")

    except Exception as e:
        dut._log.error(f"    [!] FAILED: {str(e)}")
        scoreboard.record("W25Q Init Page Program", mode_name, passed=False, error_msg=str(e))

    # Wait some time before reading back
    await Timer(10, unit="us")
    await RisingEdge(dut.clk_i)

    # READBACK VERIFICATION: Read the data back using all supported read modes
    if not (skip_all_reads):
        read_modes = [
            ("Normal Read (0x03)",      0x03, 1, 1, 0, 0, 1, False), # (1-1-1)
            ("Fast Read (0x0B)",        0x0B, 1, 1, 0, 8, 1, False), # (1-1-1)
            ("Dual Output Read (0x3B)", 0x3B, 1, 1, 0, 8, 2, False), # (1-1-2)
            ("Quad Output Read (0x6B)", 0x6B, 1, 1, 0, 8, 3, False), # (1-1-4)
            ("Dual I/O Read (0xBB)",    0xBB, 1, 2, 0, 4, 2, False), # (1-2-2)
            ("Quad I/O Read (0xEB)",    0xEB, 1, 3, 0, 6, 3, False), # (1-4-4)
            ("DDR Fast Read (0x0D)",    0x0D, 1, 1, 0, 6, 1, True), # (1-1-1) DDR
            ("DDR Dual I/O Read (0xBD)",0xBD, 1, 2, 0, 6, 2, True), # (1-2-2) DDR
            ("DDR Quad I/O Read (0xED)",0xED, 1, 3, 0, 8, 3, True), # (1-4-4) DDR            
        ]

        for mode_name, cmd, cmd_mode, addr_mode, addr_len, dummy, data_mode, ddr in read_modes:
            try:
                dut._log.info(f" -> Executing {mode_name} for verification...")
                
                readback_list = await qspi_read_transaction(
                    dut=dut, 
                    cs_mask=w25q_mask, 
                    cmd=cmd, 
                    cmd_mode=cmd_mode, 
                    addr=current_addr,
                    addr_mode=addr_mode, 
                    addr_len=addr_len,
                    dummy_len=dummy, 
                    data_mode=data_mode,
                    data_len=test_data_len,
                    ddr=ddr
                )

                dummy_dict = {current_addr: payload_pool}
                expected_list = get_expected_words(
                    golden_dict=dummy_dict, 
                    target_addr=current_addr, 
                    num_words=expected_words,
                    total_bytes=test_data_len,
                    endian="big"
                )

                # Compare what we wrote against what we read back
                for i in range(expected_words):
                    if readback_list[i] != expected_list[i]:
                        dut._log.error(f"    [VERIFY] Word {i}: Expected 0x{expected_list[i]:08X}, Got 0x{readback_list[i]:08X}")
                        raise ValueError(f"DATA MISMATCH at Word {i}! Wrote 0x{expected_list[i]:08X}, Read 0x{readback_list[i]:08X}")

                dut._log.info(f"    Readback verification for {mode_name} PASSED!")
                scoreboard.record("W25Q Readback", mode_name, passed=True)

            except Exception as e:
                dut._log.error(f"    [!] FAILED: {str(e)}")
                scoreboard.record("W25Q Readback", mode_name, passed=False, error_msg=str(e))

            await Timer(500, unit="ns")
            await RisingEdge(dut.clk_i)

        # READBACK VERIFICATION: QPI Read Modes
        # Enter QPI Mode by sending the QPI Enable command (0x38)
        dut._log.info("Enabling QPI Mode for W25Q...")
        await qspi_write_command(dut, cs_mask=w25q_mask, cmd=0x38)
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)

        dut._log.info("QPI Mode enabled. Proceeding to test QPI read modes...")

        read_modes = [
            ("QPI Fast Read (0x0B)",    0x0B, 3, 3, 0, 6, 3, False), # (4-4-4)
            ("QPI Quad I/O Read (0xEB)",0xEB, 3, 3, 0, 6, 3, False), # (4-4-4)
            ("QPI DDR Read (0xED)",     0xED, 3, 3, 0, 8, 3, True), # (4-4-4) DDR
        ]

        for mode_name, cmd, cmd_mode, addr_mode, addr_len, dummy, data_mode, ddr in read_modes:
            try:
                dut._log.info(f" -> Executing {mode_name} for verification...")
                
                readback_list = await qspi_read_transaction(
                    dut=dut, 
                    cs_mask=w25q_mask, 
                    cmd=cmd, 
                    cmd_mode=cmd_mode, 
                    addr=current_addr,
                    addr_mode=addr_mode, 
                    addr_len=addr_len,
                    dummy_len=dummy, 
                    data_mode=data_mode,
                    data_len=test_data_len,
                    ddr=ddr
                )

                dummy_dict = {current_addr: payload_pool}
                expected_list = get_expected_words(
                    golden_dict=dummy_dict, 
                    target_addr=current_addr, 
                    num_words=expected_words,
                    total_bytes=test_data_len,
                    endian="big"
                )

                # Compare what we wrote against what we read back
                for i in range(expected_words):
                    dut._log.info(f"    [VERIFY] Word {i}: Expected 0x{expected_list[i]:08X}, Got 0x{readback_list[i]:08X}")
                    if readback_list[i] != expected_list[i]:
                        raise ValueError(f"DATA MISMATCH at Word {i}! Wrote 0x{expected_list[i]:08X}, Read 0x{readback_list[i]:08X}")

                dut._log.info(f"    Readback verification for {mode_name} PASSED!")
                scoreboard.record("W25Q QPI Readback", mode_name, passed=True)

            except Exception as e:
                dut._log.error(f"    [!] FAILED: {str(e)}")
                scoreboard.record("W25Q QPI Readback", mode_name, passed=False, error_msg=str(e))

            await Timer(500, unit="ns")
            await RisingEdge(dut.clk_i)

        # Exit QPI Mode by sending the QPI Disable command (0xFF)
        dut._log.info("Disabling QPI Mode for W25Q...")
        await qspi_write_command(dut, cs_mask=w25q_mask, cmd=0xFF, qpi=True)
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)
        dut._log.info("QPI Mode disabled. Proceeding to next test...")


    # RANDOM WRITE TEST: Page Program (0x02) and Quad Page Program (0x32) with random lengths
    current_addr += 0x001000  # Reset to known empty sector for random writes
    if not skip_random_writes:
        write_modes = [
            ("Page Program (0x02)", 0x02, 1, 1, 0, 1), # (1-1-1)
            ("Quad Page Program (0x32)", 0x32, 1, 1, 0, 3)  # (1-1-4)
        ]

        for i in range(5):  # Perform 5 random write tests
            for mode_name, cmd, cmd_mode, addr_mode, addr_len, data_mode in write_modes:
                try:
                    test_data_len = random.randint(64, 256)  # Random length between 64 and 256 bytes
                    expected_words = math.ceil(test_data_len / 4)

                    dut._log.info(f" -> Executing {mode_name} with {test_data_len} Bytes...")

                    await Timer(10, unit="us")
                    await RisingEdge(dut.clk_i)

                    # Send Write Enable (WREN) before the Page Program
                    dut._log.info("    Sending Write Enable (0x06) command...")
                    await qspi_write_command(dut, cs_mask=w25q_mask, cmd=0x06)
                    await Timer(500, unit="ns")
                    await RisingEdge(dut.clk_i)

                    # Start the Write Transaction
                    await qspi_write_transaction(
                        dut=dut,
                        cs_mask=w25q_mask,
                        cmd=cmd,
                        cmd_mode=cmd_mode,
                        addr=current_addr,
                        addr_mode=addr_mode,
                        addr_len=addr_len,
                        data_mode=data_mode,
                        data_len=test_data_len,
                        data_words=payload_pool,
                        ddr=False
                    )

                    # Wait for BUSY bit to clear
                    dut._log.info("    Waiting for BUSY bit to clear in Status Register 1...")
                    await qspi_poll_wip_bit(dut, cs_mask=w25q_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=5e-3)
                    dut._log.info("    BUSY bit cleared. Write operation completed successfully.")

                    # Wait some time before reading back
                    await Timer(10, unit="us")
                    await RisingEdge(dut.clk_i)

                    # VERIFICATION: Read the data back
                    dut._log.info(f"    Verifying Written Data at 0x{current_addr:08X}...")
                    readback_list = await qspi_read_transaction(
                        dut=dut, 
                        cs_mask=w25q_mask, 
                        cmd=0xEB, # Quad IO Read
                        cmd_mode=1, addr=current_addr, addr_mode=3, addr_len=0, dummy_len=6, data_mode=3, 
                        data_len=test_data_len, ddr=False
                    )

                    dummy_dict = {current_addr: payload_pool}
                    expected_list = get_expected_words(
                        golden_dict=dummy_dict, 
                        target_addr=current_addr, 
                        num_words=expected_words,
                        total_bytes=test_data_len, 
                        endian="big"
                    )

                    # Compare what we told it to write against what we read back
                    for i in range(expected_words):
                        dut._log.info(f"    [VERIFY] Word {i}: Expected 0x{expected_list[i]:08X}, Got 0x{readback_list[i]:08X}")
                        if readback_list[i] != expected_list[i]:
                            raise ValueError(f"WRITE CORRUPTION at Word {i}! Wrote 0x{payload_pool[i]:08X}, Read 0x{readback_list[i]:08X}")

                    dut._log.info("    Write and Readback perfectly MATCH!")
                    scoreboard.record("W25Q Random Write", mode_name, passed=True)

                    current_addr += 0x001000  # Advance to next sector for next random write

                except Exception as e:
                    dut._log.error(f"    [!] FAILED: {str(e)}")
                    scoreboard.record("W25Q Random Write", mode_name, passed=False, error_msg=str(e))


    # # RANDOM WRITE TEST: QPI Write Modes (BROKEN)
    # if not skip_random_writes:
    #     # Enter QPI Mode by sending the QPI Enable command (0x38)
    #     dut._log.info("Enabling QPI Mode for W25Q...")
    #     await qspi_write_command(dut, cs_mask=w25q_mask, cmd=0x38)
    #     await Timer(500, unit="ns")
    #     await RisingEdge(dut.clk_i)

    #     dut._log.info("QPI Mode enabled. Proceeding to test QPI write modes...")
    
    #     qpi_write_modes = [
    #         ("QPI Page Program (0x02)", 0x02, 3, 3, 0, 3), # (4-4-4)
    #     ]

    #     for mode_name, cmd, cmd_mode, addr_mode, addr_len, data_mode in qpi_write_modes:
    #         try:
    #             test_data_len = random.randint(64, 256)  # Random length between 64 and 256 bytes
    #             expected_words = math.ceil(test_data_len / 4)

    #             dut._log.info(f" -> Executing {mode_name} with {test_data_len} Bytes...")

    #             await Timer(10, unit="us")
    #             await RisingEdge(dut.clk_i)

    #             # Sector Erase (0x20) before every program
    #             dut._log.info("    Sending Write Enable (0x06) command...")
    #             await qspi_write_command(dut, cs_mask=w25q_mask, cmd=0x06, qpi=True)
    #             await Timer(500, unit="ns")
    #             await RisingEdge(dut.clk_i)

    #             dut._log.info(f"    Erasing Sector at 0x{current_addr:08X} with Sector Erase (0x20) command...")
    #             await qspi_custom_transaction(
    #                 dut=dut,
    #                 cs_mask=w25q_mask,
    #                 cmd=0x20,
    #                 cmd_mode=3,
    #                 addr=current_addr,
    #                 addr_mode=3,
    #                 addr_len=0,
    #                 dummy_len=0,
    #                 data_mode=0,
    #                 data_len=0,
    #                 ddr=False
    #             )

    #             # Wait for BUSY bit to clear (15ms timeout for SE)
    #             dut._log.info("    Waiting for BUSY bit to clear in Status Register 1...")
    #             await qspi_poll_wip_bit(dut, cs_mask=w25q_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=15e-3)
    #             dut._log.info("    BUSY bit cleared. Sector erased successfully.")

    #             # Send Write Enable (WREN) before the Page Program
    #             dut._log.info("    Sending Write Enable (0x06) command...")
    #             await qspi_write_command(dut, cs_mask=w25q_mask, cmd=0x06, qpi=True)
    #             await Timer(500, unit="ns")
    #             await RisingEdge(dut.clk_i)

    #             # Start the Write Transaction
    #             await qspi_write_transaction(
    #                 dut=dut,
    #                 cs_mask=w25q_mask,
    #                 cmd=cmd,
    #                 cmd_mode=cmd_mode,
    #                 addr=current_addr,
    #                 addr_mode=addr_mode,
    #                 addr_len=addr_len,
    #                 data_mode=data_mode,
    #                 data_len=test_data_len,
    #                 data_words=payload_pool,
    #                 ddr=False
    #             )

    #             # Wait for BUSY bit to clear (10ms timeout for PP)
    #             dut._log.info("    Waiting for BUSY bit to clear in Status Register 1...")
    #             await qspi_poll_wip_bit(dut, cs_mask=w25q_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=5e-3)
    #             dut._log.info("    BUSY bit cleared. Write operation completed successfully.")

    #             # Wait some time before reading back
    #             await Timer(10, unit="us")
    #             await RisingEdge(dut.clk_i)

    #             # VERIFICATION: Read the data back
    #             dut._log.info(f"    Verifying Written Data at 0x{current_addr:08X}...")
    #             readback_list = await qspi_read_transaction(
    #                 dut=dut, 
    #                 cs_mask=w25q_mask, 
    #                 cmd=0x6B, # Quad IO Read
    #                 cmd_mode=3, addr=current_addr, addr_mode=3, addr_len=0, dummy_len=6, data_mode=3, 
    #                 data_len=test_data_len, ddr=False
    #             )

    #             dummy_dict = {current_addr: payload_pool}
    #             expected_list = get_expected_words(
    #                 golden_dict=dummy_dict, 
    #                 target_addr=current_addr, 
    #                 num_words=expected_words,
    #                 total_bytes=test_data_len, 
    #                 endian="big"
    #             )

    #             # Compare what we told it to write against what we read back
    #             for i in range(expected_words):
    #                 dut._log.info(f"    [VERIFY] Word {i}: Expected 0x{expected_list[i]:08X}, Got 0x{readback_list[i]:08X}")
    #                 if readback_list[i] != expected_list[i]:
    #                     raise ValueError(f"WRITE CORRUPTION at Word {i}! Wrote 0x{payload_pool[i]:08X}, Read 0x{readback_list[i]:08X}")

    #             dut._log.info("    Write and Readback perfectly MATCH!")
    #             scoreboard.record("W25Q Random Write", mode_name, passed=True)

    #         except Exception as e:
    #             dut._log.error(f"    [!] FAILED: {str(e)}")
    #             scoreboard.record("W25Q Random Write", mode_name, passed=False, error_msg=str(e))

    #     # Exit QPI Mode by sending the QPI Disable command (0xFF)
    #     dut._log.info("Disabling QPI Mode for W25Q...")
    #     await qspi_write_command(dut, cs_mask=w25q_mask, cmd=0xFF, qpi=True)
    #     await Timer(500, unit="ns")
    #     await RisingEdge(dut.clk_i)
    #     dut._log.info("QPI Mode disabled. Proceeding to next test...")
        

    # FINAL VERDICT
    scoreboard.report(dut._log)


@cocotb.test()
async def test_mx25l_write_read(dut):
    """Test a full write and readback cycle on the MX25L series flash memories.
    Each three steps below performed for both 3-byte and 4-byte addressing modes:
    1. Do a full 256-byte Page Program (0x02) write to a known empty sector.
    2. Read back data using all supported read modes (Normal, Fast, Dual, Quad, DDR, QPI variant) and verify against the original payload.
    3. Do a random length write using all supported write modes (Page Program, Quad Page Program, QPI variant) and verify readback.
    """
    await init_qspi_master(dut)

    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)
    
    mx25l_mask = 0b100
    scoreboard = Scoreboard()

    skip_all_reads = int(os.environ.get("SKIP_ALL_READS", "0"))
    skip_random_writes = int(os.environ.get("SKIP_RANDOM_WRITES", "0"))
    
    dut._log.info("Loading Raw Payload Pool...")
    payload_pool = load_raw_payload_from_any_file("ReadMe.TXT", endian="big")

    # Start at a known empty sector
    current_addr = 0x000000

    # ENABLE QUAD MODE for MX25L
    await mx25l_quad_enable_routine(dut, cs_mask=mx25l_mask)
    await Timer(500, unit="ns")
    await RisingEdge(dut.clk_i)

    # ======================== 3 BYTE ADDRESSING MODE TESTS ========================
    dut._log.info("COMMENCING 3-BYTE ADDERSSING MODE TESTS FOR MX25L...")

    # PAGE PROGRAM (0x02) INIT WRITE TEST
    dut._log.info(f"Commencing Write Tests starting at known empty address: 0x{current_addr:08X}...")
    try:
        test_data_len = 256  # Full Page Program
        expected_words = math.ceil(test_data_len / 4)
        
        dut._log.info(f" -> Executing Page Program (0x02) with {test_data_len} Bytes...")
        
        await Timer(10, unit="us")
        await RisingEdge(dut.clk_i)

        # Sector Erase (0x20) before every program
        dut._log.info("    Sending Write Enable (0x06) command...")
        await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0x06)
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)

        dut._log.info(f"    Erasing Sector at 0x{current_addr:08X} with Sector Erase (0x20) command...")
        await qspi_custom_transaction(dut, cs_mask=mx25l_mask, cmd_mode=1, addr_mode=1, addr_len=0, cmd=0x20, addr=current_addr)

        # Wait for BUSY bit to clear (15ms timeout for SE)
        dut._log.info("    Waiting for BUSY bit to clear in Status Register 1...")
        await qspi_poll_wip_bit(dut, cs_mask=mx25l_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=15e-3)
        dut._log.info("    BUSY bit cleared. Sector erased successfully.")

        # Send Write Enable (WREN) before the Page Program
        dut._log.info("    Sending Write Enable (0x06) command...")
        await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0x06)
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)

        # Start the Write Transaction
        await qspi_write_transaction(
            dut=dut,
            cs_mask=mx25l_mask,
            cmd=0x02, # Page Program
            cmd_mode=1,
            addr=current_addr,
            addr_mode=1,
            addr_len=0,
            data_mode=1,
            data_len=test_data_len,
            data_words=payload_pool,
            ddr=False
        )

        # Wait for BUSY bit to clear
        dut._log.info("    Waiting for BUSY bit to clear in Status Register 1...")
        await qspi_poll_wip_bit(dut, cs_mask=mx25l_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=5e-3)
        dut._log.info("    BUSY bit cleared. Write operation completed successfully.")

    except Exception as e:
        dut._log.error(f"    [!] FAILED: {str(e)}")
        scoreboard.record("MX25L Init Page Program 3-Byte Addressing", mode_name, passed=False, error_msg=str(e))

    # Wait some time before reading back
    await Timer(10, unit="us")
    await RisingEdge(dut.clk_i)

    # READBACK VERIFICATION: Read the data back using all supported read modes
    if not (skip_all_reads):
        read_modes = [
            ("Normal Read (0x03)",      0x03, 1, 1, 0, 0, 1, False), # (1-1-1)
            ("Fast Read (0x0B)",        0x0B, 1, 1, 0, 8, 1, False), # (1-1-1)
            ("Dual Output Read (0x3B)", 0x3B, 1, 1, 0, 8, 2, False), # (1-1-2)
            ("Quad Output Read (0x6B)", 0x6B, 1, 1, 0, 8, 3, False), # (1-1-4)
            ("Dual I/O Read (0xBB)",    0xBB, 1, 2, 0, 4, 2, False), # (1-2-2)
            ("Quad I/O Read (0xEB)",    0xEB, 1, 3, 0, 6, 3, False), # (1-4-4)
            ("DDR Fast Read (0x0D)",    0x0D, 1, 1, 0, 8, 1, True), # (1-1-1) DDR
            ("DDR Dual I/O Read (0xBD)",0xBD, 1, 2, 0, 4, 2, True), # (1-2-2) DDR
            ("DDR Quad I/O Read (0xED)",0xED, 1, 3, 0, 6, 3, True), # (1-4-4) DDR            
        ]

        for mode_name, cmd, cmd_mode, addr_mode, addr_len, dummy, data_mode, ddr in read_modes:
            try:
                test_data_len = 256
                expected_words = math.ceil(test_data_len / 4)

                dut._log.info(f" -> Executing {mode_name} for verification...")
                
                readback_list = await qspi_read_transaction(
                    dut=dut, 
                    cs_mask=mx25l_mask, 
                    cmd=cmd, 
                    cmd_mode=cmd_mode, 
                    addr=current_addr,
                    addr_mode=addr_mode, 
                    addr_len=addr_len,
                    dummy_len=dummy, 
                    data_mode=data_mode,
                    data_len=test_data_len,
                    ddr=ddr
                )

                dummy_dict = {current_addr: payload_pool}
                expected_list = get_expected_words(
                    golden_dict=dummy_dict, 
                    target_addr=current_addr, 
                    num_words=expected_words,
                    total_bytes=test_data_len,
                    endian="big"
                )

                # Compare what we wrote against what we read back
                for i in range(expected_words):
                    if readback_list[i] != expected_list[i]:
                        dut._log.error(f"    [VERIFY] Word {i}: Expected 0x{expected_list[i]:08X}, Got 0x{readback_list[i]:08X}")
                        raise ValueError(f"DATA MISMATCH at Word {i}! Wrote 0x{expected_list[i]:08X}, Read 0x{readback_list[i]:08X}")

                dut._log.info(f"    Readback verification for {mode_name} PASSED!")
                scoreboard.record("MX25L Readback 3-Byte Addressing", mode_name, passed=True)

            except Exception as e:
                dut._log.error(f"    [!] FAILED: {str(e)}")
                scoreboard.record("MX25L Readback 3-Byte Addressing", mode_name, passed=False, error_msg=str(e))

            await Timer(500, unit="ns")
            await RisingEdge(dut.clk_i)

        # READBACK VERIFICATION: QPI Read Modes
        # Enter QPI Mode by sending the QPI Enable command (0x35)
        dut._log.info("Enabling QPI Mode for MX25L...")
        await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0x35)
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)

        dut._log.info("QPI Mode enabled. Proceeding to test QPI read modes...")

        read_modes = [
            ("QPI Quad I/O Read (0xEB)", 0xEB, 3, 3, 0, 6, 3, False), # (4-4-4)
            ("QPI Quad DDR Read (0xED)", 0xED, 3, 3, 0, 6, 3, True), # (4-4-4) DDR
        ]

        for mode_name, cmd, cmd_mode, addr_mode, addr_len, dummy, data_mode, ddr in read_modes:
            try:
                test_data_len = 256  # Fixed length for QPI read tests
                expected_words = math.ceil(test_data_len / 4)

                dut._log.info(f" -> Executing {mode_name} for verification...")
                
                readback_list = await qspi_read_transaction(
                    dut=dut, 
                    cs_mask=mx25l_mask, 
                    cmd=cmd, 
                    cmd_mode=cmd_mode, 
                    addr=current_addr,
                    addr_mode=addr_mode, 
                    addr_len=addr_len,
                    dummy_len=dummy, 
                    data_mode=data_mode,
                    data_len=test_data_len,
                    ddr=ddr
                )

                dummy_dict = {current_addr: payload_pool}
                expected_list = get_expected_words(
                    golden_dict=dummy_dict, 
                    target_addr=current_addr, 
                    num_words=expected_words,
                    total_bytes=test_data_len,
                    endian="big"
                )

                # Compare what we wrote against what we read back
                for i in range(expected_words):
                    dut._log.info(f"    [VERIFY] Word {i}: Expected 0x{expected_list[i]:08X}, Got 0x{readback_list[i]:08X}")
                    if readback_list[i] != expected_list[i]:
                        raise ValueError(f"DATA MISMATCH at Word {i}! Wrote 0x{expected_list[i]:08X}, Read 0x{readback_list[i]:08X}")

                dut._log.info(f"    Readback verification for {mode_name} PASSED!")
                scoreboard.record("MX25L Readback 3-Byte Addressing", mode_name, passed=True)

            except Exception as e:
                dut._log.error(f"    [!] FAILED: {str(e)}")
                scoreboard.record("MX25L Readback 3-Byte Addressing", mode_name, passed=False, error_msg=str(e))

            await Timer(500, unit="ns")
            await RisingEdge(dut.clk_i)

        # Exit QPI Mode by sending the QPI Disable command (0xF5)
        dut._log.info("Disabling QPI Mode for MX25L...")
        await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0xF5, qpi=True)
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)
        dut._log.info("QPI Mode disabled. Proceeding to next test...")


    # RANDOM WRITE TEST: Page Program (0x02) and Quad Page Program (0x38) with random lengths
    current_addr += 0x001000  # Reset to known empty sector for random writes
    if not skip_random_writes:
        write_modes = [
            ("Page Program (0x02)", 0x02, 1, 1, 0, 1), # (1-1-1)
            ("Quad Page Program (0x38)", 0x38, 1, 3, 0, 3)  # (1-4-4)
        ]

        for i in range(5):  # Perform 5 random write tests
            for mode_name, cmd, cmd_mode, addr_mode, addr_len, data_mode in write_modes:
                try:
                    test_data_len = random.randint(64, 256)  # Random length between 64 and 256 bytes
                    expected_words = math.ceil(test_data_len / 4)

                    dut._log.info(f" -> Executing {mode_name} with {test_data_len} Bytes...")

                    await Timer(10, unit="us")
                    await RisingEdge(dut.clk_i)

                    # Send Write Enable (WREN) before the Page Program
                    dut._log.info("    Sending Write Enable (0x06) command...")
                    await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0x06)
                    await Timer(500, unit="ns")
                    await RisingEdge(dut.clk_i)

                    # Start the Write Transaction
                    await qspi_write_transaction(
                        dut=dut,
                        cs_mask=mx25l_mask,
                        cmd=cmd,
                        cmd_mode=cmd_mode,
                        addr=current_addr,
                        addr_mode=addr_mode,
                        addr_len=addr_len,
                        data_mode=data_mode,
                        data_len=test_data_len,
                        data_words=payload_pool,
                        ddr=False
                    )

                    # Wait for BUSY bit to clear
                    dut._log.info("    Waiting for BUSY bit to clear in Status Register 1...")
                    await qspi_poll_wip_bit(dut, cs_mask=mx25l_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=5e-3)
                    dut._log.info("    BUSY bit cleared. Write operation completed successfully.")

                    # Wait some time before reading back
                    await Timer(10, unit="us")
                    await RisingEdge(dut.clk_i)

                    # VERIFICATION: Read the data back
                    dut._log.info(f"    Verifying Written Data at 0x{current_addr:08X}...")
                    readback_list = await qspi_read_transaction(
                        dut=dut, 
                        cs_mask=mx25l_mask, 
                        cmd=0xEB, # Quad IO Read
                        cmd_mode=1, addr=current_addr, addr_mode=3, addr_len=0, dummy_len=6, data_mode=3, 
                        data_len=test_data_len, ddr=False
                    )

                    dummy_dict = {current_addr: payload_pool}
                    expected_list = get_expected_words(
                        golden_dict=dummy_dict, 
                        target_addr=current_addr, 
                        num_words=expected_words,
                        total_bytes=test_data_len, 
                        endian="big"
                    )

                    # Compare what we told it to write against what we read back
                    for i in range(expected_words):
                        dut._log.info(f"    [VERIFY] Word {i}: Expected 0x{expected_list[i]:08X}, Got 0x{readback_list[i]:08X}")
                        if readback_list[i] != expected_list[i]:
                            raise ValueError(f"WRITE CORRUPTION at Word {i}! Wrote 0x{payload_pool[i]:08X}, Read 0x{readback_list[i]:08X}")

                    dut._log.info("    Write and Readback perfectly MATCH!")
                    scoreboard.record("MX25L Random Write 3-Byte Addressing", mode_name, passed=True)

                    current_addr += 0x001000  # Advance to next sector for next random write

                except Exception as e:
                    dut._log.error(f"    [!] FAILED: {str(e)}")
                    scoreboard.record("MX25L Random Write 3-Byte Addressing", mode_name, passed=False, error_msg=str(e))


        # RANDOM WRITE TEST: QPI Write Modes (BROKEN)
    # if not skip_random_writes:
    #     # Enter QPI Mode by sending the QPI Enable command (0x35)
    #     dut._log.info("Enabling QPI Mode for MX25L...")
    #     await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0x35)
    #     await Timer(500, unit="ns")
    #     await RisingEdge(dut.clk_i)

    #     dut._log.info("QPI Mode enabled. Proceeding to test QPI write modes...")
    
    #     qpi_write_modes = [
    #         ("QPI Page Program (0x02)", 0x02, 3, 3, 0, 3), # (4-4-4)
    #     ]

    #     for i in range(5):  # Perform 5 random QPI write tests
    #         for mode_name, cmd, cmd_mode, addr_mode, addr_len, data_mode in qpi_write_modes:
    #             try:
    #                 test_data_len = random.randint(64, 256)  # Random length between 64 and 256 bytes
    #                 expected_words = math.ceil(test_data_len / 4)

    #                 dut._log.info(f" -> Executing {mode_name} with {test_data_len} Bytes...")

    #                 await Timer(10, unit="us")
    #                 await RisingEdge(dut.clk_i)

    #                 # Send Write Enable (WREN) before the Page Program
    #                 dut._log.info("    Sending Write Enable (0x06) command...")
    #                 await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0x06, qpi=True)
    #                 await Timer(500, unit="ns")
    #                 await RisingEdge(dut.clk_i)

    #                 # Start the Write Transaction
    #                 await qspi_write_transaction(
    #                     dut=dut,
    #                     cs_mask=mx25l_mask,
    #                     cmd=cmd,
    #                     cmd_mode=cmd_mode,
    #                     addr=current_addr,
    #                     addr_mode=addr_mode,
    #                     addr_len=addr_len,
    #                     data_mode=data_mode,
    #                     data_len=test_data_len,
    #                     data_words=payload_pool,
    #                     ddr=False
    #                 )

    #                 # Wait for BUSY bit to clear (10ms timeout for PP)
    #                 dut._log.info("    Waiting for BUSY bit to clear in Status Register 1...")
    #                 await qspi_poll_wip_bit(dut, cs_mask=mx25l_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=5e-3)
    #                 dut._log.info("    BUSY bit cleared. Write operation completed successfully.")

    #                 # Wait some time before reading back
    #                 await Timer(10, unit="us")
    #                 await RisingEdge(dut.clk_i)

    #                 # VERIFICATION: Read the data back
    #                 dut._log.info(f"    Verifying Written Data at 0x{current_addr:08X}...")
    #                 readback_list = await qspi_read_transaction(
    #                     dut=dut, 
    #                     cs_mask=mx25l_mask, 
    #                     cmd=0x6B, # Quad IO Read
    #                     cmd_mode=3, addr=current_addr, addr_mode=3, addr_len=0, dummy_len=6, data_mode=3, 
    #                     data_len=test_data_len, ddr=False
    #                 )

    #                 dummy_dict = {current_addr: payload_pool}
    #                 expected_list = get_expected_words(
    #                     golden_dict=dummy_dict, 
    #                     target_addr=current_addr, 
    #                     num_words=expected_words,
    #                     total_bytes=test_data_len, 
    #                     endian="big"
    #                 )

    #                 # Compare what we told it to write against what we read back
    #                 for i in range(expected_words):
    #                     dut._log.info(f"    [VERIFY] Word {i}: Expected 0x{expected_list[i]:08X}, Got 0x{readback_list[i]:08X}")
    #                     if readback_list[i] != expected_list[i]:
    #                         raise ValueError(f"WRITE CORRUPTION at Word {i}! Wrote 0x{payload_pool[i]:08X}, Read 0x{readback_list[i]:08X}")

    #                 dut._log.info("    Write and Readback perfectly MATCH!")
    #                 scoreboard.record("MX25L Random Write 3-Byte Addressing", mode_name, passed=True)

    #                 current_addr += 0x001000  # Advance to next sector for next random write
                    
    #             except Exception as e:
    #                 dut._log.error(f"    [!] FAILED: {str(e)}")
    #                 scoreboard.record("MX25L Random Write 3-Byte Addressing", mode_name, passed=False, error_msg=str(e))

    #     # Exit QPI Mode by sending the QPI Disable command (0xF5)
    #     dut._log.info("Disabling QPI Mode for MX25L...")
    #     await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0xF5, qpi=True)
    #     await Timer(500, unit="ns")
    #     await RisingEdge(dut.clk_i)
    #     dut._log.info("QPI Mode disabled. Proceeding to next test...")
        

    # ======================== 4 BYTE ADDRESSING MODE TESTS ========================
    dut._log.info("COMMENCING 4-BYTE ADDRESSING MODE TESTS FOR MX25L...")

    current_addr = 0x0100_0000

    # Enter 4-Byte mode
    dut._log.info("Enabling 4-Byte Addressing Mode for MX25L...")
    await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0xB7)

    # PAGE PROGRAM (0x02) INIT WRITE TEST
    dut._log.info(f"Commencing Write Tests starting at known empty address: 0x{current_addr:08X}...")
    try:
        test_data_len = 256  # Full Page Program
        expected_words = math.ceil(test_data_len / 4)
        
        dut._log.info(f" -> Executing Page Program (0x02) with {test_data_len} Bytes...")
        
        await Timer(10, unit="us")
        await RisingEdge(dut.clk_i)

        # Sector Erase (0x20) before every program
        dut._log.info("    Sending Write Enable (0x06) command...")
        await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0x06)
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)

        dut._log.info(f"    Erasing Sector at 0x{current_addr:08X} with Sector Erase (0x20) command...")
        await qspi_custom_transaction(dut, cs_mask=mx25l_mask, cmd_mode=1, addr_mode=1, addr_len=1, cmd=0x20, addr=current_addr)

        # Wait for BUSY bit to clear (15ms timeout for SE)
        dut._log.info("    Waiting for BUSY bit to clear in Status Register 1...")
        await qspi_poll_wip_bit(dut, cs_mask=mx25l_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=15e-3)
        dut._log.info("    BUSY bit cleared. Sector erased successfully.")

        # Send Write Enable (WREN) before the Page Program
        dut._log.info("    Sending Write Enable (0x06) command...")
        await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0x06)
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)

        # Start the Write Transaction
        await qspi_write_transaction(
            dut=dut,
            cs_mask=mx25l_mask,
            cmd=0x02, # Page Program
            cmd_mode=1,
            addr=current_addr,
            addr_mode=1,
            addr_len=1,
            data_mode=1,
            data_len=test_data_len,
            data_words=payload_pool,
            ddr=False
        )

        # Wait for BUSY bit to clear
        dut._log.info("    Waiting for BUSY bit to clear in Status Register 1...")
        await qspi_poll_wip_bit(dut, cs_mask=mx25l_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=5e-3)
        dut._log.info("    BUSY bit cleared. Write operation completed successfully.")

    except Exception as e:
        dut._log.error(f"    [!] FAILED: {str(e)}")
        scoreboard.record("MX25L Init Page Program 4-Byte Addressing", mode_name, passed=False, error_msg=str(e))

    # Wait some time before reading back
    await Timer(10, unit="us")
    await RisingEdge(dut.clk_i)

    # READBACK VERIFICATION: Read the data back using all supported read modes
    if not (skip_all_reads):
        read_modes = [
            ("Normal Read (0x03)",      0x03, 1, 1, 1, 0, 1, False), # (1-1-1)
            ("Fast Read (0x0B)",        0x0B, 1, 1, 1, 8, 1, False), # (1-1-1)
            ("Dual Output Read (0x3B)", 0x3B, 1, 1, 1, 8, 2, False), # (1-1-2)
            ("Quad Output Read (0x6B)", 0x6B, 1, 1, 1, 8, 3, False), # (1-1-4)
            ("Dual I/O Read (0xBB)",    0xBB, 1, 2, 1, 4, 2, False), # (1-2-2)
            ("Quad I/O Read (0xEB)",    0xEB, 1, 3, 1, 6, 3, False), # (1-4-4)
            ("DDR Fast Read (0x0D)",    0x0D, 1, 1, 1, 8, 1, True), # (1-1-1) DDR
            ("DDR Dual I/O Read (0xBD)",0xBD, 1, 2, 1, 4, 2, True), # (1-2-2) DDR
            ("DDR Quad I/O Read (0xED)",0xED, 1, 3, 1, 6, 3, True), # (1-4-4) DDR

            # Dedicated 4-Byte Addressing Read Modes
            ("4-Byte Normal Read (0x13)",      0x13, 1, 1, 1, 0, 1, False), # (1-1-1)
            ("4-Byte Fast Read (0x0C)",        0x0C, 1, 1, 1, 8, 1, False), # (1-1-1)
            ("4-Byte Dual Output Read (0x3C)", 0x3C, 1, 1, 1, 8, 2, False), # (1-1-2)
            ("4-Byte Quad Output Read (0x6C)", 0x6C, 1, 1, 1, 8, 3, False), # (1-1-4)
            ("4-Byte Dual I/O Read (0xBC)",    0xBC, 1, 2, 1, 4, 2, False), # (1-2-2)
            ("4-Byte Quad I/O Read (0xEC)",    0xEC, 1, 3, 1, 6, 3, False), # (1-4-4)
            ("4-Byte DDR Fast Read (0x0E)",    0x0E, 1, 1, 1, 8, 1, True), # (1-1-1) DDR
            ("4-Byte DDR Dual I/O Read (0xBE)",0xBE, 1, 2, 1, 4, 2, True), # (1-2-2) DDR
            ("4-Byte DDR Quad I/O Read (0xEE)",0xEE, 1, 3, 1, 6, 3, True), # (1-4-4) DDR

        ]

        for mode_name, cmd, cmd_mode, addr_mode, addr_len, dummy, data_mode, ddr in read_modes:
            try:
                test_data_len = 256
                expected_words = math.ceil(test_data_len / 4)

                dut._log.info(f" -> Executing {mode_name} for verification...")
                
                readback_list = await qspi_read_transaction(
                    dut=dut, 
                    cs_mask=mx25l_mask, 
                    cmd=cmd, 
                    cmd_mode=cmd_mode, 
                    addr=current_addr,
                    addr_mode=addr_mode, 
                    addr_len=addr_len,
                    dummy_len=dummy, 
                    data_mode=data_mode,
                    data_len=test_data_len,
                    ddr=ddr
                )

                dummy_dict = {current_addr: payload_pool}
                expected_list = get_expected_words(
                    golden_dict=dummy_dict, 
                    target_addr=current_addr, 
                    num_words=expected_words,
                    total_bytes=test_data_len,
                    endian="big"
                )

                # Compare what we wrote against what we read back
                for i in range(expected_words):
                    if readback_list[i] != expected_list[i]:
                        dut._log.error(f"    [VERIFY] Word {i}: Expected 0x{expected_list[i]:08X}, Got 0x{readback_list[i]:08X}")
                        raise ValueError(f"DATA MISMATCH at Word {i}! Wrote 0x{expected_list[i]:08X}, Read 0x{readback_list[i]:08X}")

                dut._log.info(f"    Readback verification for {mode_name} PASSED!")
                scoreboard.record("MX25L Readback 4-Byte Addressing", mode_name, passed=True)

            except Exception as e:
                dut._log.error(f"    [!] FAILED: {str(e)}")
                scoreboard.record("MX25L Readback 4-Byte Addressing", mode_name, passed=False, error_msg=str(e))

            await Timer(500, unit="ns")
            await RisingEdge(dut.clk_i)

        # READBACK VERIFICATION: QPI Read Modes
        # Enter QPI Mode by sending the QPI Enable command (0x35)
        dut._log.info("Enabling QPI Mode for MX25L...")
        await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0x35)
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)

        dut._log.info("QPI Mode enabled. Proceeding to test QPI read modes...")

        read_modes = [
            ("QPI Quad I/O Read (0xEB)", 0xEB, 3, 3, 1, 6, 3, False), # (4-4-4)
            ("QPI Quad DDR Read (0xED)", 0xED, 3, 3, 1, 6, 3, True), # (4-4-4) DDR

            ("4-Byte QPI Quad I/O Read (0xEC)",    0xEC, 3, 3, 1, 6, 3, False), # (4-4-4)
            ("4-Byte QPI DDR Quad I/O Read (0xEE)",0xEE, 3, 3, 1, 6, 3, True), # (4-4-4) DDR
        ]

        for mode_name, cmd, cmd_mode, addr_mode, addr_len, dummy, data_mode, ddr in read_modes:
            try:
                test_data_len = random.randint(64, 256)  # Random length between 64 and 256 bytes
                expected_words = math.ceil(test_data_len / 4)

                dut._log.info(f" -> Executing {mode_name} for verification...")
                
                readback_list = await qspi_read_transaction(
                    dut=dut, 
                    cs_mask=mx25l_mask, 
                    cmd=cmd, 
                    cmd_mode=cmd_mode, 
                    addr=current_addr,
                    addr_mode=addr_mode, 
                    addr_len=addr_len,
                    dummy_len=dummy, 
                    data_mode=data_mode,
                    data_len=test_data_len,
                    ddr=ddr
                )

                dummy_dict = {current_addr: payload_pool}
                expected_list = get_expected_words(
                    golden_dict=dummy_dict, 
                    target_addr=current_addr, 
                    num_words=expected_words,
                    total_bytes=test_data_len,
                    endian="big"
                )

                # Compare what we wrote against what we read back
                for i in range(expected_words):
                    dut._log.info(f"    [VERIFY] Word {i}: Expected 0x{expected_list[i]:08X}, Got 0x{readback_list[i]:08X}")
                    if readback_list[i] != expected_list[i]:
                        raise ValueError(f"DATA MISMATCH at Word {i}! Wrote 0x{expected_list[i]:08X}, Read 0x{readback_list[i]:08X}")

                dut._log.info(f"    Readback verification for {mode_name} PASSED!")
                scoreboard.record("MX25L Readback 4-Byte Addressing", mode_name, passed=True)

            except Exception as e:
                dut._log.error(f"    [!] FAILED: {str(e)}")
                scoreboard.record("MX25L Readback 4-Byte Addressing", mode_name, passed=False, error_msg=str(e))

            await Timer(500, unit="ns")
            await RisingEdge(dut.clk_i)

        # Exit QPI Mode by sending the QPI Disable command (0xF5)
        dut._log.info("Disabling QPI Mode for MX25L...")
        await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0xF5, qpi=True)
        await Timer(500, unit="ns")
        await RisingEdge(dut.clk_i)
        dut._log.info("QPI Mode disabled. Proceeding to next test...")


    # RANDOM WRITE TEST: Page Program (0x02) and Quad Page Program (0x38) with random lengths
    current_addr += 0x001000  # Reset to known empty sector for random writes
    if not skip_random_writes:
        write_modes = [
            ("Page Program (0x02)", 0x02, 1, 1, 1, 1), # (1-1-1)
            ("Quad Page Program (0x38)", 0x38, 1, 3, 1, 3)  # (1-4-4)
        ]

        for i in range(5):  # Perform 5 random write tests
            for mode_name, cmd, cmd_mode, addr_mode, addr_len, data_mode in write_modes:
                try:
                    test_data_len = random.randint(64, 256)  # Random length between 64 and 256 bytes
                    expected_words = math.ceil(test_data_len / 4)

                    dut._log.info(f" -> Executing {mode_name} with {test_data_len} Bytes...")

                    await Timer(10, unit="us")
                    await RisingEdge(dut.clk_i)

                    # Send Write Enable (WREN) before the Page Program
                    dut._log.info("    Sending Write Enable (0x06) command...")
                    await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0x06)
                    await Timer(500, unit="ns")
                    await RisingEdge(dut.clk_i)

                    # Start the Write Transaction
                    await qspi_write_transaction(
                        dut=dut,
                        cs_mask=mx25l_mask,
                        cmd=cmd,
                        cmd_mode=cmd_mode,
                        addr=current_addr,
                        addr_mode=addr_mode,
                        addr_len=addr_len,
                        data_mode=data_mode,
                        data_len=test_data_len,
                        data_words=payload_pool,
                        ddr=False
                    )

                    # Wait for BUSY bit to clear
                    dut._log.info("    Waiting for BUSY bit to clear in Status Register 1...")
                    await qspi_poll_wip_bit(dut, cs_mask=mx25l_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=5e-3)
                    dut._log.info("    BUSY bit cleared. Write operation completed successfully.")

                    # Wait some time before reading back
                    await Timer(10, unit="us")
                    await RisingEdge(dut.clk_i)

                    # VERIFICATION: Read the data back
                    dut._log.info(f"    Verifying Written Data at 0x{current_addr:08X}...")
                    readback_list = await qspi_read_transaction(
                        dut=dut, 
                        cs_mask=mx25l_mask, 
                        cmd=0xEB, # Quad IO Read
                        cmd_mode=1, addr=current_addr, addr_mode=3, addr_len=1, dummy_len=6, data_mode=3, 
                        data_len=test_data_len, ddr=False
                    )

                    dummy_dict = {current_addr: payload_pool}
                    expected_list = get_expected_words(
                        golden_dict=dummy_dict, 
                        target_addr=current_addr, 
                        num_words=expected_words,
                        total_bytes=test_data_len, 
                        endian="big"
                    )

                    # Compare what we told it to write against what we read back
                    for i in range(expected_words):
                        dut._log.info(f"    [VERIFY] Word {i}: Expected 0x{expected_list[i]:08X}, Got 0x{readback_list[i]:08X}")
                        if readback_list[i] != expected_list[i]:
                            raise ValueError(f"WRITE CORRUPTION at Word {i}! Wrote 0x{payload_pool[i]:08X}, Read 0x{readback_list[i]:08X}")

                    dut._log.info("    Write and Readback perfectly MATCH!")
                    scoreboard.record("MX25L Random Write 4-Byte Addressing", mode_name, passed=True)

                    current_addr += 0x001000  # Advance to next sector for next random write

                except Exception as e:
                    dut._log.error(f"    [!] FAILED: {str(e)}")
                    scoreboard.record("MX25L Random Write 4-Byte Addressing", mode_name, passed=False, error_msg=str(e))


        # RANDOM WRITE TEST: QPI Write Modes (BROKEN)
    #     # Enter QPI Mode by sending the QPI Enable command (0x35)
    #     dut._log.info("Enabling QPI Mode for MX25L...")
    #     await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0x35)
    #     await Timer(500, unit="ns")
    #     await RisingEdge(dut.clk_i)

    #     dut._log.info("QPI Mode enabled. Proceeding to test QPI write modes...")
    
    #     qpi_write_modes = [
    #         ("QPI Page Program (0x02)", 0x02, 3, 3, 1, 3), # (4-4-4)
    #     ]

    #     for i in range(5):  # Perform 5 random QPI write tests
    #         for mode_name, cmd, cmd_mode, addr_mode, addr_len, data_mode in qpi_write_modes:
    #             try:
    #                 test_data_len = random.randint(64, 256)  # Random length between 64 and 256 bytes
    #                 expected_words = math.ceil(test_data_len / 4)

    #                 dut._log.info(f" -> Executing {mode_name} with {test_data_len} Bytes...")

    #                 await Timer(10, unit="us")
    #                 await RisingEdge(dut.clk_i)

    #                 # Send Write Enable (WREN) before the Page Program
    #                 dut._log.info("    Sending Write Enable (0x06) command...")
    #                 await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0x06, qpi=True)
    #                 await Timer(500, unit="ns")
    #                 await RisingEdge(dut.clk_i)

    #                 # Start the Write Transaction
    #                 await qspi_write_transaction(
    #                     dut=dut,
    #                     cs_mask=mx25l_mask,
    #                     cmd=cmd,
    #                     cmd_mode=cmd_mode,
    #                     addr=current_addr,
    #                     addr_mode=addr_mode,
    #                     addr_len=addr_len,
    #                     data_mode=data_mode,
    #                     data_len=test_data_len,
    #                     data_words=payload_pool,
    #                     ddr=False
    #                 )

    #                 # Wait for BUSY bit to clear (10ms timeout for PP)
    #                 dut._log.info("    Waiting for BUSY bit to clear in Status Register...")
    #                 await qspi_poll_wip_bit(dut, cs_mask=mx25l_mask, status_cmd=0x05, poll_interval_ns=100000, timeout_s=5e-3)
    #                 dut._log.info("    BUSY bit cleared. Write operation completed successfully.")

    #                 # Wait some time before reading back
    #                 await Timer(10, unit="us")
    #                 await RisingEdge(dut.clk_i)

    #                 # VERIFICATION: Read the data back
    #                 dut._log.info(f"    Verifying Written Data at 0x{current_addr:08X}...")
    #                 readback_list = await qspi_read_transaction(
    #                     dut=dut, 
    #                     cs_mask=mx25l_mask, 
    #                     cmd=0x6B, # Quad IO Read
    #                     cmd_mode=3, addr=current_addr, addr_mode=3, addr_len=1, dummy_len=6, data_mode=3, 
    #                     data_len=test_data_len, ddr=False
    #                 )

    #                 dummy_dict = {current_addr: payload_pool}
    #                 expected_list = get_expected_words(
    #                     golden_dict=dummy_dict, 
    #                     target_addr=current_addr, 
    #                     num_words=expected_words,
    #                     total_bytes=test_data_len, 
    #                     endian="big"
    #                 )

    #                 # Compare what we told it to write against what we read back
    #                 for i in range(expected_words):
    #                     dut._log.info(f"    [VERIFY] Word {i}: Expected 0x{expected_list[i]:08X}, Got 0x{readback_list[i]:08X}")
    #                     if readback_list[i] != expected_list[i]:
    #                         raise ValueError(f"WRITE CORRUPTION at Word {i}! Wrote 0x{payload_pool[i]:08X}, Read 0x{readback_list[i]:08X}")

    #                 dut._log.info("    Write and Readback perfectly MATCH!")
    #                 scoreboard.record("MX25L Random Write 4-Byte Addressing", mode_name, passed=True)

    #             except Exception as e:
    #                 dut._log.error(f"    [!] FAILED: {str(e)}")
    #                 scoreboard.record("MX25L Random Write 4-Byte Addressing", mode_name, passed=False, error_msg=str(e))

    #     # Exit QPI Mode by sending the QPI Disable command (0xF5)
    #     dut._log.info("Disabling QPI Mode for MX25L...")
    #     await qspi_write_command(dut, cs_mask=mx25l_mask, cmd=0xF5, qpi=True)
    #     await Timer(500, unit="ns")
    #     await RisingEdge(dut.clk_i)
    #     dut._log.info("QPI Mode disabled. Proceeding to next test...")
        

    # FINAL VERDICT
    scoreboard.report(dut._log)


