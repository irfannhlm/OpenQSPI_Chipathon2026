# ==========================================
# Cocotb Makefile for QSPI Master Testbench
# ==========================================

# sim configs
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
COMPILE_ARGS += -g2012 -pfileline=1 -Wno-timescale -DSPEEDSIM -DW25Q65NE -DIM
#SIM_ARGS += -fst

# verilog sources
VERILOG_SOURCES += $(PWD)/tb_qspi_master.sv
VERILOG_SOURCES += $(PWD)/../../../rtl/qspi_master.sv
VERILOG_SOURCES += $(PWD)/../../srcs/S25FL128S/s25fl128s.v
VERILOG_SOURCES += $(PWD)/../../srcs/W25QxxNE_Family_v1.0n/W25QxxNExxIx_v1.0n.v
VERILOG_SOURCES += $(PWD)/../../srcs/MX25L51245G/MX25L51245G.v

TOPLEVEL = tb_qspi_master
MODULE = tb_qspi_master # python testbench module

#export COCOTB_RESULTS_FILE = qspi_waves.fst

include $(shell cocotb-config --makefiles)/Makefile.sim