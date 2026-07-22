# Nitro P&R 에러 원문 기록과 중단 판정 근거

P&R 시도(2026-07-21, v1 10000ps netlist) 중 발생한 에러의 원문과, 이를 툴 내부
버그로 판정해 중단한 논거를 기록한다. 시도의 시간 순 경과는 `docs/log/47` §4,
결정 요약은 `../oasys/results/sweep_report.md` §6.

## 발생 경과

- PLC1020: Oasys가 생성한 datapath 블럭 36개가 movable이 아니어서 `place_macros`
  자동 배치가 거부됨 → GUI 수동 배치로 진행 (GEMM 수업 방식과 동일).
- SDA101: 수동 배치 후 `run_place_timing`에서 placer 내부 assertion 크래시.
  칩 1.4mm(util 70%) → 1.6mm(util 53%)로 확대·재배치 후 재시도에서도 동일 지점
  재현 (아래 원문의 error2/error3).

## "툴 내부 버그"로 판정한 근거

1. **에러의 종류가 assertion이다.** `internal error 'grCapFrac <= 1' at
   densityboxcontrol.cpp line 245` — 소스 파일·행 번호가 찍힌 내부 불변식 위반이다.
   사용자 입력이 잘못된 경우 툴은 사용자 레벨 에러로 보고하며, 실제로 이번 시도에서
   잘못된 입력이었던 매크로 미배치는 PLC1020이라는 사용자 에러로 구분되어 나왔다.
   assertion 크래시는 툴 내부 상태가 스스로 모순에 빠졌다는 뜻이다.
2. **사용자 파라미터와 무관하게 같은 지점에서 재현된다.** 크래시된 불변식은 밀도
   계산(`grCapFrac`, density box control)인데, 칩 면적을 키워 util을 70%→53%로
   낮춘 뒤에도 같은 파일 같은 행에서 재현됐다. 밀도 조건이 원인이라면 완화 시
   증상이 달라져야 한다 — 입력이 아니라 내부 상태 문제라는 방증이다.
3. **같은 플로우의 대조군이 존재한다.** 같은 서버, 같은 Nitro 빌드(2020.2), 같은
   절차(수업 GEMM 플로우와 diff로 동일성 검증)로 GEMM 디자인은 P&R을 완주했다.
   절차 오류가 아니라 "이 netlist(datapath 블럭 36개 포함)와 이 빌드의 조합"에서
   터지는 문제다.
4. **남은 회피 수단이 사용자 권한 밖이다.** 시도 가능한 레버(칩 면적, utilization,
   수동 배치)는 소진했고, 남은 것은 툴 버전 교체나 벤더 패치인데 학교 서버 공용
   설치라 불가하다.

## 중단이 합리적이었던 이유

Track A의 목적(v1/v2 비교 + 보조 지표)은 합성 결과로 이미 완결됐고, P&R이 더해줄
것은 "post-route에서도 결론 유지" 방어 한 줄이었다. 반면 재시도 비용은 회당 수 시간
+ GUI 수동 배치였다. 기대 기여 대비 비용 초과로 중단하고, 절차와 스크립트
(`tcl/nitro_step0~7.tcl`)는 재개 가능한 상태로 보존했다.

```text
warning PLC2012: The port 'out_sample[0]' is not fixed.
warning PLC2012: The port 'clk' is not fixed.
warning PLC2012: The port 'out_sample[1]' is not fixed.
warning PLC2012: The port 'out_sample[2]' is not fixed.
warning PLC2012: The port 'out_sample[3]' is not fixed.
warning PLC2012: The port 'out_sample[4]' is not fixed.
warning PLC2012: The port 'out_sample[5]' is not fixed.
warning PLC2012: The port 'out_sample[6]' is not fixed.
warning PLC2012: The port 'out_sample[7]' is not fixed.
warning PLC2012: The port 'out_sample[8]' is not fixed.
error PLC1020: Cannot run macro placement on a design without any movable macros. 
error UI150: Command 'place_timing' execution failed: Global placer failed to complete.. 
info UI: 10 (out of 34) 'PLC2012' messages were displayed
error UI26: Script file '/mnt/NewHDD/home/ddl2026/ddl2026_<user>/ddl2026_folder/zynq-fir-decimation-ip/asic/nitro/tcl/nitro_step1b_macros.tcl' execution failed (and stopped) at line 3 (place_macros -partition $TOP_MODULE). 
error2
error SDA101: internal error has occurred 'grCapFrac <= 1.' at /home/devmgr/work/73777_2020.2.R1/dev/src/pldb/engine/densityboxcontrol.cpp line 245 
error UI150: Command 'place_timing' execution failed. 
error UI26: Script file '/mnt/NewHDD/home/ddl2026/ddl2026_<user>/ddl2026_folder/zynq-fir-decimation-ip/asic/nitro/tcl/nitro_step4.tcl' execution failed (and stopped) at line 2 (run_place_timing -effort high). 
error3
error SDA101: internal error has occurred 'grCapFrac <= 1.' at /home/devmgr/work/73777_2020.2.R1/dev/src/pldb/engine/densityboxcontrol.cpp line 245 
error UI150: Command 'place_timing' execution failed. 
error UI26: Script file '/mnt/NewHDD/home/ddl2026/ddl2026_<user>/ddl2026_folder/zynq-fir-decimation-ip/asic/nitro/tcl/nitro_step4.tcl' execution failed (and stopped) at line 2 (run_place_timing -effort high).
```
