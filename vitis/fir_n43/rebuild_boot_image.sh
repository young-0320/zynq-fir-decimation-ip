#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  vitis/fir_n43/rebuild_boot_image.sh [--bit PATH] [--boot-out PATH] [--boot-tag TEXT] [--sd-mount PATH]

Rebuild an SD-boot image after C-only application changes.

Tool discovery:
  - Set VITIS_ROOT=/path/to/Xilinx/Vitis/2024.2 when Vitis is not under a common install path.
  - BOOTGEN, TOOLCHAIN_BIN, and NINJA can be set explicitly to override auto-detection.

Default behavior:
  - Reuses the existing Vitis workspace in build/fir_n43/vitis.
  - Uses the first available FIR-DMA bitstream candidate.
  - Generates build/fir_n43/output/BOOT.bin.

Useful debug flow:
  vitis/fir_n43/rebuild_boot_image.sh \
    --bit build/debug/axis_debug/output/bd_fir_dma_axis_debug_wrapper.bit \
    --boot-out build/debug/axis_debug/output/BOOT.bin

Steps:
  1. copy sw/fir_decimator_demo.c into the Vitis app workspace
  2. rebuild fir_decimator_demo.elf with the existing Ninja project
  3. copy fsbl.elf, selected bitstream, and app ELF into the output directory
  4. generate a repo-relative BIF
  5. run bootgen
  6. optionally copy the generated image to PATH/BOOT.bin

It does not rebuild Vivado hardware or regenerate the Vitis platform.
EOF
}

SD_MOUNT=""
USER_BIT_SRC=""
BOOT_OUT_ARG=""
BOOT_TAG="FIR"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --boot-tag)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --boot-tag requires a value" >&2
        exit 2
      fi
      BOOT_TAG="$2"
      shift 2
      ;;
    --sd-mount)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --sd-mount requires a path" >&2
        exit 2
      fi
      SD_MOUNT="$2"
      shift 2
      ;;
    --bit)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --bit requires a path" >&2
        exit 2
      fi
      USER_BIT_SRC="$2"
      shift 2
      ;;
    --boot-out)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --boot-out requires a path" >&2
        exit 2
      fi
      BOOT_OUT_ARG="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

VITIS_ROOT="${VITIS_ROOT:-${XILINX_VITIS:-}}"
if [[ -z "$VITIS_ROOT" ]]; then
  for candidate in \
    "$HOME/Xilinx/Vitis/2024.2" \
    /opt/Xilinx/Vitis/2024.2
  do
    if [[ -d "$candidate" ]]; then
      VITIS_ROOT="$candidate"
      break
    fi
  done
fi

BOOTGEN="${BOOTGEN:-}"
if [[ -z "$BOOTGEN" ]]; then
  if command -v bootgen >/dev/null 2>&1; then
    BOOTGEN="$(command -v bootgen)"
  elif [[ -n "$VITIS_ROOT" ]]; then
    BOOTGEN="$VITIS_ROOT/bin/bootgen"
  fi
fi

TOOLCHAIN_BIN="${TOOLCHAIN_BIN:-}"
if [[ -z "$TOOLCHAIN_BIN" ]]; then
  if [[ -n "$VITIS_ROOT" ]]; then
    TOOLCHAIN_BIN="$VITIS_ROOT/gnu/aarch32/lin/gcc-arm-none-eabi/bin"
  elif command -v arm-none-eabi-gcc >/dev/null 2>&1; then
    TOOLCHAIN_BIN="$(dirname "$(command -v arm-none-eabi-gcc)")"
  fi
fi

NINJA="${NINJA:-}"
if [[ -z "$NINJA" ]]; then
  NINJA_CANDIDATES=(ninja)
  if [[ -n "$VITIS_ROOT" ]]; then
    NINJA_CANDIDATES=(
      "$VITIS_ROOT/tps/lnx64/lopper-1.1.0/env/lib/python3.8/site-packages/ninja/data/bin/ninja"
      "$VITIS_ROOT/tps/lnx64/lopper-1.1.0/env/bin/ninja"
      "${NINJA_CANDIDATES[@]}"
    )
  fi
  for candidate in "${NINJA_CANDIDATES[@]}"; do
    if command -v "$candidate" >/dev/null 2>&1 || [[ -x "$candidate" ]]; then
      NINJA="$candidate"
      break
    fi
  done
fi

APP_SRC="$REPO_ROOT/sw/fir_decimator_demo.c"
VITIS_APP_SRC="$REPO_ROOT/build/fir_n43/vitis/fir_decimator_demo/fir_decimator_demo.c"
APP_BUILD_DIR="$REPO_ROOT/build/fir_n43/vitis/fir_decimator_demo/build"
APP_ELF_WS="$APP_BUILD_DIR/fir_decimator_demo.elf"

FSBL_CANDIDATES=(
  "$REPO_ROOT/build/fir_n43/vitis/fir_decimator_pf/export/fir_decimator_pf/sw/boot/fsbl.elf"
  "$REPO_ROOT/build/fir_n43/vitis/fir_decimator_pf/zynq_fsbl/build/fsbl.elf"
)

BIT_CANDIDATES=(
  "$REPO_ROOT/build/fir_n43/output/bd_fir_dma_wrapper.bit"
  "$REPO_ROOT/build/fir_n43/vivado/fir_decimator_trans_n43.runs/impl_1/bd_fir_dma_wrapper.bit"
  "$REPO_ROOT/build/fir_n43/vitis/fir_decimator_demo/_ide/bitstream/bd_fir_dma_wrapper.bit"
)

DEFAULT_OUT_DIR="$REPO_ROOT/build/fir_n43/output"

if [[ -n "$BOOT_OUT_ARG" ]]; then
  if [[ "$BOOT_OUT_ARG" = /* ]]; then
    OUT_BOOT="$BOOT_OUT_ARG"
  else
    OUT_BOOT="$REPO_ROOT/$BOOT_OUT_ARG"
  fi
  OUT_DIR="$(dirname "$OUT_BOOT")"
else
  OUT_DIR="$DEFAULT_OUT_DIR"
  OUT_BOOT="$OUT_DIR/BOOT.bin"
fi

OUT_FSBL="$OUT_DIR/fsbl.elf"
OUT_APP="$OUT_DIR/fir_decimator_demo.elf"

require_file() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" ]]; then
    echo "ERROR: missing $label: $path" >&2
    exit 1
  fi
}

first_existing() {
  local path
  for path in "$@"; do
    if [[ -f "$path" ]]; then
      printf '%s\n' "$path"
      return 0
    fi
  done
  return 1
}

abs_path() {
  local path="$1"
  if [[ "$path" = /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s\n' "$REPO_ROOT/$path"
  fi
}

copy_if_different() {
  local src="$1"
  local dst="$2"

  if [[ -e "$dst" ]] && [[ "$(realpath "$src")" == "$(realpath "$dst")" ]]; then
    echo "skip copy; source and destination are identical: $dst"
    return 0
  fi

  cp "$src" "$dst"
}

repo_rel() {
  local path="$1"
  realpath --relative-to="$REPO_ROOT" "$path"
}

require_file "$APP_SRC" "application source"
require_file "$VITIS_APP_SRC" "Vitis app source copy"
if [[ ! -d "$APP_BUILD_DIR" ]]; then
  echo "ERROR: missing Vitis app build dir: $APP_BUILD_DIR" >&2
  echo "Run the full Vitis platform/app generation flow before using this C-only rebuild script." >&2
  exit 1
fi
if [[ -z "$NINJA" ]]; then
  echo "ERROR: could not find ninja. Set NINJA=/path/to/ninja." >&2
  exit 1
fi
if [[ -z "$BOOTGEN" ]]; then
  echo "ERROR: could not find bootgen. Source the Xilinx environment or set BOOTGEN=/path/to/bootgen." >&2
  exit 1
fi
if [[ -z "$TOOLCHAIN_BIN" || ! -d "$TOOLCHAIN_BIN" ]]; then
  echo "ERROR: could not find ARM toolchain bin directory. Set TOOLCHAIN_BIN=/path/to/gcc-arm-none-eabi/bin." >&2
  exit 1
fi
require_file "$BOOTGEN" "bootgen"

FSBL_SRC="$(first_existing "${FSBL_CANDIDATES[@]}")" || {
  echo "ERROR: missing fsbl.elf. Checked:" >&2
  printf '  %s\n' "${FSBL_CANDIDATES[@]}" >&2
  exit 1
}

if [[ -n "$USER_BIT_SRC" ]]; then
  BIT_SRC="$(abs_path "$USER_BIT_SRC")"
  require_file "$BIT_SRC" "selected bitstream"
else
  BIT_SRC="$(first_existing "${BIT_CANDIDATES[@]}")" || {
    echo "ERROR: missing bitstream. Checked:" >&2
    printf '  %s\n' "${BIT_CANDIDATES[@]}" >&2
    exit 1
  }
fi

mkdir -p "$OUT_DIR" "$(dirname "$OUT_BOOT")"

OUT_BIT="$OUT_DIR/$(basename "$BIT_SRC")"
OUT_BOOT_BASE="$(basename "$OUT_BOOT")"
if [[ "$OUT_BOOT_BASE" == "BOOT.bin" ]]; then
  OUT_BIF="$OUT_DIR/fir_decimator_demo.bif"
else
  OUT_BIF="$OUT_DIR/${OUT_BOOT_BASE%.bin}.bif"
fi

echo "== C-only SD boot rebuild =="
echo "repo:       $REPO_ROOT"
echo "source:     $APP_SRC"
echo "vitis src:  $VITIS_APP_SRC"
echo "fsbl:       $FSBL_SRC"
echo "bitstream:  $BIT_SRC"
echo "bif:        $OUT_BIF"
echo "output:     $OUT_BOOT"
echo "boot tag:   $BOOT_TAG"
echo ""

cp "$APP_SRC" "$VITIS_APP_SRC"
BOOT_TAG_HEADER="$(dirname "$VITIS_APP_SRC")/boot_tag.h"
cat > "$BOOT_TAG_HEADER" <<EOF
#ifndef BOOT_TAG
#define BOOT_TAG "$BOOT_TAG"
#endif
EOF

PATH="$TOOLCHAIN_BIN:$PATH" "$NINJA" -C "$APP_BUILD_DIR"
require_file "$APP_ELF_WS" "rebuilt app ELF"

copy_if_different "$FSBL_SRC" "$OUT_FSBL"
copy_if_different "$BIT_SRC" "$OUT_BIT"
copy_if_different "$APP_ELF_WS" "$OUT_APP"

cat > "$OUT_BIF" <<EOF
the_ROM_image:
{
    [bootloader]$(repo_rel "$OUT_FSBL")
    $(repo_rel "$OUT_BIT")
    $(repo_rel "$OUT_APP")
}
EOF

(
  cd "$REPO_ROOT"
  "$BOOTGEN" -arch zynq -image "$(repo_rel "$OUT_BIF")" -o "$(repo_rel "$OUT_BOOT")" -w on
)

require_file "$OUT_BOOT" "BOOT image"

echo ""
echo "Generated:"
ls -l "$OUT_FSBL" "$OUT_BIT" "$OUT_APP" "$OUT_BIF" "$OUT_BOOT"

if [[ -n "$SD_MOUNT" ]]; then
  if [[ ! -d "$SD_MOUNT" ]]; then
    echo "ERROR: SD mount directory does not exist: $SD_MOUNT" >&2
    exit 1
  fi
  cp "$OUT_BOOT" "$SD_MOUNT/BOOT.bin"
  sync
  echo ""
  echo "Copied to SD:"
  ls -l "$SD_MOUNT/BOOT.bin"
fi
