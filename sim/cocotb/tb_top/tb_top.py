import os
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer, Event
from cocotb.queue import Queue

# ==============================================================================
# QSPI Register Map Offsets
# ==============================================================================
QSPI_CTRL    = 0x00
QSPI_CFG0    = 0x04
QSPI_DLEN    = 0x08
QSPI_CMD     = 0x0C
QSPI_ADDR    = 0x10
QSPI_DR      = 0x14
QSPI_BCNT    = 0x18
QSPI_TIMEOUT = 0x1C

# ==============================================================================
# Helper Coroutines
# ==============================================================================

clock_period_ns = 1e9 // int(os.environ.get("CLOCK_FREQ", "50000000"))  # Default to 50 MHz if not set

def get_baud_div(dut):
    """Safely calculates the baud divisor for both RTL and GLS modes."""
    try:
        # Try to read the parameters directly (Works in normal RTL)
        clock_freq = dut.CLOCK_FREQ.value
        baud_rate = dut.BAUD_RATE.value
        return int(clock_freq) // int(baud_rate)
    except AttributeError:
        # If parameters are missing (Gate-Level Mode), use the Makefile variables!
        clock_freq = int(os.environ.get("CLOCK_FREQ", "50000000"))
        baud_rate = int(os.environ.get("TEST_BAUD", "921600"))
        return clock_freq // baud_rate

async def generic_pulse_monitor(clk, signal, event):
    """
    A generic background monitor that never misses a clock cycle.
    It triggers the provided Python Event whenever the target signal goes HIGH.
    """
    while True:
        await RisingEdge(clk)
        if signal.value == 1:
            event.set()
    
async def uart_send_byte(dut, byte_val):
    """Simulates a PC sending a byte to the DUT's RX pin."""
    baud_div = get_baud_div(dut)
    
    # Send Start bit (0)
    dut.uart_rx_i.value = 0
    for _ in range(baud_div): 
        await RisingEdge(dut.clk_i)
    
    # Send 8 Data bits (LSB first)
    for i in range(8):
        dut.uart_rx_i.value = (byte_val >> i) & 1
        for _ in range(baud_div): 
            await RisingEdge(dut.clk_i)
            
    # Send Stop bit (1)
    dut.uart_rx_i.value = 1
    for _ in range(baud_div): 
        await RisingEdge(dut.clk_i)

async def uart_receive_byte(dut):
    """Simulates a PC receiving a byte from the DUT's TX pin."""
    baud_div = get_baud_div(dut)

    # Wait for the Start bit (falling edge)
    await FallingEdge(dut.uart_tx_o)
    
    # Wait half a baud cycle to sample perfectly in the middle of the start bit
    for _ in range(baud_div // 2): 
        await RisingEdge(dut.clk_i)
    assert dut.uart_tx_o.value == 0, "Expected Start Bit to be 0!"
    
    byte_val = 0
    # Sample 8 Data bits
    for i in range(8):
        for _ in range(baud_div): 
            await RisingEdge(dut.clk_i)
        bit = int(dut.uart_tx_o.value)
        byte_val |= (bit << i)
        
    # Check for Stop bit
    for _ in range(baud_div): 
        await RisingEdge(dut.clk_i)
    assert dut.uart_tx_o.value == 1, "Expected Stop Bit to be 1!"

    return byte_val

async def uart_rx_monitor(dut, rx_queue):
    """
    Runs in parallel forever. Continuously listens to the TX line 
    and pushes received bytes into a thread-safe Queue.
    """
    dut._log.info("Starting background UART RX monitor...")
    try: 
        while True:
            byte_val = await uart_receive_byte(dut) 
            await rx_queue.put(byte_val)
    except AssertionError as e:
        dut._log.error(f"UART RX CRASHED: Assertion Failed! {e}")
        await rx_queue.put(None) # Push a dummy value to unblock the main thread
    except Exception as e:
        dut._log.error(f"UART RX CRASHED: {e}")
        await rx_queue.put(None)

async def setup_dut(dut, flash_setup_time_us=3000):
    """Initialize standard signals and start the clock."""
    cocotb.start_soon(Clock(dut.clk_i, clock_period_ns, unit="ns").start())

    # Set default inputs
    dut.rst_ni.value = 0
    dut.uart_rx_i.value = 1 # Idle high

    for _ in range(10):  # Hold reset for 10 clock cycles
        await RisingEdge(dut.clk_i)
    
    dut.rst_ni.value = 1
    await RisingEdge(dut.clk_i)

    rx_queue = Queue()
    cocotb.start_soon(uart_rx_monitor(dut, rx_queue))

    # Wait for flash setup time
    cocotb.log.info(f"Waiting for flash setup time: {flash_setup_time_us} us...")
    await Timer(flash_setup_time_us, unit="us")
    await RisingEdge(dut.clk_i)

    return rx_queue

async def csr_read(dut, rx_queue, addr, verbose=True):
    """Reads a value from a CSR address through UART."""
    if verbose:
        dut._log.info(f"Reading from CSR address 0x{addr:02X} via UART...")

    addr_byte = addr & 0x7F  # Ensure R/W bit is 0 for read
    await uart_send_byte(dut, addr_byte)  # Send address byte

    # Wait for ACK (0x55) from DUT
    ack_byte = await rx_queue.get()
    if ack_byte == 0x55:
        if verbose:
            dut._log.info(f"CSR Read from 0x{addr:02X} successful, ACK received.")
    else:
        dut._log.error(f"CSR Read from 0x{addr:02X} failed, expected ACK 0x55 but received 0x{ack_byte:02X}.")
        return None  # Return None to indicate failure
    
    # Wait for the response (4 bytes of data)
    data_bytes = []
    for _ in range(4):
        data_byte = await rx_queue.get()
        data_bytes.append(data_byte)

    # Combine the received bytes into a single 32-bit value (big endian)
    data_val = 0
    for i in range(4):
        data_val |= (data_bytes[i] << (8 * (3 - i)))

    if verbose:
        dut._log.info(f"Received data 0x{data_val:08X} from CSR address 0x{addr:02X}.")

    # Wait for a short period 
    baud_div = get_baud_div(dut)
    for _ in range(int(baud_div * 1.5)):
        await RisingEdge(dut.clk_i)

    return data_val

async def csr_write(dut, rx_queue, addr, data, verbose=True):
    """Writes a value to a CSR address through UART."""
    if verbose:
        dut._log.info(f"Writing 0x{data:08X} to CSR address 0x{addr:02X} via UART...")

    addr_byte = (addr & 0x7F) | 0x80  # Set R/W bit to 1 for write
    await uart_send_byte(dut, addr_byte)  # Send address byte

    for i in range(4):  # Send 4 bytes of data (32 bits, big endian)
        byte_to_send = (data >> (8 * (3 - i))) & 0xFF
        await uart_send_byte(dut, byte_to_send)

    ack_byte = await rx_queue.get()

    if ack_byte == 0x55:
        if verbose:
            dut._log.info(f"CSR Write to 0x{addr:02X} successful, ACK received.")
    else:
        dut._log.error(f"CSR Write to 0x{addr:02X} failed, expected ACK 0x55 but received 0x{ack_byte:02X}.")

    # Wait for a short period 
    baud_div = get_baud_div(dut)
    for _ in range(int(baud_div * 1.5)):
        await RisingEdge(dut.clk_i)

# ==============================================================================
# QSPI Helper Functions
# ==============================================================================
def build_cfg0(prescaler=0, addr_len=0, dummy_len=0, cmd_mode=0, addr_mode=0, data_mode=0, sck_mode=0, data_dir=0, crm=0, ddr=0, endian=0, cs_num=0):
    """Packs fields into QSPI_CFG0 format."""
    cfg = 0
    cfg |= (prescaler & 0xFF) << 0
    cfg |= (addr_len & 0x1) << 8
    cfg |= (dummy_len & 0x3F) << 9
    cfg |= (cmd_mode & 0x3) << 15
    cfg |= (addr_mode & 0x3) << 17
    cfg |= (data_mode & 0x3) << 19
    cfg |= (sck_mode & 0x1) << 21
    cfg |= (data_dir & 0x1) << 22
    cfg |= (crm & 0x1) << 23
    cfg |= (ddr & 0x1) << 24
    cfg |= (endian & 0x1) << 25
    cfg |= ((1<<cs_num) & 0x3) << 26

    return cfg

async def qspi_wait_idle(dut, rx_queue, timeout_cycles=1000):
    """Polls QSPI_CTRL until the BUSY bit [3] clears."""
    dut._log.info("Waiting for QSPI core to become idle...")
    for _ in range(timeout_cycles):
        ctrl = await csr_read(dut, rx_queue, QSPI_CTRL, verbose=False)
        if (ctrl & 0x08) == 0:  # Check if BUSY is 0
            dut._log.info("QSPI core is idle.")
            return True
        await RisingEdge(dut.clk_i)
    
    dut._log.error("QSPI core wait timeout!")
    return False

async def flash_poll_busy(dut, rx_queue, interval_us=100, timeout_us=2000):
    """Polls the flash's status register until the BUSY bit clears."""
    dut._log.info("Polling flash status register for BUSY bit...")
    # Setup CFG0 for Read Status Register (0x05)
    cfg0 = build_cfg0(cmd_mode=1, data_mode=1, data_dir=0)
    await csr_write(dut, rx_queue, QSPI_CFG0, cfg0)
    await csr_write(dut, rx_queue, QSPI_CMD, 0x05)  # Read Status Register
    await csr_write(dut, rx_queue, QSPI_DLEN, 0xFFFF_FFFF) # Do unlimited read
    await csr_write(dut, rx_queue, QSPI_CTRL, 0x01)  # Start transaction

    timeout_cycles = timeout_us // interval_us
    cleared = False
    for _ in range(timeout_cycles):
        for _ in range(16):  # Fully drain the RX FIFO to get the latest status
            status = await csr_read(dut, rx_queue, QSPI_DR)
            if (status & 0x01) == 0:  # Check if BUSY bit is cleared
                dut._log.info("Flash is ready (BUSY bit cleared).")
                await csr_write(dut, rx_queue, QSPI_CTRL, 0x02)  # Abort transaction
                await csr_write(dut, rx_queue, QSPI_CTRL, 0x200)  # Flush FIFO

                return True
        
        await Timer(interval_us, unit="us")
        await RisingEdge(dut.clk_i)
    
    dut._log.error("Flash BUSY polling timeout!")
    return False

# ==============================================================================
# Test Cases
# ==============================================================================

@cocotb.test()
async def test_csr_read_write(dut):
    """Sanity test reading and writing to CSRs via UART."""
    rx_queue = await setup_dut(dut, flash_setup_time_us=10)

    # Example CSR address and data
    test_addr = QSPI_TIMEOUT
    test_data = 0xDEADBEEF

    await csr_write(dut, rx_queue, test_addr, test_data)
    read_data = await csr_read(dut, rx_queue, test_addr)
    assert read_data == test_data, f"CSR Read/Write Mismatch: wrote 0x{test_data:08X}, read 0x{read_data:08X}"


@cocotb.test()
async def test_qspi_rdid(dut):
    """Test standard QSPI Read ID (RDID 0x9F) sequence."""
    rx_queue = await setup_dut(dut)
    dut._log.info("Starting SPI RDID (0x9F) Test...")

    for i in range(2):  # Test both flash chips (CS0 and CS1)
        dut._log.info(f"Testing RDID for the flash chip (CS{i})...")

        # Setup CFG0: Single CMD, Single Data, Direction=Read, No Address, No Dummies
        cfg0 = build_cfg0(cmd_mode=1, data_mode=1, data_dir=0, cs_num=i)
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
        
        dut._log.info(f"RDID Raw Data Received: 0x{rdid_data:08X}")


@cocotb.test()
async def test_qspi_program_read(dut):
    """Test standard Page Program (0x02) followed by Normal Read (0x03)."""
    rx_queue = await setup_dut(dut)
    dut._log.info("Starting SPI Program and Read Test...")

    target_addr = 0x001000  # Example 24-bit flash address
    target_data = 0xCAFEBABE
    
    # --- PHASE 1: Write Enable (0x06) ---
    dut._log.info("--- Phase 1: Sending Write Enable (0x06) ---")
    cfg0_we = build_cfg0(cmd_mode=1) # Command only
    await csr_write(dut, rx_queue, QSPI_CFG0, cfg0_we)
    await csr_write(dut, rx_queue, QSPI_CMD, 0x06)
    await csr_write(dut, rx_queue, QSPI_DLEN, 0)
    
    await csr_write(dut, rx_queue, QSPI_CTRL, 0x01)
    await qspi_wait_idle(dut, rx_queue)

    # --- PHASE 2: Page Program (0x02) ---
    dut._log.info(f"--- Phase 2: Page Program (0x02) to Addr 0x{target_addr:06X} ---")
    # Single CMD, Single ADDR, Single DATA, Write direction (data_dir=1), 3-byte addr (addr_len=0)
    cfg0_prog = build_cfg0(cmd_mode=1, addr_mode=1, data_mode=1, data_dir=1, addr_len=0)
    await csr_write(dut, rx_queue, QSPI_CFG0, cfg0_prog)
    await csr_write(dut, rx_queue, QSPI_CMD, 0x02)
    await csr_write(dut, rx_queue, QSPI_ADDR, target_addr)
    await csr_write(dut, rx_queue, QSPI_DLEN, 4) # Writing 4 bytes
    
    # Push data into TX FIFO
    await csr_write(dut, rx_queue, QSPI_DR, target_data)
    
    await csr_write(dut, rx_queue, QSPI_CTRL, 0x01)
    await qspi_wait_idle(dut, rx_queue)

    # Poll flash until it's ready
    await flash_poll_busy(dut, rx_queue)

    # --- PHASE 3: Normal Read (0x03) ---
    dut._log.info(f"--- Phase 3: Normal Read (0x03) from Addr 0x{target_addr:06X} ---")
    # Single CMD, Single ADDR, Single DATA, Read direction (data_dir=0)
    cfg0_read = build_cfg0(cmd_mode=1, addr_mode=1, data_mode=1, data_dir=0, addr_len=0)
    await csr_write(dut, rx_queue, QSPI_CFG0, cfg0_read)
    await csr_write(dut, rx_queue, QSPI_CMD, 0x03)
    await csr_write(dut, rx_queue, QSPI_ADDR, target_addr)
    await csr_write(dut, rx_queue, QSPI_DLEN, 4)
    
    await csr_write(dut, rx_queue, QSPI_CTRL, 0x01)
    await qspi_wait_idle(dut, rx_queue)

    # Pop data from RX FIFO
    read_data = await csr_read(dut, rx_queue, QSPI_DR)
    dut._log.info(f"Read Data Received: 0x{read_data:08X}")
    
    assert read_data != 0xFFFFFFFF, "Read data is all 1's, indicating a failed read or unprogrammed flash."
    assert read_data == target_data, f"Data Mismatch: wrote 0x{target_data:08X}, read 0x{read_data:08X}"