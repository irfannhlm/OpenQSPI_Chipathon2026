onerror {resume}
quietly virtual signal -install {/chip_top_tb/i_chip_top/\i_chip_core.a09_inst } { (context /chip_top_tb/i_chip_top/\i_chip_core.a09_inst )&{\inst_apb_qspi.paddr_i[31] , \inst_apb_qspi.paddr_i[30] , \inst_apb_qspi.paddr_i[29] , \inst_apb_qspi.paddr_i[28] , \inst_apb_qspi.paddr_i[27] , \inst_apb_qspi.paddr_i[26] , \inst_apb_qspi.paddr_i[25] , \inst_apb_qspi.paddr_i[24] , \inst_apb_qspi.paddr_i[23] , \inst_apb_qspi.paddr_i[22] , \inst_apb_qspi.paddr_i[21] , \inst_apb_qspi.paddr_i[20] , \inst_apb_qspi.paddr_i[19] , \inst_apb_qspi.paddr_i[18] , \inst_apb_qspi.paddr_i[17] , \inst_apb_qspi.paddr_i[16] , \inst_apb_qspi.paddr_i[15] , \inst_apb_qspi.paddr_i[14] , \inst_apb_qspi.paddr_i[13] , \inst_apb_qspi.paddr_i[12] , \inst_apb_qspi.paddr_i[11] , \inst_apb_qspi.paddr_i[15] , \inst_apb_qspi.paddr_i[14] , \inst_apb_qspi.paddr_i[13] , \inst_apb_qspi.paddr_i[12] , \inst_apb_qspi.paddr_i[11] , \inst_apb_qspi.paddr_i[10] , \inst_apb_qspi.paddr_i[9] , \inst_apb_qspi.paddr_i[8] , \inst_apb_qspi.paddr_i[7] , \inst_apb_qspi.paddr_i[6] , \inst_apb_qspi.paddr_i[5] , \inst_apb_qspi.paddr_i[4] , \inst_apb_qspi.paddr_i[3] , \inst_apb_qspi.paddr_i[2] , \inst_apb_qspi.paddr_i[1] , \inst_apb_qspi.paddr_i[0] }} paddr
quietly virtual signal -install {/chip_top_tb/i_chip_top/\i_chip_core.a09_inst } { (context /chip_top_tb/i_chip_top/\i_chip_core.a09_inst )&{\inst_apb_qspi.pwdata_i[0] , \inst_apb_qspi.pwdata_i[1] , \inst_apb_qspi.pwdata_i[2] , \inst_apb_qspi.pwdata_i[3] , \inst_apb_qspi.pwdata_i[4] , \inst_apb_qspi.pwdata_i[5] , \inst_apb_qspi.pwdata_i[6] , \inst_apb_qspi.pwdata_i[7] , \inst_apb_qspi.pwdata_i[8] , \inst_apb_qspi.pwdata_i[9] , \inst_apb_qspi.pwdata_i[10] , \inst_apb_qspi.pwdata_i[11] , \inst_apb_qspi.pwdata_i[12] , \inst_apb_qspi.pwdata_i[13] , \inst_apb_qspi.pwdata_i[14] , \inst_apb_qspi.pwdata_i[15] , \inst_apb_qspi.pwdata_i[16] , \inst_apb_qspi.pwdata_i[17] , \inst_apb_qspi.pwdata_i[18] , \inst_apb_qspi.pwdata_i[19] , \inst_apb_qspi.pwdata_i[20] , \inst_apb_qspi.pwdata_i[21] , \inst_apb_qspi.pwdata_i[22] , \inst_apb_qspi.pwdata_i[23] , \inst_apb_qspi.pwdata_i[24] , \inst_apb_qspi.pwdata_i[25] , \inst_apb_qspi.pwdata_i[26] , \inst_apb_qspi.pwdata_i[27] , \inst_apb_qspi.pwdata_i[28] , \inst_apb_qspi.pwdata_i[29] , \inst_apb_qspi.pwdata_i[30] , \inst_apb_qspi.pwdata_i[31] }} pwdata
quietly virtual signal -install {/chip_top_tb/i_chip_top/\i_chip_core.a09_inst } { (context /chip_top_tb/i_chip_top/\i_chip_core.a09_inst )&{\inst_apb_qspi.pwdata_i[31] , \inst_apb_qspi.pwdata_i[30] , \inst_apb_qspi.pwdata_i[29] , \inst_apb_qspi.pwdata_i[28] , \inst_apb_qspi.pwdata_i[27] , \inst_apb_qspi.pwdata_i[26] , \inst_apb_qspi.pwdata_i[25] , \inst_apb_qspi.pwdata_i[24] , \inst_apb_qspi.pwdata_i[23] , \inst_apb_qspi.pwdata_i[22] , \inst_apb_qspi.pwdata_i[21] , \inst_apb_qspi.pwdata_i[20] , \inst_apb_qspi.pwdata_i[19] , \inst_apb_qspi.pwdata_i[18] , \inst_apb_qspi.pwdata_i[17] , \inst_apb_qspi.pwdata_i[16] , \inst_apb_qspi.pwdata_i[15] , \inst_apb_qspi.pwdata_i[14] , \inst_apb_qspi.pwdata_i[13] , \inst_apb_qspi.pwdata_i[12] , \inst_apb_qspi.pwdata_i[11] , \inst_apb_qspi.pwdata_i[10] , \inst_apb_qspi.pwdata_i[9] , \inst_apb_qspi.pwdata_i[8] , \inst_apb_qspi.pwdata_i[7] , \inst_apb_qspi.pwdata_i[6] , \inst_apb_qspi.pwdata_i[5] , \inst_apb_qspi.pwdata_i[4] , \inst_apb_qspi.pwdata_i[3] , \inst_apb_qspi.pwdata_i[2] , \inst_apb_qspi.pwdata_i[1] , \inst_apb_qspi.pwdata_i[0] }} pwdata001
quietly WaveActivateNextPane {} 0
add wave -noupdate -expand /chip_top_tb/bidir_PAD
add wave -noupdate /chip_top_tb/clk_i
add wave -noupdate {/chip_top_tb/i_chip_top/\i_chip_core.a09_inst /paddr}
add wave -noupdate -expand {/chip_top_tb/i_chip_top/\i_chip_core.a09_inst /pwdata001}
add wave -noupdate {/chip_top_tb/i_chip_top/\i_chip_core.a09_inst /\inst_apb_qspi.pwrite_i }
TreeUpdate [SetDefaultTree]
WaveRestoreCursors
quietly wave cursor active 0
configure wave -namecolwidth 415
configure wave -valuecolwidth 100
configure wave -justifyvalue left
configure wave -signalnamewidth 0
configure wave -snapdistance 10
configure wave -datasetprefix 0
configure wave -rowmargin 4
configure wave -childrowmargin 2
configure wave -gridoffset 0
configure wave -gridperiod 1
configure wave -griddelta 40
configure wave -timeline 0
configure wave -timelineunits ps
update
WaveRestoreZoom {3550347199 ps} {3550409535 ps}
