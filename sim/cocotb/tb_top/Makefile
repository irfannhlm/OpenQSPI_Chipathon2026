# sim configs
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
# COMPILE_ARGS += -g2012 -pfileline=1 -Wno-timescale

# include dirs
COMPILE_ARGS += -I $(PWD)/../../../rtl/
COMPILE_ARGS += -I $(PWD)/../../srcs/S25FL128S/
COMPILE_ARGS += -I $(PWD)/../../srcs/W25QxxNE_Family_v1.0n/
COMPILE_ARGS += -I $(PWD)/../../srcs/MX25L51245G/

# verilog sources
VERILOG_SOURCES += $(PWD)/tb_top.sv
VERILOG_SOURCES += $(PWD)/../../srcs/S25FL128S/s25fl128s.v
VERILOG_SOURCES += $(PWD)/../../srcs/W25QxxNE_Family_v1.0n/W25QxxNExxIx_v1.0n.v
VERILOG_SOURCES += $(PWD)/../../srcs/MX25L51245G/MX25L51245G.v

TOPLEVEL = tb_top
COCOTB_TEST_MODULES = tb_top

export TEST_BAUD ?= 921600
export CLOCK_FREQ ?= 50000000

ifeq ($(GATELEVEL), 1)
    # --- Gate-Level Simulation (GLS) ---
    $(info *** RUNNING POST-SYNTHESIS GATE-LEVEL SIMULATION ***)
    
    VERILOG_SOURCES += $(PWD)/../../../synth/yosys/top_netlist.v
    VERILOG_SOURCES += /foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/gf180mcu_fd_sc_mcu7t5v0.v
    VERILOG_SOURCES += /foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/primitives.v
    
    # Disable specify blocks and use typical delays for zero-delay gate sim
    COMPILE_ARGS += -gspecify -Ttyp -DGATELEVEL
else
    # --- Standard RTL Simulation ---
    $(info *** RUNNING STANDARD RTL SIMULATION ***)
	COMPILE_ARGS += -P $(TOPLEVEL).BAUD_RATE=$(TEST_BAUD) -P $(TOPLEVEL).CLOCK_FREQ=$(CLOCK_FREQ)
	VERILOG_SOURCES += $(PWD)/../../../rtl/*.sv
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

.PHONY: copy_mem_files compile sim regression

copy_mem_files:
	@mkdir -p ./sim_build
	@cp -f ../../srcs/S25FL128S/*.mem ./ 2>/dev/null || true
	@cp -f ../../srcs/MX25L51245G/*.TXT ./ 2>/dev/null || true
	@cp -f ../../srcs/MX25L51245G/*.mem ./ 2>/dev/null || true
	@cp -f ../../srcs/MX25L51245G/*.dat ./ 2>/dev/null || true
	
compile: copy_mem_files
sim: copy_mem_files
regression: copy_mem_files