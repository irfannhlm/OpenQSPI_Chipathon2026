# sim configs
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
# COMPILE_ARGS += -g2012 -pfileline=1 -Wno-timescale
SIM_ARGS += -l iverilog_sim.log

TOPLEVEL = uart_simple
COCOTB_TEST_MODULES = tb_uart_simple

export TEST_BAUD ?= 921600
export CLOCK_FREQ ?= 50000000

# ==============================================================================
# Dynamic RTL vs GLS Toggle
# ==============================================================================

ifeq ($(GATES), 1)
    # --- Gate-Level Simulation (GLS) ---
    $(info *** RUNNING POST-SYNTHESIS GATE-LEVEL SIMULATION ***)
    
    VERILOG_SOURCES += $(PWD)/../../../synth/yosys/uart_simple_netlist.v
    VERILOG_SOURCES += /foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/gf180mcu_fd_sc_mcu7t5v0.v
    VERILOG_SOURCES += /foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/primitives.v
    
    # Disable specify blocks and use typical delays for zero-delay gate sim
    COMPILE_ARGS += -gspecify -Ttyp
else
    # --- Standard RTL Simulation ---
    $(info *** RUNNING STANDARD RTL SIMULATION ***)
	COMPILE_ARGS += -P $(TOPLEVEL).BAUD_RATE=$(TEST_BAUD) -P $(TOPLEVEL).CLOCK_FREQ=$(CLOCK_FREQ)
	VERILOG_SOURCES += $(PWD)/../../../rtl/uart_simple.sv
endif

include $(shell cocotb-config --makefiles)/Makefile.sim