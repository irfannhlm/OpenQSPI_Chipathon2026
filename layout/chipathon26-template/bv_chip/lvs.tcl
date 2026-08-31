# netgen: LVS of the assembled chip - Magic-extracted layout vs a fully
# device-level source netlist. No blackboxes for A09_BV or the pad ring.
#   netgen -batch source lvs.tcl
# env: BV_EXT_SPICE  SCL_SPICE  IO_SPICE  WSIO_SPICE  A09BV_PNL  PADRING_V
#      WRAPPER_V  NETGEN_SETUP  LVS_RPT
#
# Mirrors macros/A09_BV/runs/*/74-netgen-lvs/lvs_script.lvs one level up:
#   circuit1 = extracted layout
#   circuit2 = std-cell + IO-cell device subckts  +  A09_BV.pnl.v (defines A09_BV)
#              + A09_BV_padring.v (defines A09_BV_padring) + wrapper (defines A09_BV_chip)
# netgen resolves A09_BV_chip -> {padring -> io cells -> devices,
#                                 A09_BV  -> std cells -> devices}.
#
# PADRING_V is A09_BV_padring.prep.v (prep.py) - the supplied
# A09_BV_padring.v with the brk5 power-domain breaks modeled. See LVS_NOTES.md.

set circuit1 [readnet spice $env(BV_EXT_SPICE)]
set circuit2 [readnet verilog /dev/null]

readnet spice   $env(SCL_SPICE)  $circuit2
readnet spice   $env(IO_SPICE)   $circuit2
readnet spice   $env(WSIO_SPICE) $circuit2
readnet verilog $env(A09BV_PNL)  $circuit2
readnet verilog $env(PADRING_V)  $circuit2
readnet verilog $env(WRAPPER_V)  $circuit2

lvs "$circuit1 A09_BV_chip" "$circuit2 A09_BV_chip" \
    $env(NETGEN_SETUP) $env(LVS_RPT) -blackbox -json
