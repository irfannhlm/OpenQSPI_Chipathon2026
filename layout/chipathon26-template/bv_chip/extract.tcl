# Magic: extract a SPICE netlist from the assembled full-chip GDS for LVS.
#   magic -dnull -noconsole -rcfile <gf180mcuD.magicrc> extract.tcl
# env: BV_GDS  BV_TOP  BV_EXT_DIR  BV_EXT_SPICE
# The .magicrc sets up the GF180 tech; the GDS carries the full cell hierarchy,
# so every IO cell and A09_BV is extracted to devices - no blackboxes.

set gds  $env(BV_GDS)
set top  $env(BV_TOP)
set edir $env(BV_EXT_DIR)
set osp  $env(BV_EXT_SPICE)

file mkdir $edir
cd $edir

gds read $gds
load $top
select top cell

# promote the 88 perimeter-ball labels (added by assemble.py) to ports so the
# extracted .subckt A09_BV_chip has a port list for LVS
port makeall

extract no all
extract do local
extract all

ext2spice lvs
ext2spice -o $osp
puts "wrote $osp"
quit -noprompt
