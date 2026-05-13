#!/usr/bin/env python3
"""
download_and_run.py: pexpect로 xsdb 인터랙티브 모드 구동
workaround: sourced 모드에서 JTAG byte3가 flush되지 않는 버그 회피.
각 mwr마다 xsdb% 프롬프트를 기다려 REPL barrier를 재현한다.
Usage: python vitis/download_and_run.py  (repo root에서 실행)
"""
import os
import struct
import sys
import time
import pexpect

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIT      = f"{REPO_ROOT}/build/vivado/fir_decimator_trans_n43.runs/impl_1/bd_fir_dma_wrapper.bit"
ELF      = f"{REPO_ROOT}/build/output/fir_decimator_demo.elf"
PS7_INIT = f"{REPO_ROOT}/build/vivado/fir_decimator_trans_n43.gen/sources_1/bd/bd_fir_dma/ip/bd_fir_dma_processing_system7_0_0/ps7_init.tcl"


def read_elf(path):
    data = open(path, "rb").read()
    assert data[:4] == b"\x7fELF"
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
    # 긴 source 경로가 readline에서 줄바꿈되며 중간에 'xsdb%'가 여러 번 출력됨.
    # 남은 xsdb% 모두 소진하여 다음 명령이 잘못된 프롬프트와 동기화되지 않게 함.
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
    if not os.path.exists(ELF):
        sys.exit(f"Error: ELF 없음: {ELF}")

    words, e_entry = read_elf(ELF)
    total = len(words)
    print(f"ELF 로드: {total} words, entry=0x{e_entry:08X}")

    # dimensions=(24, 1000): PTY 폭을 넓혀 긴 명령(특히 source ps7_init.tcl)이
    # 화면 줄바꿈되며 readline이 \rxsdb%를 중간에 다시 그리는 것을 막음
    xsdb = pexpect.spawn('xsdb', encoding='utf-8', timeout=60, dimensions=(24, 1000))
    xsdb.searchwindowsize = 500
    xsdb.expect('xsdb%')
    print("xsdb 프롬프트 확인")

    cmd(xsdb, "connect")
    cmd(xsdb, 'targets -set -filter {name =~ "APU*"}')
    cmd(xsdb, f"fpga {BIT}", timeout=120)
    print("비트스트림 로드 완료, 버퍼 정리 중...")
    time.sleep(1) # 하드웨어 안정화 대기
    try:
        # 버퍼가 완전히 빌 때까지 0.5초 단위로 긁어냄
        while xsdb.expect([r'.+', pexpect.TIMEOUT], timeout=0.5) == 0:
            pass
    except:
        pass

    cmd(xsdb, 'targets -set -filter {name =~ "*A9*#0"}')
    cmd(xsdb, "rst -processor -clear-registers")
    cmd(xsdb, f"source {PS7_INIT}")
    cmd(xsdb, "ps7_init")
    cmd(xsdb, "ps7_post_config")
    cmd(xsdb, "after 500") # 안정화를 위해 대기 시간 상향
    cmd(xsdb, "mwr 0xF8F0277C 0x0000FFFF")  # L2 캐시 무효화
    cmd(xsdb, "after 200")

    # DDR 사전 점검 (pexpect cmd()의 mrd 파싱이 불안정하므로 실패해도 계속 진행)
    print("\n[DDR 점검] 테스트 패턴 쓰기/읽기...")
    xsdb.sendline("mwr -force 0x100000 0xDEADBEEF")
    xsdb.expect('xsdb%', timeout=10)
    xsdb.sendline("mrd -force 0x100000 1")
    xsdb.expect('xsdb%', timeout=10)
    out = xsdb.before.strip()
    if "DEADBEEF" not in out.upper():
        print(f"[경고] DDR sanity check 불확실 (mrd 결과: '{out}') — 계속 진행")
    else:
        print("[OK] DDR 접근 정상")

    print(f"\nELF 로딩 중... ({total} words, 각 mwr마다 REPL barrier)")
    t_start = time.time()

    for i, (addr, word) in enumerate(words):
        while True:
            try:
                xsdb.sendline(f"mwr -force 0x{addr:08X} 0x{word:08X}")
                xsdb.expect('xsdb%', timeout=30)
                out = xsdb.before.strip()
                xsdb.buffer = ''  # 누적 버퍼 초기화
                if i < 8 or out:  # 처음 8개 + 에러 출력 감지
                    print(f"  [word {i}] mwr 0x{addr:08X} 0x{word:08X} → '{out}'", flush=True)
                break
            except pexpect.TIMEOUT:
                print(f"\n[{i+1}] timeout, 재시도...", flush=True)
            except pexpect.EOF:
                sys.exit("xsdb 프로세스 종료")

        if (i + 1) % 100 == 0 or (i + 1) == total:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed
            eta = (total - i - 1) / rate if rate > 0 else 0
            print(f"  {i+1}/{total} ({100*(i+1)//total}%)  {rate:.0f} words/s  ETA {eta:.0f}s",
                  flush=True)

    cmd(xsdb, f"rwr pc 0x{e_entry:08X}")

    # 벡터 테이블 검증 (cmd() 대신 직접 sendline/expect — cmd() 내부 while 루프가
    # mwr 후 남은 xsdb%를 소진하며 mrd 출력을 빈 문자열로 만드는 버그 회피)
    print("\n[검증] 0x100000 첫 4워드 확인...")
    xsdb.sendline("mrd -force 0x100000 4")
    xsdb.expect('xsdb%', timeout=10)
    out = xsdb.before.strip()
    expected = {0x100000: 0xEA000031, 0x100004: 0xEA00000D,
                0x100008: 0xEA000013, 0x10000C: 0xEA000023}
    ok = all(f"{v:08X}".upper() in out.upper() for v in expected.values())
    if ok:
        print("[OK] 벡터 테이블 정상 — byte3 flush 성공")
    else:
        print(f"[FAIL] byte3 불일치!\n  예상: {[f'{v:08X}' for v in expected.values()]}\n  실제: {out}")
        sys.exit("ELF 로딩 실패 — 전원 재공급 후 재시도")

    cmd(xsdb, "con")
    xsdb.close()

    print("\n=== 다운로드 완료 ===")
    print("DONE LED 확인 후: python test_uart.py")


if __name__ == "__main__":
    main()
