# sim configs
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
COMPILE_ARGS += -g2012 -pfileline=1 -Wno-timescale
#SIM_ARGS += -fst

# defines
COMPILE_ARGS += -D SPEEDSIM -D W25Q65NE -D IM

# include dirs
COMPILE_ARGS += -I $(PWD)/../../../rtl/
COMPILE_ARGS += -I $(PWD)/../../srcs/S25FL128S/
COMPILE_ARGS += -I $(PWD)/../../srcs/W25QxxNE_Family_v1.0n/
COMPILE_ARGS += -I $(PWD)/../../srcs/MX25L51245G/

# verilog sources
VERILOG_SOURCES += $(PWD)/tb_qspi_master.sv
VERILOG_SOURCES += $(PWD)/../../../rtl/qspi_master.sv
VERILOG_SOURCES += $(PWD)/../../srcs/S25FL128S/s25fl128s.v
VERILOG_SOURCES += $(PWD)/../../srcs/W25QxxNE_Family_v1.0n/W25QxxNExxIx_v1.0n.v
VERILOG_SOURCES += $(PWD)/../../srcs/MX25L51245G/MX25L51245G.v

TOPLEVEL = tb_qspi_master
COCOTB_TEST_MODULES = tb_qspi_master # python testbench module

#export COCOTB_RESULTS_FILE = qspi_waves.fst

include $(shell cocotb-config --makefiles)/Makefile.sim

.PHONY: copy_mem_files compile sim regression

copy_mem_files:
	@echo "--- Menyalin file inisialisasi memori ke folder simulasi ---"
	@mkdir -p ./sim_build
	@cp -f ../../srcs/S25FL128S/*.mem ./ 2>/dev/null || true
	@cp -f ../../srcs/S25FL128S/*.mem ./sim_build/ 2>/dev/null || true
	@cp -f ../../srcs/W25QxxNE_Family_v1.0n/*.TXT ./ 2>/dev/null || true
	@cp -f ../../srcs/W25QxxNE_Family_v1.0n/*.TXT ./sim_build/ 2>/dev/null || true
	@cp -f ../../srcs/MX25L51245G/*.TXT ./ 2>/dev/null || true
	@cp -f ../../srcs/MX25L51245G/*.TXT ./sim_build/ 2>/dev/null || true
	@cp -f ../../srcs/MX25L51245G/*.mem ./ 2>/dev/null || true
	@cp -f ../../srcs/MX25L51245G/*.mem ./sim_build/ 2>/dev/null || true
	@cp -f ../../srcs/MX25L51245G/*.dat ./ 2>/dev/null || true
	@cp -f ../../srcs/MX25L51245G/*.dat ./sim_build/ 2>/dev/null || true
	
compile: copy_mem_files
sim: copy_mem_files
regression: copy_mem_files