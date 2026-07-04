README for Verilog Model File

Overview:
This README provides information about the Verilog model file included in this repository.
The model is designed to simulate "1.2V SPI-NOR-Flash, W25QxxNE Family"

Disclaimer:
This Verilog model is provided "as is" without any warranties or guarantees.
The author(s) make no representations or warranties of any kind, express or implied,
about the completeness, accuracy, reliability, suitability,
or availability with respect to the model or the information contained in the documentation.
Any reliance you place on such information is therefore strictly at your own risk.

Usage:
1.Requirements: Ensure you have a compatible Verilog simulator installed.
2.Compilation: Compile the Verilog file using your simulator.
3.Simulation: Run the simulation to verify the functionality of the model.
4.Modification: Feel free to modify the model to suit your needs but note that any changes are your responsibility.

Testing:
This model has been tested on the three most popular compilers:
*ncVerilog
*VCS
*ModelSim
Based on "Target W25Q81NE RevA1 08222024" Datasheet for 8Mb
Based on "Target W25Q16NE RevA4 08222024 KMS" Datasheet for 16Mb
Based on "Target W25Q32NE RevA1 08272024" Datasheet for 32Mb
Based on "Target W25Q65NE RevA1 09252024" Datasheet for 64Mb

Files:
W25QxxNExxIx_v1.0n.v     : The main Verilog model file.
W25QxxNExxIx_test.v      : A testbench example file to simulate and verify the model.
SECSI.TXT                : Security Array Initial Data file
SFDP.TXT                 : SFDP Array Initial Data file
SREG.TXT                 : Status Register Initial Data file
ReadMe.TXT               : This file

===========================================================
                 NE Family User Guide
===========================================================

1. Interface Mode
    Required selection (no default):
    -----------------------------------------------------------
    | Use         | Model | DTR | SR[QE]     | JEDEC_ID[15:8] |
    |-------------|-------|-----|------------|----------------|
    | define+IM   | IM    | V   | default 0  | 8'h85          |
    | define+IG   | IG    | X   | default 1  | 8'h65          |
    -----------------------------------------------------------

2. Density Configuration
    Select one of the following devices:
    ------------------------------------------------------------------------------------
    | Use                | Model     | Density(Mb) | Device ID | JEDEC_ID[7:0] | tCE(s) |
    |--------------------|-----------|-------------|-----------|---------------|--------|
    | define+W25Q81NE    | W25Q81NE  | 8           | 8'h13     | 8'h14         | 5      |
    | define+W25Q16NE    | W25Q16NE  | 16          | 8'h14     | 8'h15         | 10     |
    | define+W25Q32NE    | W25Q32NE  | 32          | 8'h15     | 8'h16         | 20     |
    | define+W25Q65NE    | W25Q65NE  | 64          | 8'h16     | 8'h17         | 40     |
    -------------------------------------------------------------------------------------

Note:
    - The density, Device ID, JEDEC ID, and chip erase time vary depending on the specific combination.

