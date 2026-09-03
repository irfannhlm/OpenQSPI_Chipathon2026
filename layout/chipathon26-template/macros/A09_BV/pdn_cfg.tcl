# Copyright 2025 LibreLane Contributors
#
# Adapted from OpenLane
#
# Copyright 2020-2022 Efabless Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
source $::env(SCRIPTS_DIR)/openroad/common/set_global_connections.tcl
set_global_connections

set secondary []
foreach vdd $::env(VDD_NETS) gnd $::env(GND_NETS) {
    if { $vdd != $::env(VDD_NET)} {
        lappend secondary $vdd

        set db_net [[ord::get_db_block] findNet $vdd]
        if {$db_net == "NULL"} {
            set net [odb::dbNet_create [ord::get_db_block] $vdd]
            $net setSpecial
            $net setSigType "POWER"
        }
    }

    if { $gnd != $::env(GND_NET)} {
        lappend secondary $gnd

        set db_net [[ord::get_db_block] findNet $gnd]
        if {$db_net == "NULL"} {
            set net [odb::dbNet_create [ord::get_db_block] $gnd]
            $net setSpecial
            $net setSigType "GROUND"
        }
    }
}

set_voltage_domain -name CORE -power $::env(VDD_NET) -ground $::env(GND_NET) \
    -secondary_power $secondary



if { $::env(PDN_MULTILAYER) == 1 } {

    set arg_list [list]
    if { $::env(PDN_ENABLE_PINS) } {
        lappend arg_list -pins "$::env(PDN_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)"
    }

    define_pdn_grid \
        -name stdcell_grid \
        -starts_with POWER \
        -voltage_domain CORE \
        {*}$arg_list

    set arg_list [list]
    append_if_equals arg_list PDN_EXTEND_TO "core_ring" -extend_to_core_ring
    append_if_equals arg_list PDN_EXTEND_TO "boundary" -extend_to_boundary

    add_pdn_stripe \
        -grid stdcell_grid \
        -layer $::env(PDN_VERTICAL_LAYER) \
        -width $::env(PDN_VWIDTH) \
        -pitch $::env(PDN_VPITCH) \
        -offset $::env(PDN_VOFFSET) \
        -spacing $::env(PDN_VSPACING) \
        -starts_with POWER \
        {*}$arg_list

    add_pdn_stripe \
        -grid stdcell_grid \
        -layer $::env(PDN_HORIZONTAL_LAYER) \
        -width $::env(PDN_HWIDTH) \
        -pitch $::env(PDN_HPITCH) \
        -offset $::env(PDN_HOFFSET) \
        -spacing $::env(PDN_HSPACING) \
        -starts_with POWER \
        {*}$arg_list

    add_pdn_connect \
        -grid stdcell_grid \
        -layers "$::env(PDN_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)"
} else {

    set arg_list [list]
    if { $::env(PDN_ENABLE_PINS) } {
        lappend arg_list -pins "$::env(PDN_VERTICAL_LAYER)"
    }

    define_pdn_grid \
        -name stdcell_grid \
        -starts_with POWER \
        -voltage_domain CORE \
        {*}$arg_list

    set arg_list [list]
    append_if_equals arg_list PDN_EXTEND_TO "core_ring" -extend_to_core_ring
    append_if_equals arg_list PDN_EXTEND_TO "boundary" -extend_to_boundary

    add_pdn_stripe \
        -grid stdcell_grid \
        -layer $::env(PDN_VERTICAL_LAYER) \
        -width $::env(PDN_VWIDTH) \
        -pitch $::env(PDN_VPITCH) \
        -offset $::env(PDN_VOFFSET) \
        -spacing $::env(PDN_VSPACING) \
        -starts_with POWER \
        {*}$arg_list
}

# Adds the standard cell rails if enabled.
if { $::env(PDN_ENABLE_RAILS) == 1 } {
    add_pdn_stripe \
        -grid stdcell_grid \
        -layer $::env(PDN_RAIL_LAYER) \
        -width $::env(PDN_RAIL_WIDTH) \
        -followpins

    add_pdn_connect \
        -grid stdcell_grid \
        -layers "$::env(PDN_RAIL_LAYER) $::env(PDN_VERTICAL_LAYER)"
}


# Adds the core ring if enabled.
if { $::env(PDN_CORE_RING) == 1 } {
    if { $::env(PDN_MULTILAYER) == 1 } {
        set arg_list [list]
        append_if_flag arg_list PDN_CORE_RING_ALLOW_OUT_OF_DIE -allow_out_of_die
        append_if_flag arg_list PDN_CORE_RING_CONNECT_TO_PADS -connect_to_pads
        append_if_equals arg_list PDN_EXTEND_TO "boundary" -extend_to_boundary

        set pdn_core_vertical_layer $::env(PDN_VERTICAL_LAYER)
        set pdn_core_horizontal_layer $::env(PDN_HORIZONTAL_LAYER)

        if { [info exists ::env(PDN_CORE_VERTICAL_LAYER)] } {
            set pdn_core_vertical_layer $::env(PDN_CORE_VERTICAL_LAYER)
        }

        if { [info exists ::env(PDN_CORE_HORIZONTAL_LAYER)] } {
            set pdn_core_horizontal_layer $::env(PDN_CORE_HORIZONTAL_LAYER)
        }

        add_pdn_ring \
            -grid stdcell_grid \
            -layers "$pdn_core_vertical_layer $pdn_core_horizontal_layer" \
            -widths "$::env(PDN_CORE_RING_VWIDTH) $::env(PDN_CORE_RING_HWIDTH)" \
            -spacings "$::env(PDN_CORE_RING_VSPACING) $::env(PDN_CORE_RING_HSPACING)" \
            -core_offset "$::env(PDN_CORE_RING_VOFFSET) $::env(PDN_CORE_RING_HOFFSET)" \
            {*}$arg_list

        if { [info exists ::env(PDN_CORE_VERTICAL_LAYER)] } {
            add_pdn_connect \
                -grid stdcell_grid \
                -layers "$::env(PDN_CORE_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)"
        }

        if { [info exists ::env(PDN_CORE_HORIZONTAL_LAYER)] } {
            add_pdn_connect \
                -grid stdcell_grid \
                -layers "$::env(PDN_CORE_HORIZONTAL_LAYER) $::env(PDN_VERTICAL_LAYER)"
        }

        if { [info exists ::env(PDN_CORE_VERTICAL_LAYER)] && [info exists ::env(PDN_CORE_HORIZONTAL_LAYER)] } {
            add_pdn_connect \
                -grid stdcell_grid \
                -layers "$::env(PDN_CORE_VERTICAL_LAYER) $::env(PDN_CORE_HORIZONTAL_LAYER)"
        }

    } else {
        throw APPLICATION "PDN_CORE_RING cannot be used when PDN_MULTILAYER is set to false."
    }
}

# =============================================================================
# Padframe power bridge  (A09_BV: connect west-edge power pins to the core ring)
# =============================================================================
# The FP_DEF_TEMPLATE (A09_BV.def) provides Metal2-only VDD/VSS pin stubs on the
# west die edge. pdngen builds the core ring inboard of them, with VSS as the
# outer vertical Metal2 leg and VDD as the inner one. A Metal2 run from the VDD
# stubs would short across the VSS leg, so each bridge is built as:
#
#   VSS :  Metal2 (edge)  ->  Metal2 across its own ring leg           (no via)
#   VDD :  Metal2 landing  ->  Via2 col -> Metal3 hop (over the VSS leg)
#                          ->  Via2 col -> onto the VDD ring leg
#
# Both bridges are the same width (_PG_BRIDGE_W_UM), centred on the pin.
#
# Notes on *why it is done here, wrapped around pdngen*:
#   * GeneratePDN (this step) runs BEFORE Odb.ApplyDEFTemplate, so the VDD/VSS
#     bterms do not exist yet -> pin Y positions are parsed from the template DEF.
#   * The core-ring geometry only exists AFTER pdngen runs, so the builder is
#     invoked from a thin wrapper installed over `pdngen`. It reads the real ring
#     legs from the DB and therefore tracks whatever PDN_CORE_RING_* values are
#     in effect.
#   * Geometry is added to the VDD/VSS SPECIAL nets (dbSWire), never as pin-port
#     shapes.
#   * The Via2 stack is a VIARULE-generated via (Via2_GEN_HH + ROWCOL), i.e. the
#     exact DEF form pdngen emits for the ring, so Magic and KLayout stream it to
#     identical GDS -> no XOR difference.

set ::_PG_BRIDGE_W_UM   2.0     ;# width (Y) of the VSS and VDD bridges
set ::_PG_M2_LAND_UM    2.0     ;# VDD Metal2 landing reach from the die edge
set ::_PG_M3_EDGE_UM    0.20    ;# Metal3 hop start offset from the die edge
set ::_PG_VIA_ROWS      3       ;# Via2 cut rows per stack  (Y)
set ::_PG_VIA_COLS      3       ;# Via2 cut cols per stack  (X)

proc _pg_template_path {} {
    # Locate the FP_DEF_TEMPLATE. That env var is not exported into the
    # GeneratePDN step, so fall back to reading config.yaml (which sits next to
    # PDN_CFG) and resolving its `FP_DEF_TEMPLATE: dir::<rel>` value.
    if {[info exists ::env(FP_DEF_TEMPLATE)] && [file readable $::env(FP_DEF_TEMPLATE)]} {
        return $::env(FP_DEF_TEMPLATE)
    }
    if {![info exists ::env(PDN_CFG)]} {
        error "power-bridge: cannot locate template (no FP_DEF_TEMPLATE, no PDN_CFG)"
    }
    set cfgdir [file dirname $::env(PDN_CFG)]
    set cfg    [file join $cfgdir config.yaml]
    if {[file readable $cfg]} {
        set fh [open $cfg r]; set txt [read $fh]; close $fh
        if {[regexp {FP_DEF_TEMPLATE:\s*dir::(\S+)} $txt -> rel]} {
            set p [file normalize [file join $cfgdir $rel]]
            if {[file readable $p]} { return $p }
        }
    }
    error "power-bridge: could not resolve FP_DEF_TEMPLATE from $cfg"
}

proc _pg_template_pin_rows {net_name} {
    # -> {tdbu {{y1 y2 x2} ...}} : Metal2 stub rows for $net_name, in template DBU
    set path [_pg_template_path]
    set fh [open $path r]
    set tdbu 0
    set rows {}
    set in 0
    while {[gets $fh line] >= 0} {
        if {[regexp {UNITS\s+DISTANCE\s+MICRONS\s+(\d+)} $line -> u]} {
            set tdbu $u; continue
        }
        if {[regexp {^-\s+(\S+)\s+\+\s+NET\s+(\S+)} $line -> pn nn]} {
            set in [expr {$nn eq $net_name}]; continue
        }
        if {$in} {
            if {[regexp {LAYER\s+Metal2\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)} \
                     $line -> x1 y1 x2 y2]} {
                lappend rows [list $y1 $y2 $x2]
            }
            if {[string first ";" $line] >= 0} { set in 0 }
        }
    }
    close $fh
    if {$tdbu == 0} {
        error "power-bridge: no 'UNITS DISTANCE MICRONS' in $path"
    }
    return [list $tdbu $rows]
}

proc _pg_west_leg {net} {
    # -> {xmin xmax} of $net's west-most tall vertical Metal2 stripe (the ring leg)
    set best ""
    foreach sw [$net getSWires] {
        foreach box [$sw getWires] {
            if {[$box isVia]} { continue }
            set ly [$box getTechLayer]
            if {$ly eq "NULL" || [$ly getName] ne "Metal2"} { continue }
            set w [expr {[$box xMax] - [$box xMin]}]
            set h [expr {[$box yMax] - [$box yMin]}]
            if {$h < 5 * $w} { continue }
            if {$best eq "" || [$box xMin] < [lindex $best 0]} {
                set best [list [$box xMin] [$box xMax]]
            }
        }
    }
    return $best
}

proc _pg_make_stack_via {block name m2 v2 m3 nrow ncol} {
    # An $nrow x $ncol Via2 stack as a VIARULE-generated via (Via2_GEN_HH), i.e.
    # the same DEF form pdngen uses for the ring -> both GDS streamers expand it
    # identically -> no XOR.  GF180 Via2: 0.26 um cut (Vn.1); 0.06 um enclosure
    # all round (Vn.3); 0.26 um cut spacing, 0.36 um once a direction has >=4
    # cuts (Vn.2a/2b).  All in um * block DBU, so it is PDK/DBU agnostic.
    set dbu [$block getDbUnitsPerMicron]
    set cut [expr {round(0.26 * $dbu)}]
    set enc [expr {round(0.06 * $dbu)}]
    set sp  [expr {round(($nrow >= 4 || $ncol >= 4 ? 0.36 : 0.26) * $dbu)}]
    set v [odb::dbVia_create $block $name]
    $v setViaGenerateRule [[$block getTech] findViaGenerateRule "Via2_GEN_HH"]
    set p [$v getViaParams]
    $p setBottomLayer $m2
    $p setCutLayer    $v2
    $p setTopLayer    $m3
    $p setXCutSize $cut ; $p setYCutSize $cut
    $p setXCutSpacing $sp ; $p setYCutSpacing $sp
    $p setXBottomEnclosure $enc ; $p setYBottomEnclosure $enc
    $p setXTopEnclosure    $enc ; $p setYTopEnclosure    $enc
    $p setNumCutRows $nrow ; $p setNumCutCols $ncol
    $v setViaParams $p
    return $v
}

proc _pg_build_power_bridges {} {
    if {[info exists ::_PG_DONE]} { return }
    set ::_PG_DONE 1
    set block [ord::get_db_block]
    set tech  [ord::get_db_tech]
    set dbu   [$block getDbUnitsPerMicron]
    set m2    [$tech findLayer Metal2]
    set v2    [$tech findLayer Via2]
    set m3    [$tech findLayer Metal3]
    if {$m2 eq "NULL" || $v2 eq "NULL" || $m3 eq "NULL"} {
        error "power-bridge: Metal2/Via2/Metal3 not found in tech"
    }
    set bw    [expr {int($::_PG_BRIDGE_W_UM * $dbu)}]
    set landx [expr {int($::_PG_M2_LAND_UM  * $dbu)}]
    set m3x0  [expr {int($::_PG_M3_EDGE_UM  * $dbu)}]
    set colv  [_pg_make_stack_via $block PG_V2_COL $m2 $v2 $m3 \
                   $::_PG_VIA_ROWS $::_PG_VIA_COLS]

    set vdd [$block findNet VDD]
    set vss [$block findNet VSS]
    if {$vdd eq "NULL" || $vss eq "NULL"} { error "power-bridge: VDD/VSS net missing" }

    set vss_leg [_pg_west_leg $vss]
    set vdd_leg [_pg_west_leg $vdd]
    if {$vss_leg eq "" || $vdd_leg eq ""} {
        error "power-bridge: could not find VDD/VSS core-ring legs"
    }
    lassign $vss_leg vssL vssR
    lassign $vdd_leg vddL vddR
    puts "\[INFO\] power-bridge: VSS leg x=($vssL $vssR)  VDD leg x=($vddL $vddR)"

    # ---- VSS: coplanar Metal2, die edge -> across its own ring leg ----
    lassign [_pg_template_pin_rows VSS] tdbu rows
    if {[llength $rows] == 0} { error "power-bridge: no VSS Metal2 stubs in template" }
    set sc [expr {double($dbu) / $tdbu}]
    set sw [odb::dbSWire_create $vss "ROUTED"]
    foreach r $rows {
        lassign $r y1 y2 x2
        set cy [expr {int(($y1 + $y2) * 0.5 * $sc)}]
        odb::dbSBox_create $sw $m2 0 [expr {$cy - $bw / 2}] \
            $vssR [expr {$cy + $bw / 2}] "STRIPE"
    }
    puts "\[INFO\] power-bridge: VSS  [llength $rows] Metal2 bridges"

    # ---- VDD: Metal2 landing -> Via2 col -> Metal3 hop -> Via2 col -> ring leg ----
    lassign [_pg_template_pin_rows VDD] tdbu rows
    if {[llength $rows] == 0} { error "power-bridge: no VDD Metal2 stubs in template" }
    set sc  [expr {double($dbu) / $tdbu}]
    set sw  [odb::dbSWire_create $vdd "ROUTED"]
    set xcw [expr {$landx / 2}]                  ;# west via column (in the landing)
    set xce [expr {($vddL + $vddR) / 2}]         ;# east via column (centre of VDD leg)
    set nv 0
    foreach r $rows {
        lassign $r y1 y2 x2
        set cy [expr {int(($y1 + $y2) * 0.5 * $sc)}]
        set lo [expr {$cy - $bw / 2}]
        set hi [expr {$cy + $bw / 2}]
        odb::dbSBox_create $sw $m2 0     $lo $landx $hi "STRIPE"   ;# landing
        odb::dbSBox_create $sw $m3 $m3x0 $lo $vddR  $hi "STRIPE"   ;# hop over the VSS leg
        odb::dbSBox_create $sw $colv $xcw $cy "STRIPE"             ;# pin-side via column
        odb::dbSBox_create $sw $colv $xce $cy "STRIPE"             ;# ring-leg via column
        incr nv 2
    }
    puts "\[INFO\] power-bridge: VDD  [llength $rows] bridges, $nv Via2 stacks (${::_PG_VIA_ROWS}x${::_PG_VIA_COLS} each)"
}

# Install the post-pdngen hook (idempotent).
if {[info commands pdngen] ne "" && [info commands _pg_pdngen_real] eq ""} {
    rename pdngen _pg_pdngen_real
    proc pdngen {args} {
        set rc [uplevel 1 [list _pg_pdngen_real {*}$args]]
        if {[catch {_pg_build_power_bridges} emsg]} {
            puts stderr "\[ERROR\] power-bridge builder failed: $emsg"
            puts stderr $::errorInfo
        }
        return $rc
    }
}
