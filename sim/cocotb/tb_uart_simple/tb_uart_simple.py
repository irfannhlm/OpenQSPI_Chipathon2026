import os
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer, Event

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
        baud_rate = int(os.environ.get("TEST_BAUD", "115200"))
        return clock_freq // baud_rate
    

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


async def setup_dut(dut):
    """Initialize standard signals and start the clock."""

    cocotb.start_soon(Clock(dut.clk_i, clock_period_ns, unit="ns").start())
    
    # Set default inputs
    dut.rst_ni.value = 0
    dut.tx_start_i.value = 0
    dut.tx_data_i.value = 0
    dut.uart_rx_i.value = 1 # Idle high
    
    # Hold reset for a few cycles
    for _ in range(5): 
        await RisingEdge(dut.clk_i)
        
    dut.rst_ni.value = 1
    await RisingEdge(dut.clk_i)

async def generic_pulse_monitor(clk, signal, event):
    """
    A generic background monitor that never misses a clock cycle.
    It triggers the provided Python Event whenever the target signal goes HIGH.
    """
    while True:
        await RisingEdge(clk)
        if signal.value == 1:
            event.set()


# ==============================================================================
# Cocotb Tests
# ==============================================================================

@cocotb.test()
async def test_uart_tx(dut):
    """Test the module transmitting a byte (DUT -> PC)"""
    await setup_dut(dut)
    
    tx_event = Event()
    cocotb.start_soon(generic_pulse_monitor(dut.clk_i, dut.tx_done_o, tx_event))    

    test_byte = 0xA5 # 1010_0101

    # Load data and pulse start
    dut.tx_data_i.value = test_byte
    dut.tx_start_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.tx_start_i.value = 0
    
    # Await the receiver helper function
    dut._log.info(f"Receiving {hex(test_byte)} from UART module...")
    received_byte = await uart_receive_byte(dut)
    
    # Wait for the DUT to assert tx_done_o
    await tx_event.wait()
    tx_event.clear()
    
    # Verify
    assert received_byte == test_byte, f"TX mismatch: expected {hex(test_byte)}, got {hex(received_byte)}"
    dut._log.info(f"Successfully transmitted {hex(received_byte)}")


@cocotb.test()
async def test_uart_rx(dut):
    """Test the module receiving a byte (PC -> DUT)"""
    await setup_dut(dut)

    rx_event = Event()
    cocotb.start_soon(generic_pulse_monitor(dut.clk_i, dut.rx_valid_o, rx_event))
    
    test_byte = 0x3C # 0011_1100
    
    # Use the helper to bit-bang the RX pin
    dut._log.info(f"Sending {hex(test_byte)} to UART module...")
    await uart_send_byte(dut, test_byte)
    
    # Wait for the DUT to assert rx_valid_o
    await rx_event.wait()
    rx_event.clear()  

    # Verify
    assert dut.rx_error_o.value == 0, "DUT flagged a framing error!"
    assert dut.rx_data_o.value == test_byte, f"RX mismatch: expected {hex(test_byte)}, got {hex(dut.rx_data_o.value)}"
    dut._log.info(f"Successfully received {hex(dut.rx_data_o.value)}")


@cocotb.test()
async def test_uart_rx_error(dut):
    """Test the module catching a framing error (invalid start bit)"""
    await setup_dut(dut)
    baud_div = get_baud_div(dut)

    # Create a glitch: Pull RX low to trigger START state, but pull it back high immediately
    dut.uart_rx_i.value = 0
    for _ in range(baud_div // 4): 
        await RisingEdge(dut.clk_i)
    
    dut.uart_rx_i.value = 1 # Glitch goes away before the mid-point sample
    
    # Wait to see if error flag is raised
    for _ in range(baud_div):
        await RisingEdge(dut.clk_i)
        if dut.rx_error_o.value == 1:
            dut._log.info("Successfully caught a glitch/framing error!")
            return
            
    assert False, "Module failed to assert rx_error_o on an invalid start bit."

@cocotb.test()
async def test_uart_burst_stream(dut):
    """Test sending a burst of bytes to the DUT (PC -> DUT)"""
    await setup_dut(dut)
    
    # 1. Create the event and spawn the monitor ONCE
    rx_event = Event()
    cocotb.start_soon(generic_pulse_monitor(dut.clk_i, dut.rx_valid_o, rx_event))
    
    # 2. Send a burst of 5 bytes
    for i in range(5):
        # Send the byte
        await uart_send_byte(dut, 0xA0 + i)
        
        # Safely wait for the hardware to process it and pulse the valid line
        await rx_event.wait()
        rx_event.clear() 
        
        # Read the data
        received = int(dut.rx_data_o.value)
        dut._log.info(f"Byte {i} received: {hex(received)}")

@cocotb.test()
async def test_uart_echo_loopback(dut):
    """Test Turnaround: PC -> DUT -> PC (Validates Half-Duplex FSM Switching)"""
    await setup_dut(dut)
    
    # 1. Setup events and start our permanent background monitors
    rx_event = Event()
    tx_event = Event()
    cocotb.start_soon(generic_pulse_monitor(dut.clk_i, dut.rx_valid_o, rx_event))
    cocotb.start_soon(generic_pulse_monitor(dut.clk_i, dut.tx_done_o, tx_event))

    # The byte we want to bounce off the chip
    test_payload = 0x5A 
    dut._log.info(f"--- Starting Echo Loopback with Payload: {hex(test_payload)} ---")

    # ==========================================
    # PHASE 1: PC Transmits to DUT
    # ==========================================
    dut._log.info("Phase 1: PC sending data to DUT...")
    await uart_send_byte(dut, test_payload)
    
    # Wait for the background monitor to catch the RX pulse
    await rx_event.wait()
    rx_event.clear()
    
    # Read what the Verilog actually captured
    received_in_dut = int(dut.rx_data_o.value)
    dut._log.info(f"   -> DUT successfully received: {hex(received_in_dut)}")
    assert received_in_dut == test_payload, "DUT failed to receive the correct byte!"

    # ==========================================
    # PHASE 2: DUT Turns Around and Transmits to PC
    # ==========================================
    dut._log.info("Phase 2: DUT echoing data back to PC...")
    
    # Feed the received data directly into the TX register
    dut.tx_data_i.value = received_in_dut
    dut.tx_start_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.tx_start_i.value = 0
    
    # Use our bit-banger to listen to the DUT's TX pin
    echoed_byte = await uart_receive_byte(dut)
    
    # Wait for the background monitor to catch the TX done pulse
    await tx_event.wait()
    tx_event.clear()

    dut._log.info(f"   -> PC successfully received echo: {hex(echoed_byte)}")
    assert echoed_byte == test_payload, "Echoed byte did not match original payload!"
    
    dut._log.info("--- Turnaround Echo Loopback PASSED! ---")