#!/usr/bin/env python3
"""
download_bringup.py: bringup_demo.elf를 Zybo Z7-20에 로드 후 실행
Usage: python vitis/legacy/bringup_demo/download_bringup.py  (repo root에서 실행)

pexpect로 xsdb 인터랙티브 모드를 구동해 각 mwr마다 REPL barrier를 재현.
(sourced 모드 + dow 모두 byte3 MSB 오염 버그가 있어 사용 불가)
"""
import os
import struct
import sys
import time
import pexpect

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BIT      = f"{REPO_ROOT}/build/fir_n43/output/bd_fir_dma_wrapper.bit"
ELF      = f"{REPO_ROOT}/build/legacy/bringup/fir_dma_bringup_demo/build/fir_dma_bringup_demo.elf"
PS7_INIT = f"{REPO_ROOT}/build/fir_n43/vivado/fir_decimator_trans_n43.gen/sources_1/bd/bd_fir_dma/ip/bd_fir_dma_processing_system7_0_0/ps7_init.tcl"


def read_elf(path):
    data = open(path, "rb").read()
    assert data[:4] == b"\x7fELF", "ELF 매직 없음"
    e_entry,   = struct.unpack_from("<I", data, 24)
    e_phoff,   = struct.unpack_from("<I", data, 28)
    e_phentsz, = struct.unpack_from("<H", data, 42)
    e_phnum,   = struct.unpack_from("<H", data, 44)
    words = []
    for i in range(e_phnum):
        base = e_phoff + i * e_phentsz
        p_type, p_foff, _vaddr, p_paddr, p_filesz = struct.unpack_from("<5I", data, base)
        if p_type != 1 or p_filesz == 0:
            continue
        seg = data[p_foff:p_foff + p_filesz]
        for j in range(0, len(seg), 4):
            chunk = seg[j:j + 4].ljust(4, b"\x00")
            word, = struct.unpack_from("<I", chunk)
            words.append((p_paddr + j, word))
    return words, e_entry


def cmd(xsdb, command, show=True, timeout=30):
    if show:
        print(f">> {command}")
    xsdb.sendline(command)
    xsdb.expect('xsdb%', timeout=timeout)
    last_before = xsdb.before
    # readline wrap으로 인한 잔여 xsdb% 모두 소진
    while True:
        try:
            xsdb.expect('xsdb%', timeout=0.05)
            last_before = xsdb.before
        except pexpect.TIMEOUT:
            break
    out = last_before.strip()
    if show and out:
        print(out)
    return out


def main():
    for path, name in [(BIT, "비트스트림"), (ELF, "ELF"), (PS7_INIT, "ps7_init.tcl")]:
        if not os.path.exists(path):
            sys.exit(f"[오류] {name} 없음: {path}")

    words, e_entry = read_elf(ELF)
    total = len(words)
    print(f"ELF: {total} words, entry=0x{e_entry:08X}")

    # dimensions=(24, 1000): PTY 폭 확장으로 긴 source 경로의 readline wrap 방지
    xsdb = pexpect.spawn('xsdb', encoding='utf-8', timeout=60, dimensions=(24, 1000))
    xsdb.searchwindowsize = 500
    xsdb.expect('xsdb%')
    print("xsdb 프롬프트 확인")

    cmd(xsdb, "connect")
    cmd(xsdb, 'targets -set -filter {name =~ "APU*"}')
    cmd(xsdb, f"fpga {BIT}", timeout=120)
    print("비트스트림 로드 완료, 안정화 대기...")
    time.sleep(1)
    try:
        while xsdb.expect([r'.+', pexpect.TIMEOUT], timeout=0.5) == 0:
            pass
    except Exception:
        pass

    cmd(xsdb, 'targets -set -filter {name =~ "*A9*#0"}')
    cmd(xsdb, "rst -processor -clear-registers")
    cmd(xsdb, f"source {PS7_INIT}")
    cmd(xsdb, "ps7_init")
    cmd(xsdb, "ps7_post_config")
    cmd(xsdb, "after 500")
    cmd(xsdb, "mwr 0xF8F0277C 0x0000FFFF")  # L2 캐시 무효화
    cmd(xsdb, "after 200")

    # DDR 접근 점검 (-force: 캐시/파이프라인 우회)
    print("\n[DDR 점검]")
    cmd(xsdb, "mwr -force 0x100000 0xDEADBEEF")
    out = cmd(xsdb, "mrd -force 0x100000 1")
    if "DEADBEEF" not in out.upper():
        sys.exit(f"[치명적] DDR 접근 실패: '{out}'\n→ 전원 재공급 후 재시도")
    print("[OK] DDR 접근 정상")

    # ELF 로딩
    print(f"\n[ELF 로딩] {total} words...")
    t_start = time.time()
    for i, (addr, word) in enumerate(words):
        while True:
            try:
                xsdb.sendline(f"mwr -force 0x{addr:08X} 0x{word:08X}")
                xsdb.expect('xsdb%', timeout=30)
                out = xsdb.before.strip()
                xsdb.buffer = ''
                if i < 8 or out:
                    print(f"  [{i}] 0x{addr:08X} = 0x{word:08X}  {f'← {out}' if out else ''}", flush=True)
                break
            except pexpect.TIMEOUT:
                print(f"  [{i}] timeout, 재시도...", flush=True)
            except pexpect.EOF:
                sys.exit("xsdb 종료")

        if (i + 1) % 200 == 0 or (i + 1) == total:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed
            eta = (total - i - 1) / rate if rate > 0 else 0
            print(f"  {i+1}/{total} ({100*(i+1)//total}%)  {rate:.0f} w/s  ETA {eta:.0f}s", flush=True)

    # 엔트리 포인트 설정
    cmd(xsdb, f"rwr pc 0x{e_entry:08X}")

    # 로딩 검증: ELF의 첫 워드와 mrd 비교
    print("\n[검증] 0x100000 첫 4워드 확인...")
    out = cmd(xsdb, "mrd -force 0x100000 4")
    first_words = [w for a, w in words[:4]]
    ok = all(f"{w:08X}".upper() in out.upper() for w in first_words)
    if ok:
        print("[OK] 벡터 테이블 정상 — byte3 flush 성공")
    else:
        print(f"[FAIL] 불일치!\n  예상: {[f'{w:08X}' for w in first_words]}\n  실제: {out}")
        sys.exit("ELF 로딩 실패 — 전원 재공급 후 재시도")

    cmd(xsdb, "con")
    xsdb.close()

    print("\n=== 완료 ===")
    print("Serial Monitor에서 'BRINGUP OK' + 'ALIVE N' 확인")


if __name__ == "__main__":
    main()
