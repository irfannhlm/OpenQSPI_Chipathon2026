import os

# A large, readable block of text to stress-test the FIFO (700+ bytes)
LOREM_IPSUM = (
    "The QSPI Master Controller is currently executing a massive continuous read operation. "
    "This text is designed to completely overflow the internal RX FIFO if the APB bus does "
    "not pop the data fast enough. By reading hundreds of bytes, we can verify that the "
    "hardware bidirectional clock-pausing mechanism works flawlessly. When the FIFO hits "
    "its maximum capacity, the state machine must halt the SCLK toggling immediately, "
    "holding the CSn line low, and patiently wait for the CPU to drain the buffer. "
    "Once the buffer has space, the SCLK should resume perfectly without any phantom edges. "
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor "
    "incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud "
    "exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute "
    "irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla "
    "pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui "
    "officia deserunt mollit anim id est laborum. END_OF_TRANSMISSION."
)

def generate_hex_file(filename, header_comment, text_payload, start_address=0):
    """Converts a readable string into a $readmemh compatible hex file."""
    
    # Convert the string to raw bytes (ASCII/UTF-8)
    byte_data = text_payload.encode('utf-8')
    
    with open(filename, 'w') as f:
        f.write(f"// {header_comment}\n")
        f.write("// Unlisted locations remain FF (Flash Erased State)\n\n")
        
        # Write the starting address
        f.write(f"@{start_address:06X}\n")
        
        # Write the data, 16 bytes per line for easy reading in GTKWave/Hex editors
        for i in range(0, len(byte_data), 16):
            chunk = byte_data[i:i+16]
            hex_strings = [f"{b:02X}" for b in chunk]
            f.write(" ".join(hex_strings) + "\n")
            
    print(f"Generated {filename} ({len(byte_data)} bytes)")

# Generate the files for your specific flash models
if __name__ == "__main__":
    print("Generating Flash Memory initialization files...")
    
    generate_hex_file(
        filename="s25fl128s.mem",
        header_comment="Initial flash contents for Infineon S25FL128S",
        text_payload=LOREM_IPSUM
    )
    
    generate_hex_file(
        filename="MX25L51245G.TXT",
        header_comment="Main preload for Macronix MX25L51245G",
        text_payload=LOREM_IPSUM
    )
    
    generate_hex_file(
        filename="MEM.TXT",
        header_comment="Main flash preload for Winbond W25Q",
        text_payload=LOREM_IPSUM
    )
    
    print("Done! You can now run your Cocotb simulation.")