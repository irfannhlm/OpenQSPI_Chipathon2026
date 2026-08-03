# Project Overview
To design a fully functional 32-bit Quad Serial Peripheral Interface (QSPI) master controller used for communication with external memories. The IP should be entirely synthesizable using standard RTL digital flow with the target process node GF180MCU from GlobalFoundries. The final product should be tested using commercially available flash memory ICs, e.g. S25FL family from Infineon and W25Q family from Winbond.

# Target Specification
- Open-source, modular, and synthesizable
- Compatible with commercial flash memories
- Full support of single, dual, quad, and DDR modes (fast, IO, QPI)
- 50MHz target frequency (200Mbps at quad DDR)

# Main Architecture
![APB QSPI Architecture](docs/images/apb_qspi_arch.png)

# Design Testbench
There are three main testbench for this project, following bottom-up verification:
- [`tb_qspi_master`](sim/cocotb/tb_qspi_master/README.md), a command-specific custom testbench using cocotb and iverilog to test the [`qspi_master`](rtl/qspi_master.sv) core functionality (single, dual, quad, DDR) verified with official flash models (S25FL128S, W25Q65NE, MX25L51245G).
- [`tb_apb_qspi`](sim/cocotb/tb_apb_qspi/README.md), a comprehensive UVM-based testbench using pyUVM to evaluate the APB compliance and the QSPI commands coverage of the [`apb_qspi`](rtl/apb_qspi.sv) module.
- [`tb_top`](sim/cocotb/tb_top/README.md), a quick top level testbench to test top level integration ([`top`](rtl/top.sv)) with full program flow using UART.

More detailed explanations can be found in the respective documentations.


# Documentations
- [QSPI Master Module](docs/qspi_master.md)
- [APB Wrapped QSPI](docs/apb_qspi.md)
- [QSPI CSR](docs/qspi_csr.md)
- [UART FPGA GUI](docs/uart_fpga_gui.md)