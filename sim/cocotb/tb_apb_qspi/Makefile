# pyuvm testbench for apb_qspi (APB wrapper + qspi_master + fifo + S25FL128S)
# Usage: make            - run all tests
#        make COCOTB_TESTCASE=ApbComplianceTest  - run one test
#        make test_apb / test_spi / test_cmds / test_flash - shortcuts
#        make WAVES=1    - dump sim_build/tb_apb_qspi.fst (cocotb built-in)

# sim configs
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
COMPILE_ARGS += -g2012 -pfileline=1 -Wno-timescale

# defines
COMPILE_ARGS += -D SPEEDSIM

# include dirs
COMPILE_ARGS += -I $(PWD)/../../../rtl/
COMPILE_ARGS += -I $(PWD)/../../srcs/S25FL128S/

# verilog sources
VERILOG_SOURCES += $(PWD)/tb_apb_qspi.sv
VERILOG_SOURCES += $(PWD)/../../../rtl/fifo.sv
VERILOG_SOURCES += $(PWD)/../../../rtl/qspi_master.sv
VERILOG_SOURCES += $(PWD)/../../../rtl/apb_qspi.sv
VERILOG_SOURCES += $(PWD)/../../srcs/S25FL128S/s25fl128s.v

TOPLEVEL = tb_apb_qspi
COCOTB_TEST_MODULES = test  # python testbench module (pyuvm_tb/test.py)

# prepend, don't clobber: keep caller's PYTHONPATH (e.g. a pip --target dir
# for cocotb-coverage inside IIC-OSIC-TOOLS)
export PYTHONPATH := $(PWD)/pyuvm_tb:$(PYTHONPATH)

# WAVES=1 is handled natively by cocotb's Makefile.icarus (fst dump module)
include $(shell cocotb-config --makefiles)/Makefile.sim

.PHONY: copy_mem_files compile sim regression test_apb test_spi test_cmds test_flash

copy_mem_files:
	@mkdir -p ./sim_build
	@cp -f ../../srcs/S25FL128S/*.mem ./ 2>/dev/null || true
	@cp -f ../../srcs/S25FL128S/*.mem ./sim_build/ 2>/dev/null || true

compile: copy_mem_files
sim: copy_mem_files
regression: copy_mem_files

# single-test shortcuts (same spirit as ldpc-personal's group_* targets)
test_apb:
	$(MAKE) sim COCOTB_TESTCASE=ApbComplianceTest
test_spi:
	$(MAKE) sim COCOTB_TESTCASE=SpiComplianceTest
test_cmds:
	$(MAKE) sim COCOTB_TESTCASE=AllCommandsTest
test_flash:
	$(MAKE) sim COCOTB_TESTCASE=FlashModelTest
