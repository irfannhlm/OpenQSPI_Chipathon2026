import os
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer, Event
from cocotb.queue import Queue

# ==============================================================================
# Helper Coroutines (Cycle-Accurate Bit-Banging)
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

async def setup_dut(dut):
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

    return rx_queue


async def csr_read(dut, rx_queue, addr, verbose=True):
    """Reads a value from a CSR address through UART."""

    dut._log.info(f"Reading from CSR address 0x{addr:02X} via UART...")

    addr_byte = addr & 0x7F  # Ensure R/W bit is 0 for read
    await uart_send_byte(dut, addr_byte)  # Send address byte

    # Wait for ACK (0x55) from DUT
    ack_byte = await rx_queue.get()
    if ack_byte == 0x55:
        dut._log.info(f"CSR Read from 0x{addr:02X} successful, ACK received.")
    else:
        dut._log.error(f"CSR Read from 0x{addr:02X} failed, expected ACK 0x55 but received 0x{ack_byte:02X}.")
        return None  # Return None to indicate failure
    
    # Wait for the response (4 bytes of data)
    data_bytes = []
    for _ in range(4):
        if verbose:
            dut._log.info(f"Waiting for data byte {_+1}/4 from CSR address 0x{addr:02X}...")
        data_byte = await rx_queue.get()
        if verbose:
            dut._log.info(f"Received data byte: 0x{data_byte:02X}")
        data_bytes.append(data_byte)

    # Combine the received bytes into a single 32-bit value (big endian)
    data_val = 0
    for i in range(4):
        data_val |= (data_bytes[i] << (8 * (3 - i)))

    dut._log.info(f"Received data 0x{data_val:08X} from CSR address 0x{addr:02X}.")

    # Wait for a short period 
    baud_div = get_baud_div(dut)
    for _ in range(int(baud_div * 1.5)):
        await RisingEdge(dut.clk_i)

    return data_val


async def csr_write(dut, rx_queue, addr, data, verbose=True):
    """Writes a value to a CSR address through UART."""

    dut._log.info(f"Writing 0x{data:08X} to CSR address 0x{addr:02X} via UART...")

    addr_byte = (addr & 0x7F) | 0x80  # Set R/W bit to 1 for write
    await uart_send_byte(dut, addr_byte)  # Send address byte

    for i in range(4):  # Send 4 bytes of data (32 bits, big endian)
        byte_to_send = (data >> (8 * (3 - i))) & 0xFF
        if verbose:
            dut._log.info(f"Sending data byte {i+1}/4: 0x{byte_to_send:02X}")
        await uart_send_byte(dut, byte_to_send)

    ack_byte = await rx_queue.get()

    if ack_byte == 0x55:
        dut._log.info(f"CSR Write to 0x{addr:02X} successful, ACK received.")
    else:
        dut._log.error(f"CSR Write to 0x{addr:02X} failed, expected ACK 0x55 but received 0x{ack_byte:02X}.")

    # Wait for a short period 
    baud_div = get_baud_div(dut)
    for _ in range(int(baud_div * 1.5)):
        await RisingEdge(dut.clk_i)


@cocotb.test()
async def test_csr_read_write(dut):
    """Test reading and writing to CSRs via UART."""
    rx_queue = await setup_dut(dut)

    # Example CSR address and data
    test_addr = 0x10
    test_data = 0xDEADBEEF

    # Write to CSR
    await csr_write(dut, rx_queue, test_addr, test_data)

    # Read back from CSR
    read_data = await csr_read(dut, rx_queue, test_addr)

    # Verify the read data matches the written data
    assert read_data == test_data, f"CSR Read/Write Mismatch: wrote 0x{test_data:08X}, read 0x{read_data:08X}"