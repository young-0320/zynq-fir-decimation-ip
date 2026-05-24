#!/usr/bin/env python3
"""Build the Vitis platform/app from the canonical XSA.

Usage:
  vitis -s vitis/fir_n43/build_fir_decimator_demo.py

Run from the repository root after `vivado/fir_n43/build_bd_fir_dma.tcl` has produced
`build/fir_n43/output/bd_fir_dma_wrapper.xsa`.
"""

import glob
import os
import shutil
import sys

import vitis


REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
XSA = os.path.join(REPO_ROOT, "build", "fir_n43", "output", "bd_fir_dma_wrapper.xsa")
WORKSPACE = os.path.join(REPO_ROOT, "build", "fir_n43", "vitis")
OUT_DIR = os.path.join(REPO_ROOT, "build", "fir_n43", "output")
SRC = os.path.join(REPO_ROOT, "sw", "fir_decimator_demo.c")

PLATFORM_NAME = "fir_decimator_pf"
APP_NAME = "fir_decimator_demo"
DOMAIN_NAME = "standalone_ps7_cortexa9_0"
CPU_NAME = "ps7_cortexa9_0"


def require_file(path, label):
    if not os.path.isfile(path):
        sys.exit(f"ERROR: missing {label}: {path}")


def first_existing(paths):
    for path in paths:
        if os.path.isfile(path):
            return path
    return None


def copy_required(src, dst, label):
    require_file(src, label)
    shutil.copy2(src, dst)
    print(f"{label}: {dst}")


def write_bif():
    bif = os.path.join(OUT_DIR, "fir_decimator_demo.bif")
    with open(bif, "w", encoding="utf-8") as f:
        f.write("the_ROM_image:\n")
        f.write("{\n")
        f.write("    [bootloader]build/fir_n43/output/fsbl.elf\n")
        f.write("    build/fir_n43/output/bd_fir_dma_wrapper.bit\n")
        f.write("    build/fir_n43/output/fir_decimator_demo.elf\n")
        f.write("}\n")
    print(f"BIF: {bif}")


def main():
    require_file(XSA, "XSA")
    require_file(SRC, "application source")

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(WORKSPACE, exist_ok=True)

    client = vitis.create_client()
    try:
        client.update_workspace(WORKSPACE)

        platform = client.create_platform_component(
            name=PLATFORM_NAME,
            hw_design=XSA,
            os="standalone",
            cpu=CPU_NAME,
            domain_name=DOMAIN_NAME,
        )
        platform.build()

        xpfm = os.path.join(
            WORKSPACE,
            PLATFORM_NAME,
            "export",
            PLATFORM_NAME,
            f"{PLATFORM_NAME}.xpfm",
        )
        require_file(xpfm, "platform xpfm")

        app = client.create_app_component(
            name=APP_NAME,
            platform=xpfm,
            domain=DOMAIN_NAME,
            template="empty_application",
        )
        app.import_files(from_loc=os.path.dirname(SRC), files=[os.path.basename(SRC)])
        app.set_app_config(key="USER_LINK_LIBRARIES", values=["m"])
        app.build()
    finally:
        vitis.dispose()

    app_elf = first_existing(
        [
            os.path.join(WORKSPACE, APP_NAME, "build", f"{APP_NAME}.elf"),
            *glob.glob(os.path.join(WORKSPACE, APP_NAME, "*", f"{APP_NAME}.elf")),
        ]
    )
    fsbl_elf = first_existing(
        [
            os.path.join(WORKSPACE, PLATFORM_NAME, "export", PLATFORM_NAME, "sw", "boot", "fsbl.elf"),
            os.path.join(WORKSPACE, PLATFORM_NAME, "zynq_fsbl", "build", "fsbl.elf"),
            *glob.glob(os.path.join(WORKSPACE, PLATFORM_NAME, "**", "fsbl.elf"), recursive=True),
        ]
    )

    if app_elf is None:
        sys.exit(f"ERROR: app ELF not found under {os.path.join(WORKSPACE, APP_NAME)}")
    if fsbl_elf is None:
        sys.exit(f"ERROR: fsbl.elf not found under {os.path.join(WORKSPACE, PLATFORM_NAME)}")

    copy_required(fsbl_elf, os.path.join(OUT_DIR, "fsbl.elf"), "FSBL")
    copy_required(app_elf, os.path.join(OUT_DIR, f"{APP_NAME}.elf"), "App ELF")
    write_bif()

    print("")
    print("=== Vitis build complete ===")
    print(f"Workspace: {WORKSPACE}")
    print(f"Next: bootgen -arch zynq -image build/fir_n43/output/fir_decimator_demo.bif -o build/fir_n43/output/BOOT.bin -w on")


if __name__ == "__main__":
    main()
