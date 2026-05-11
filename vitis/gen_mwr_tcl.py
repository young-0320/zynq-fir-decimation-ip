#!/usr/bin/env python3
"""
gen_mwr_tcl.py: ELF → xsdb mwr Tcl script
Workaround for xsdb JTAG write buffer bug: byte 3 (MSB) of each 32-bit write
is only flushed when the next JTAG command starts. We insert mrd after each mwr
to force flush before the next write.
Usage: python vitis/gen_mwr_tcl.py build/output/fir_decimator_demo.elf build/output/load_elf.tcl
"""
import sys
import struct


def main():
    if len(sys.argv) != 3:
        sys.exit(f"Usage: {sys.argv[0]} <elf> <output.tcl>")

    elf_path, tcl_path = sys.argv[1], sys.argv[2]
    data = open(elf_path, "rb").read()

    assert data[:4] == b"\x7fELF", "Not an ELF file"
    assert data[4] == 1, "Only ELF32 supported"
    assert data[5] == 1, "Only little-endian supported"

    (e_entry,) = struct.unpack_from("<I", data, 24)
    (e_phoff,) = struct.unpack_from("<I", data, 28)
    (e_phentsz,) = struct.unpack_from("<H", data, 42)
    (e_phnum,) = struct.unpack_from("<H", data, 44)

    cmds = []
    n_words = 0
    for i in range(e_phnum):
        base = e_phoff + i * e_phentsz
        p_type, p_foff, _vaddr, p_paddr, p_filesz = struct.unpack_from("<5I", data, base)
        if p_type != 1 or p_filesz == 0:  # PT_LOAD only
            continue
        seg = data[p_foff : p_foff + p_filesz]
        for j in range(0, len(seg), 4):
            chunk = seg[j : j + 4].ljust(4, b"\x00")
            (word,) = struct.unpack_from("<I", chunk)
            addr = p_paddr + j
            cmds.append(f"mwr 0x{addr:08X} 0x{word:08X}")
            cmds.append(f"after 0")
            n_words += 1

    cmds.append(f"rwr pc 0x{e_entry:08X}")

    with open(tcl_path, "w") as f:
        f.write(f"# ELF loader: mwr+mrd per word (xsdb JTAG byte3 flush workaround)\n")
        f.write(f"# Source: {elf_path}\n")
        f.write(f"# {n_words} words\n\n")
        f.write("\n".join(cmds) + "\n")

    print(f"Generated {n_words} mwr+mrd pairs → {tcl_path}")


if __name__ == "__main__":
    main()
