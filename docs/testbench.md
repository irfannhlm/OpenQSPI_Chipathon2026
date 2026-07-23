# Design Testbench
There are three main testbench for this project, following bottom-up verification:
- [`tb_qspi_master`](../sim/cocotb/tb_qspi_master/README.md), a command-specific custom testbench using cocotb and iverilog to test the [`qspi_mater`](../rtl/qspi_master.sv) core functionality (single, dual, quad, DDR) verified with official flash models (S25FL128S, W25Q65NE, MX25L51245G).
- [`tb_apb_qspi`](../sim/cocotb/tb_apb_qspi/README.md), a comprehensive UVM-based testbench using pyUVM to evaluate the APB compliance and the QSPI commands coverage of the [`apb_qspi`](../rtl/apb_qspi.sv) module.
- [`tb_top`](../sim/cocotb/tb_top/README.md), a quick top level testbench to test top level integration with UART communication to configure the QSPI CSR

More detailed explanations can be found in the respective documentations.


## [Back to README](../README.md)