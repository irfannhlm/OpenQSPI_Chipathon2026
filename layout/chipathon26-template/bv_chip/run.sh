#!/usr/bin/env bash
# Assemble A09_BV + A09_BV_padring into a full-chip GDS and verify it, without
# LibreLane: KLayout for GDS assembly + DRC, Magic + Netgen for LVS.
#
# Run inside the project nix-shell, from the template root:
#     cd layout/chipathon26-template
#     nix-shell
#     make clone-pdk            # if gf180mcu/ is missing
#     bv_chip/run.sh            # prep -> assemble -> drc -> extract -> lvs -> summary
#     bv_chip/run.sh <stage>    # prep|assemble|drc|extract|lvs|summary
#     bv_chip/run.sh openklayout   # view the merged GDS
#
# Outputs land in bv_chip/out/.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$(cd "$HERE/.." && pwd)"
cd "$TEMPLATE"

PDK_ROOT="${PDK_ROOT:-$TEMPLATE/gf180mcu}"
PDK="${PDK:-gf180mcuD}"
export PDK_ROOT PDK          # gf180mcuD.magicrc / PDK runners read these from the env
REF="$PDK_ROOT/$PDK/libs.ref"
TECH="$PDK_ROOT/$PDK/libs.tech"
VARIANT="${VARIANT:-D}"          # gf180mcuD: metal_top=11K, 5LM  (run_drc.py --help)

OUT="$HERE/out"
mkdir -p "$OUT"

GDS="$OUT/A09_BV_chip.gds"
EXT_DIR="$OUT/ext"
EXT_SPICE="$OUT/A09_BV_chip.ext.spice"
PADRING_PREP="$HERE/A09_BV_padring.prep.v"

stage="${1:-all}"

prep()     { python3 "$HERE/prep.py"; }

assemble() { klayout -b -r "$HERE/assemble.py"; }

drc() {
  python3 "$TECH/klayout/tech/drc/run_drc.py" \
    --path="$GDS" --variant="$VARIANT" --topcell=A09_BV_chip \
    --run_dir="$OUT/drc" --run_mode=deep
}

extract() {
  rm -rf "$EXT_DIR"; mkdir -p "$EXT_DIR"
  BV_GDS="$GDS" BV_TOP=A09_BV_chip BV_EXT_DIR="$EXT_DIR" BV_EXT_SPICE="$EXT_SPICE" \
    magic -dnull -noconsole -rcfile "$TECH/magic/${PDK}.magicrc" "$HERE/extract.tcl"
}

lvs() {
  mkdir -p "$OUT/lvs"
  prep
  BV_EXT_SPICE="$EXT_SPICE" \
  SCL_SPICE="$REF/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice" \
  IO_SPICE="$REF/gf180mcu_fd_io/spice/gf180mcu_fd_io.spice" \
  WSIO_SPICE="$REF/gf180mcu_fd_io/spice/gf180mcu_ws_io.spice" \
  A09BV_PNL="$TEMPLATE/macros/A09_BV/final/pnl/A09_BV.pnl.v" \
  PADRING_V="$PADRING_PREP" \
  WRAPPER_V="$HERE/A09_BV_chip.v" \
  NETGEN_SETUP="$TECH/netgen/${PDK}_setup.tcl" \
  LVS_RPT="$OUT/lvs/lvs.netgen.rpt" \
    netgen -batch source "$HERE/lvs.tcl"
}

summary() {
  set +e +o pipefail          # this is a report - never let a missing file abort it
  echo
  echo "==================  bv_chip : A09_BV_chip  =================="
  local drclog drcn
  drclog=$(ls -t "$OUT"/drc/*.log 2>/dev/null | head -1 || true)
  drcn=$(cat "$OUT"/drc/*.lyrdb 2>/dev/null | grep -c "<item>" || true)
  if [ -n "${drclog:-}" ] && grep -q "DRC run is clean" "$drclog"; then
    echo "  DRC   : CLEAN  (0 violations)"
  elif [ -n "${drclog:-}" ]; then
    echo "  DRC   : ${drcn:-?} violation(s)   -> $OUT/drc/"
  else
    echo "  DRC   : not run"
  fi
  local rpt res
  rpt="$OUT/lvs/lvs.netgen.rpt"
  if [ -f "$rpt" ]; then
    res=$(grep -E "^Final result:" "$rpt" | tail -1 | sed 's/^Final result:[[:space:]]*//')
    case "$res" in
      *match*) echo "  LVS   : MATCH  ($res)" ;;
      "")      echo "  LVS   : incomplete   -> $rpt" ;;
      *)       echo "  LVS   : MISMATCH  ($res)   -> $rpt" ;;
    esac
  else
    echo "  LVS   : not run"
  fi
  echo "  GDS   : $GDS"
  echo "==========================================================="
}

openklayout() { exec klayout -l "$TECH/klayout/tech/gf180mcu.lyp" "$GDS"; }

case "$stage" in
  prep)      prep ;;
  assemble)  assemble ;;
  drc)       drc; summary ;;
  extract)   extract ;;
  lvs)       lvs; summary ;;
  summary)   summary ;;
  all)       prep; assemble; drc; extract; lvs; summary ;;
  openklayout|klayout|open) openklayout ;;
  openroad|gui)             openroad_gui ;;
  *) echo "usage: $0 [prep|assemble|drc|extract|lvs|summary|all|openklayout|openroad]" >&2; exit 2 ;;
esac
