import os
import random
import logging
from pathlib import Path
from tabnanny import verbose

import cocotb
from cocotb.clock import Clock
from cocotb.queue import Queue
from cocotb.triggers import Timer, Edge, RisingEdge, FallingEdge, ClockCycles
from cocotb_tools.runner import get_runner


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

CLOCK_FREQ = 50_000_000  # 50 MHz
UART_BAUD = 2_000_000  # 921600 bps
BAUD_DIV = int(CLOCK_FREQ // UART_BAUD)  # Clock cycles per UART bit


async def uart_send_byte(dut, byte_val, baud_div=BAUD_DIV):
    """Simulates a PC sending a byte to the DUT's RX pin."""

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

async def uart_receive_byte(dut, baud_div=BAUD_DIV):
    """Simulates a PC receiving a byte from the DUT's TX pin (GLS Safe)."""

    # Wait for the Start bit (FallingEdge triggers on 1->0, but also 1->X)
    await FallingEdge(dut.uart_tx_o)
    
    # Wait half a baud cycle to sample perfectly in the middle of the start bit
    for _ in range(baud_div // 2): 
        await RisingEdge(dut.clk_i)
        
    start_bit = str(dut.uart_tx_o.value)
    if start_bit != '0':
        cocotb.log.warning(f"UART RX Warning: Start Bit is '{start_bit}' (Expected '0')")
    
    byte_val = 0
    # Sample 8 Data bits
    for i in range(8):
        for _ in range(baud_div): 
            await RisingEdge(dut.clk_i)
            
        bit_str = str(dut.uart_tx_o.value)
        
        if bit_str == '1':
            byte_val |= (1 << i)
        elif bit_str != '0':
            # If it is 'X' or 'Z', we log a warning and default the bit to 0 to prevent a crash
            cocotb.log.warning(f"UART RX Warning: Unknown bit '{bit_str}' at index {i}. Defaulting to 0.")
            
    # Check for Stop bit
    for _ in range(baud_div): 
        await RisingEdge(dut.clk_i)
        
    stop_bit = str(dut.uart_tx_o.value)
    if stop_bit != '1':
        cocotb.log.warning(f"UART RX Warning: Stop Bit is '{stop_bit}' (Expected '1')")

    return byte_val

async def uart_rx_monitor(dut, rx_queue):
    """
    Runs in parallel forever. Continuously listens to the TX line 
    and pushes received bytes into a thread-safe Queue.
    """
    cocotb.log.info("Starting background UART RX monitor...")
    try: 
        while True:
            byte_val = await uart_receive_byte(dut) 
            await rx_queue.put(byte_val)
    except Exception as e:
        # Catch any unexpected errors cleanly so the simulator doesn't hard-crash
        cocotb.log.error(f"UART RX FATAL ERROR: {e}")
        await rx_queue.put(None)
        
async def csr_read(dut, rx_queue, addr, baud_div=BAUD_DIV, verbose=True):
    """Reads a value from a CSR address through UART."""
    if verbose:
        cocotb.log.info(f"Reading from CSR address 0x{addr:02X} via UART...")

    addr_byte = addr & 0x7F  # Ensure R/W bit is 0 for read
    await uart_send_byte(dut, addr_byte)  # Send address byte

    # Wait for ACK (0x55) from DUT
    ack_byte = await rx_queue.get()
    if ack_byte == 0x55:
        if verbose:
            cocotb.log.info(f"CSR Read from 0x{addr:02X} successful, ACK received.")
    else:
        cocotb.log.error(f"CSR Read from 0x{addr:02X} failed, expected ACK 0x55 but received 0x{ack_byte:02X}.")
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
        cocotb.log.info(f"Received data 0x{data_val:08X} from CSR address 0x{addr:02X}.")

    # Wait for a short period 
    for _ in range(int(baud_div * 1.5)):
        await RisingEdge(dut.clk_i)

    return data_val

async def csr_write(dut, rx_queue, addr, data, baud_div=BAUD_DIV, verbose=True):
    """Writes a value to a CSR address through UART."""
    if verbose:
        cocotb.log.info(f"Writing 0x{data:08X} to CSR address 0x{addr:02X} via UART...")

    addr_byte = (addr & 0x7F) | 0x80  # Set R/W bit to 1 for write
    await uart_send_byte(dut, addr_byte)  # Send address byte

    for i in range(4):  # Send 4 bytes of data (32 bits, big endian)
        byte_to_send = (data >> (8 * (3 - i))) & 0xFF
        await uart_send_byte(dut, byte_to_send)

    ack_byte = await rx_queue.get()

    if ack_byte == 0x55:
        if verbose:
            cocotb.log.info(f"CSR Write to 0x{addr:02X} successful, ACK received.")
    else:
        cocotb.log.error(f"CSR Write to 0x{addr:02X} failed, expected ACK 0x55 but received 0x{ack_byte:02X}.")

    # Wait for a short period 
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
    cocotb.log.info("Waiting for QSPI core to become idle...")
    for _ in range(timeout_cycles):
        ctrl = await csr_read(dut, rx_queue, QSPI_CTRL, verbose=False)
        if (ctrl & 0x08) == 0:  # Check if BUSY is 0
            cocotb.log.info("QSPI core is idle.")
            return True
        await RisingEdge(dut.clk_i)
    
    cocotb.log.error("QSPI core wait timeout!")
    return False

async def flash_poll_busy(dut, rx_queue, prescaler=0, interval_us=100, timeout_us=2000):
    """Polls the flash's status register until the BUSY bit clears."""
    cocotb.log.info("Polling flash status register for BUSY bit...")
    # Setup CFG0 for Read Status Register (0x05)
    cfg0 = build_cfg0(cmd_mode=1, data_mode=1, data_dir=0, prescaler=prescaler)
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
                cocotb.log.info("Flash is ready (BUSY bit cleared).")
                await csr_write(dut, rx_queue, QSPI_CTRL, 0x02)  # Abort transaction
                await csr_write(dut, rx_queue, QSPI_CTRL, 0x200)  # Flush FIFO

                return True
        
        await Timer(interval_us, unit="us")
        await RisingEdge(dut.clk_i)
    
    cocotb.log.error("Flash BUSY polling timeout!")
    return False