# sim configs
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
COMPILE_ARGS += -g2012 -pfileline=1 -Wno-timescale

# include dirs
COMPILE_ARGS += -I $(PWD)/../../../rtl/
COMPILE_ARGS += -I $(PWD)/../../srcs/S25FL128S/
COMPILE_ARGS += -I $(PWD)/../../srcs/W25QxxNE_Family_v1.0n/
COMPILE_ARGS += -I $(PWD)/../../srcs/MX25L51245G/

# verilog sources
VERILOG_SOURCES += $(PWD)/tb_qspi_master.sv
VERILOG_SOURCES += $(PWD)/../../../rtl/fifo.sv
VERILOG_SOURCES += $(PWD)/../../srcs/S25FL128S/s25fl128s.v
VERILOG_SOURCES += $(PWD)/../../srcs/W25QxxNE_Family_v1.0n/W25QxxNExxIx_v1.0n.v
VERILOG_SOURCES += $(PWD)/../../srcs/MX25L51245G/MX25L51245G.v
VERILOG_SOURCES += $(PWD)/../../srcs/23LC1024/23LC1024.v

TOPLEVEL = tb_qspi_master
COCOTB_TEST_MODULES = tb_qspi_master # python testbench module

FIFO_DEPTH ?= 8
COMPILE_ARGS += -P $(TOPLEVEL).FIFO_DEPTH=$(FIFO_DEPTH)

export SKIP_ALL_READS ?= 0
export SKIP_RANDOM_WRITES ?= 0

ifeq ($(GATELEVEL), 1)
    # --- Gate-Level Simulation (GLS) ---
    $(info *** RUNNING POST-SYNTHESIS GATE-LEVEL SIMULATION ***)
    
    VERILOG_SOURCES += $(PWD)/../../../synth/yosys/qspi_master_4cs_nl.v
    VERILOG_SOURCES += /foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/gf180mcu_fd_sc_mcu7t5v0.v
    VERILOG_SOURCES += /foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/primitives.v
    
    # Disable specify blocks and use typical delays for zero-delay gate sim
    COMPILE_ARGS += -gspecify -Ttyp -DGATELEVEL
else
    # --- Standard RTL Simulation ---
    $(info *** RUNNING STANDARD RTL SIMULATION ***)
	VERILOG_SOURCES += $(PWD)/../../../rtl/qspi_master.sv
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

.PHONY: copy_mem_files compile sim regression

copy_mem_files:
	@mkdir -p ./sim_build
	@cp -f ../../srcs/S25FL128S/*.mem ./ 2>/dev/null || true
	@cp -f ../../srcs/W25QxxNE_Family_v1.0n/*.TXT ./ 2>/dev/null || true
	@cp -f ../../srcs/MX25L51245G/*.TXT ./ 2>/dev/null || true
	
compile: copy_mem_files
sim: copy_mem_files
regression: copy_mem_files