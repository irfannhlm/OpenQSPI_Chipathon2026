import os
import sys
import argparse

def read_input_file(filepath):
    """Reads a .txt or .bin file and returns its content as raw bytes."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"❌ Error: Could not find '{filepath}'")
    
    # Check the extension to determine how to read the file
    _, ext = os.path.splitext(filepath)
    
    if ext.lower() == '.bin':
        print(f"📂 Detected Binary File. Reading raw bytes...")
        with open(filepath, 'rb') as f:
            return f.read()
    else:
        print(f"📄 Detected Text File. Encoding to UTF-8 bytes...")
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read().encode('utf-8')

def generate_hex_file(filename, header_comment, payload_bytes, start_address=0):
    """Converts raw bytes into a $readmemh compatible hex file."""
    with open(filename, 'w') as f:
        f.write(f"// {header_comment}\n")
        f.write("// Unlisted locations remain FF (Flash Erased State)\n\n")
        
        # Write the starting address
        f.write(f"@{start_address:06X}\n")
        
        # Write the data, 16 bytes per line for easy reading in GTKWave/Hex editors
        for i in range(0, len(payload_bytes), 16):
            chunk = payload_bytes[i:i+16]
            hex_strings = [f"{b:02X}" for b in chunk]
            f.write(" ".join(hex_strings) + "\n")
            
    print(f"  ✅ Generated {filename} ({len(payload_bytes)} bytes)")

if __name__ == "__main__":
    # Setup command line argument parsing
    parser = argparse.ArgumentParser(description="Generate QSPI Flash Memory .mem/.TXT files from an input file.")
    parser.add_argument("input_file", help="Path to the input .txt or .bin payload file.")
    args = parser.parse_args()

    try:
        # 1. Read the raw bytes from the provided file
        payload_bytes = read_input_file(args.input_file)
        
        # 2. Generate the files for your specific flash models
        print("\n Generating Flash Memory initialization files...")
        
        generate_hex_file(
            filename="s25fl128s.mem",
            header_comment=f"Initial flash contents for Infineon S25FL128S (Source: {args.input_file})",
            payload_bytes=payload_bytes
        )
        
        generate_hex_file(
            filename="MX25L51245G.TXT",
            header_comment=f"Main preload for Macronix MX25L51245G (Source: {args.input_file})",
            payload_bytes=payload_bytes
        )
        
        generate_hex_file(
            filename="MEM.TXT",
            header_comment=f"Main flash preload for Winbond W25Q (Source: {args.input_file})",
            payload_bytes=payload_bytes
        )
        
        print("\n🚀 Done! You can now run your Cocotb simulation.")
        
    except Exception as e:
        print(e)
        sys.exit(1)