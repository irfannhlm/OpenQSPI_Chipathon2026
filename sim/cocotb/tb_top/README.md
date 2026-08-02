# Top-Level Testbench - `tb_top`

## Overview
A quick and simple integration testbench designed to verify that the top-level modules (UART, APB Bridge, and QSPI Master) are wired together correctly. This testbench simply acts as a host PC, sending bit-banged UART bytes to configure the QSPI Master's Control and Status Registers (CSRs) to verify the end-to-end communication datapath.

## Main Tests
- `test_csr_read_write`, a quick bus sanity check. It writes a value to a configuration register and reads it back to ensure the UART RX/TX and APB bridge are synchronized.

- `test_qspi_rdid`, an end-to-end integration check. It issues a standard 0x9F (Read JEDEC ID) command to the external flash and verifies the 3-byte response successfully travels all the way back out the UART TX pin.

- `test_qspi_program_read`, a basic datapath check. It commands the core to perform a Sector Erase, Page Program (0x02), and Normal Read (0x03) to ensure memory modification works from the absolute top level.

## Usage and Commands

### Run all integration tests:
```bash
make 
```

### Run with waveforms (for GTKWave):
> *Note: you can open existing `gtkwave_rtl.gtkw` or `gtkwave_gl.gtkw` GTKWave config*
```bash
make WAVES=1
```

### Run the Gate-Level Simulation (GLS):
> *Note: GLS could take up minutes*
```bash
make WAVES=1 GATELEVEL=1
```

### Run a single specific testcase:
```bash
make TESTCASE=test_qspi_program_read
```

## [Back to `testbench.md`](../../../docs/testbench.md)