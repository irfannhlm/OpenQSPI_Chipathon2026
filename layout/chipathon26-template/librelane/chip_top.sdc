# SPDX-License-Identifier: Apache-2.0
#
# chip_top constraints for variant BV, against the supplied A09_BV padring.
#
# Ports here are bond-pad slot names, all declared `inout wire` in chip_top.sv.
# The pad-to-signal mapping comes from project_defs/BV/A09_BV_pad_map.yaml:
#
#   W12 = VSS          W17 = uart_tx     W20 = qspi_sck
#   W13 = VDD          W18 = qspi_csn[0] W21 = qspi_io[0]
#   W14 = clk          W19 = qspi_csn[1] W22 = qspi_io[1]
#   W15 = rst_n                          N01 = qspi_io[2]
#   W16 = uart_rx                        N02 = qspi_io[3]
#
# The clock is created on the *pad* port W14 so the in_s pad delay is inside
# the clock path. CLOCK_NET is W14_Y (the core-side net) because cts.tcl
# searches for nets, not ports -- do not collapse the two.

current_design $::env(DESIGN_NAME)
set_units -time ns

set clock_port [lindex $::env(CLOCK_PORT) 0]
puts "\[INFO] Using clock port $clock_port…"
create_clock [get_ports $clock_port] -name $clock_port -period $::env(CLOCK_PERIOD)
set clocks [get_clocks $clock_port]

# Reset is asynchronous.
set_false_path -from [get_ports W15]

set input_delay_value [expr $::env(CLOCK_PERIOD) * $::env(IO_DELAY_CONSTRAINT) / 100]
set output_delay_value [expr $::env(CLOCK_PERIOD) * $::env(IO_DELAY_CONSTRAINT) / 100]
puts "\[INFO] Setting input delay to: $input_delay_value"
puts "\[INFO] Setting output delay to: $output_delay_value"

# Bidirectional pads (gf180mcu_fd_io__bi_t): uart_tx, qspi_csn, qspi_sck, qspi_io.
# Every port is `inout`, so all_inputs/all_outputs cannot classify them --
# they are listed explicitly.
set bidir_ports [get_ports {
    W17
    W18 W19
    W20
    W21 W22 N01 N02
}]

set_input_delay  -min 0                   -clock $clocks $bidir_ports
set_input_delay  -max $input_delay_value  -clock $clocks $bidir_ports
set_output_delay $output_delay_value      -clock $clocks $bidir_ports

# Input-only pads: uart_rx (in_c). rst_n (W15) is false-pathed above and the
# clock (W14) must not carry an input delay.
set input_ports [get_ports { W16 }]

set_input_delay -min 0                  -clock $clocks $input_ports
set_input_delay -max $input_delay_value -clock $clocks $input_ports

set_max_fanout $::env(MAX_FANOUT_CONSTRAINT) [current_design]
if { [info exists ::env(MAX_TRANSITION_CONSTRAINT)] } {
    set_max_transition $::env(MAX_TRANSITION_CONSTRAINT) [current_design]
}
if { [info exists ::env(MAX_CAPACITANCE_CONSTRAINT)] } {
    set_max_capacitance $::env(MAX_CAPACITANCE_CONSTRAINT) [current_design]
}

set cap_load [expr $::env(OUTPUT_CAP_LOAD) / 1000.0]
puts "\[INFO] Setting load to: $cap_load"
set_load $cap_load $bidir_ports

puts "\[INFO] Setting clock uncertainty to: $::env(CLOCK_UNCERTAINTY_CONSTRAINT)"
set_clock_uncertainty $::env(CLOCK_UNCERTAINTY_CONSTRAINT) $clocks

puts "\[INFO] Setting clock transition to: $::env(CLOCK_TRANSITION_CONSTRAINT)"
set_clock_transition $::env(CLOCK_TRANSITION_CONSTRAINT) $clocks

puts "\[INFO] Setting timing derate to: $::env(TIME_DERATING_CONSTRAINT)%"
set_timing_derate -early [expr 1-[expr $::env(TIME_DERATING_CONSTRAINT) / 100]]
set_timing_derate -late  [expr 1+[expr $::env(TIME_DERATING_CONSTRAINT) / 100]]

if { [info exists ::env(OPENLANE_SDC_IDEAL_CLOCKS)] && $::env(OPENLANE_SDC_IDEAL_CLOCKS) } {
    unset_propagated_clock [all_clocks]
} else {
    set_propagated_clock [all_clocks]
}
