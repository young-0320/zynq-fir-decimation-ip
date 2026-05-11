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
PS7_INIT = f"{REPO_ROOT}/build/vitis/fir_decimator_demo/_ide/psinit/ps7_init.tcl"


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
    # 1. 버퍼 청소: 이전 명령어의 잔재가 남아있지 않도록 비움
    while True:
        try:
            xsdb.expect(r'.+', timeout=0.01)
        except (pexpect.TIMEOUT, pexpect.EOF):
            break

    if show:
        print(f">> {command}")

    # 2. 명령어 전송
    xsdb.sendline(command)

    # 3. 핵심 수정: 명령어가 '에코'되어 돌아올 때까지 먼저 기다림
    # xsdb는 우리가 보낸 문장을 그대로 다시 출력합니다. 이걸 먼저 소화시켜야 합니다.
    try:
        xsdb.expect_exact(command.strip(), timeout=timeout)
    except pexpect.TIMEOUT:
        pass # 에코가 안 올 경우를 대비해 넘어가지만, 보통은 여기서 걸러집니다.

    # 4. 이제 진짜 결과값과 다음 프롬프트를 기다림
    xsdb.expect('xsdb%', timeout=timeout)
    
    # 5. '에코'와 '프롬프트' 사이의 알맹이만 추출
    out = xsdb.before.strip()

    if show and out:
        print(out)
    return out

def main():
    if not os.path.exists(ELF):
        sys.exit(f"Error: ELF 없음: {ELF}")

    words, e_entry = read_elf(ELF)
    total = len(words)
    print(f"ELF 로드: {total} words, entry=0x{e_entry:08X}")

    xsdb = pexpect.spawn('xsdb', encoding='utf-8', timeout=60)
    xsdb.searchwindowsize = 500  # 전체 buffer 대신 최근 500자만 검색 → 누적 방지
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

    # DDR 사전 점검: 쓰기/읽기 왕복으로 DDR 접근 확인
    print("\n[DDR 점검] 테스트 패턴 쓰기/읽기...")
    cmd(xsdb, "mwr 0x100000 0xDEADBEEF")
    out = cmd(xsdb, "mrd 0x100000 1")
    if "DEADBEEF" not in out.upper():
        sys.exit(
            f"[치명적 오류] DDR 접근 실패! mrd 결과: '{out}'\n"
            "→ 전원 재공급(power cycle) 후 재시도하세요."
        )
    print("[OK] DDR 접근 정상")

    print(f"\nELF 로딩 중... ({total} words, 각 mwr마다 REPL barrier)")
    t_start = time.time()

    for i, (addr, word) in enumerate(words):
        while True:
            try:
                xsdb.sendline(f"mwr 0x{addr:08X} 0x{word:08X}")
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

    # 벡터 테이블 검증
    print("\n[검증] 0x100000 첫 4워드 확인...")
    out = cmd(xsdb, "mrd 0x100000 4")
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
