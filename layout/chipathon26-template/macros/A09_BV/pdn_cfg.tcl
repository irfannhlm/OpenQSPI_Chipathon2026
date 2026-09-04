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
#   VSS :  full-height Metal2 from the die edge straight onto its own ring leg
#          (same layer + same net, nothing in between -> no via)
#   VDD :  Metal2 landing -> Via2 stack(s) -> Metal3 hop (over the VSS leg)
#                         -> Via2 stack(s) -> onto the VDD ring leg
#
# Each VDD bridge end gets _PG_VIA_STACKS square Via2 stacks tiled across the
# bridge width (0 = auto: as many as fit, keeping _PG_VIA_STACK_GAP_UM between
# stacks and _PG_VIA_STACK_EDGE_UM from the bridge edges). Several square stacks
# share current more evenly than one tall array and are kinder to EM and yield
# -- see _pg_stack_ys.
#
# The VSS bridge uses the full pin-stub height. The VDD bridge width is set by
# _PG_VDD_BRIDGE_W_UM (um, centred on the pin); 0 means "full pin-stub height
# too" -- only safe when the PDN straps are placed clear of the pin Y positions,
# since the VDD Metal3 hop / Via2 stacks run past the VSS leg and could collide
# with VSS strap-to-ring vias. Either way, after building the VDD bridges the
# script HARD-ERRORS if any VDD bridge shape overlaps, or sits within same-layer
# min-spacing of, a VSS shape (_pg_assert_no_vss_conflict). Different layers
# crossing (the Metal3 hop over the Metal2 VSS leg) are fine and ignored.
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

set ::_PG_VDD_BRIDGE_W_UM  0  ;# VDD bridge width (Y, um); 0 = full pin-stub
                               ;#   height (needs PDN straps clear of the pin Ys)
set ::_PG_M2_LAND_UM      3.0   ;# VDD Metal2 landing reach from the die edge
set ::_PG_M3_EDGE_UM      0.20  ;# Metal3 hop start offset from the die edge
set ::_PG_VIA_ROWS        4     ;# Via2 cut rows per stack  (Y)
set ::_PG_VIA_COLS        4     ;# Via2 cut cols per stack  (X)
set ::_PG_VIA_STACKS       0    ;# via stacks per bridge end, tiled across the
                               ;#   width; 0 = auto (as many as fit)
set ::_PG_VIA_STACK_GAP_UM 1.0  ;# solid-metal gap between adjacent stacks
set ::_PG_VIA_STACK_EDGE_UM 0.3 ;# inset of the outer stacks from the bridge edge
set ::_PG_STRICT_VSS_CLEARANCE 0 ;# 1 = VDD/VSS gap below min-spacing is fatal;
                                 ;#     0 = warn only (a true short still errors)

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
    set fh [open [_pg_template_path] r]
    set tdbu 1000
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
    if {[$block findVia $name] ne "NULL"} {
        error "power-bridge: via '$name' already exists (builder re-run on a dirty DB?)"
    }
    set v [odb::dbVia_create $block $name]
    $v setViaGenerateRule [[$block getTech] findViaGenerateRule "Via2_GEN_HH"]
    set p  [$v getViaParams]
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

proc _pg_stack_ys {lo hi n sh gap edge} {
    # -> via-stack Y centres tiled across [lo,hi]: >= $gap of solid metal between
    # adjacent stacks, >= $edge from the bridge Y edges. $sh = stack Y half-
    # height. $n<=0 -> as many as fit; else clamped to that. n==1 -> centred.
    #   fit test:  n*2sh + (n-1)*gap + 2*edge <= span
    set span [expr {$hi - $lo}]
    set nmax [expr {max(1, int(($span - 2 * $edge + $gap) / double(2 * $sh + $gap)))}]
    set n    [expr {$n <= 0 ? $nmax : ($n < $nmax ? $n : $nmax)}]
    set a [expr {$lo + $sh + $edge}]
    set b [expr {$hi - $sh - $edge}]
    if {$n <= 1 || $b <= $a} { return [list [expr {($lo + $hi) / 2}]] }
    set ys {}
    for {set i 0} {$i < $n} {incr i} {
        lappend ys [expr {int($a + ($b - $a) * $i / double($n - 1))}]
    }
    return $ys
}

proc _pg_layer_spacing {tech lname fallback} {
    set ly [$tech findLayer $lname]
    if {$ly eq "NULL"} { return $fallback }
    set s [$ly getSpacing]
    return [expr {$s > 0 ? $s : $fallback}]
}

proc _pg_assert_no_vss_conflict {block vss shapes} {
    # shapes : list of {layerName x1 y1 x2 y2} just added to the VDD net.
    #   overlap               -> SHORT, always fatal
    #   0 < gap < min-spacing -> clearance, fatal iff _PG_STRICT_VSS_CLEARANCE
    # A plain VSS metal box only matters against same-layer VDD metal (the
    # Metal3 hop crossing the Metal2 VSS leg is a different-layer crossing, fine).
    # A VSS *via* box (ring<->strap ties: via2_3 / via3_4 ...) spans layers, so
    # it is checked against every VDD bridge shape.
    set tech   [$block getTech]
    set def    [expr {round(0.3 * [$block getDbUnitsPerMicron])}]
    set strict [expr {[info exists ::_PG_STRICT_VSS_CLEARANCE] ? $::_PG_STRICT_VSS_CLEARANCE : 1}]
    array set spc {}
    foreach shp $shapes {
        set la [lindex $shp 0]
        if {![info exists spc($la)]} { set spc($la) [_pg_layer_spacing $tech $la $def] }
    }
    set shorts {}
    set clears {}
    foreach sw [$vss getSWires] {
        foreach box [$sw getWires] {
            set bvia [$box isVia]
            set blyr [expr {$bvia ? "" : [[$box getTechLayer] getName]}]
            set bx1 [$box xMin] ; set by1 [$box yMin]
            set bx2 [$box xMax] ; set by2 [$box yMax]
            foreach shp $shapes {
                lassign $shp la x1 y1 x2 y2
                if {!$bvia && $blyr ne $la} { continue }
                set s $spc($la)
                set gx [expr {max($x1 - $bx2, $bx1 - $x2, 0)}]
                set gy [expr {max($y1 - $by2, $by1 - $y2, 0)}]
                if {$gx >= $s || $gy >= $s} { continue }
                set src [expr {$bvia ? "via" : $blyr}]
                set desc [format {%-6s vs VSS-%-6s  VDD(%d %d %d %d) VSS(%d %d %d %d) gap=(%d,%d) min=%d} \
                    $la $src $x1 $y1 $x2 $y2 $bx1 $by1 $bx2 $by2 $gx $gy $s]
                if {$gx == 0 && $gy == 0} {
                    lappend shorts "  SHORT      $desc"
                } else {
                    lappend clears "  clearance  $desc"
                }
            }
        }
    }
    set shorts [lsort -unique $shorts]
    set clears [lsort -unique $clears]
    set hint "  -> widen the VSS/VDD ring spacing, or reduce _PG_VDD_BRIDGE_W_UM / _PG_M2_LAND_UM / _PG_VIA_ROWS / _PG_VIA_COLS"
    if {[llength $clears] && !$strict} {
        puts stderr "\[WARNING\] power-bridge: [llength $clears] VDD shape(s) within VSS min-spacing (real DRC will judge; set _PG_STRICT_VSS_CLEARANCE 1 to make fatal):\n[join $clears \n]\n$hint"
        set clears {}
    }
    set all [concat $shorts $clears]
    if {[llength $all]} {
        error "power-bridge: VDD bridge conflicts with VSS geometry ([llength $all]):\n[join $all \n]\n$hint"
    }
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
    set bw    [expr {int($::_PG_VDD_BRIDGE_W_UM * $dbu)}]
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

    # ---- VSS: full-height Metal2, die edge -> straight onto its own ring leg ----
    lassign [_pg_template_pin_rows VSS] tdbu rows
    if {[llength $rows] == 0} { error "power-bridge: no VSS Metal2 stubs in template" }
    set sc [expr {double($dbu) / $tdbu}]
    set sw [odb::dbSWire_create $vss "ROUTED"]
    foreach r $rows {
        lassign $r y1 y2 x2
        odb::dbSBox_create $sw $m2 0 [expr {int($y1 * $sc)}] \
            $vssR [expr {int($y2 * $sc)}] "STRIPE"
    }
    puts "\[INFO\] power-bridge: VSS  [llength $rows] Metal2 bridges (full stub height)"

    # ---- VDD: Metal2 landing -> Via2 col -> Metal3 hop -> Via2 col -> ring leg ----
    lassign [_pg_template_pin_rows VDD] tdbu rows
    if {[llength $rows] == 0} { error "power-bridge: no VDD Metal2 stubs in template" }
    set sc  [expr {double($dbu) / $tdbu}]
    set sw  [odb::dbSWire_create $vdd "ROUTED"]
    set xcw [expr {$landx / 2}]                  ;# west via stacks (in the landing)
    set xce [expr {($vddL + $vddR) / 2}]         ;# east via stacks (centre of VDD leg)
    set vb  [$colv getBBox]
    set vx1 [$vb xMin] ; set vy1 [$vb yMin] ; set vx2 [$vb xMax] ; set vy2 [$vb yMax]
    set sh   [expr {($vy2 - $vy1) / 2}]          ;# stack Y half-height
    set gap  [expr {int($::_PG_VIA_STACK_GAP_UM  * $dbu)}]
    set edge [expr {int($::_PG_VIA_STACK_EDGE_UM * $dbu)}]
    set nv 0
    set warned_h 0
    set nstk_last 0
    set shapes {}
    foreach r $rows {
        lassign $r y1 y2 x2
        set cy [expr {int(($y1 + $y2) * 0.5 * $sc)}]
        if {$bw <= 0} {                              ;# 0 -> full pin-stub height
            set lo [expr {int($y1 * $sc)}]
            set hi [expr {int($y2 * $sc)}]
        } else {
            set lo [expr {$cy - $bw / 2}]
            set hi [expr {$cy + $bw / 2}]
        }
        odb::dbSBox_create $sw $m2 0     $lo $landx $hi "STRIPE"   ;# landing
        odb::dbSBox_create $sw $m3 $m3x0 $lo $vddR  $hi "STRIPE"   ;# hop over the VSS leg
        lappend shapes [list Metal2 0 $lo $landx $hi] [list Metal3 $m3x0 $lo $vddR $hi]

        if {!$warned_h && 2 * $sh > $hi - $lo} {
            puts stderr "\[WARNING\] power-bridge: Via2 stack ([format %.2f [expr {2.0*$sh/$dbu}]]um) is taller than the VDD bridge ([format %.2f [expr {($hi-$lo)/double($dbu)}]]um) -> 1 stack, may overhang; lower _PG_VIA_ROWS or raise _PG_VDD_BRIDGE_W_UM"
            set warned_h 1
        }
        set ys [_pg_stack_ys $lo $hi $::_PG_VIA_STACKS $sh $gap $edge]
        set nstk_last [llength $ys]
        foreach syc $ys {
            odb::dbSBox_create $sw $colv $xcw $syc "STRIPE"       ;# pin-side stack
            odb::dbSBox_create $sw $colv $xce $syc "STRIPE"       ;# ring-leg stack
            incr nv 2
            lappend shapes \
                [list Via2 [expr {$xcw+$vx1}] [expr {$syc+$vy1}] [expr {$xcw+$vx2}] [expr {$syc+$vy2}]] \
                [list Via2 [expr {$xce+$vx1}] [expr {$syc+$vy1}] [expr {$xce+$vx2}] [expr {$syc+$vy2}]]
        }
    }
    puts "\[INFO\] power-bridge: VDD  [llength $rows] bridges ([expr {$bw <= 0 ? {full stub} : "${::_PG_VDD_BRIDGE_W_UM}um"}] wide), $nstk_last stacks/end x2 ends, ${::_PG_VIA_ROWS}x${::_PG_VIA_COLS} cuts each, $nv total"

    _pg_assert_no_vss_conflict $block $vss $shapes
}

# Install the post-pdngen hook (idempotent). A failure in the builder --
# including a detected VDD/VSS conflict -- is re-raised so GeneratePDN fails and
# the flow stops, rather than silently continuing with a bad/missing bridge.
if {[info commands pdngen] ne "" && [info commands _pg_pdngen_real] eq ""} {
    rename pdngen _pg_pdngen_real
    proc pdngen {args} {
        set rc [uplevel 1 [list _pg_pdngen_real {*}$args]]
        if {[catch {_pg_build_power_bridges} emsg]} {
            puts stderr "\[ERROR\] power-bridge: $emsg"
            puts stderr $::errorInfo
            return -code error "power-bridge builder failed (see above): $emsg"
        }
        return $rc
    }
}
