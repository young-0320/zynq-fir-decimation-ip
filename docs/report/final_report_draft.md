# 최종보고서 내용 초안 — Zynq AXI FIR Decimation IP

> 학교 양식에 부어넣기 위한 **내용 초안** (2026-07-21 작성, 에이전트).
> `[TrackB]` 표시는 수요일 전력 실측 후 채움. 수치는 전부 리포 문서에서 검증된 값.

---

## 1. 프로젝트 개요

- 목표: **N=43 half-band FIR + 2:1 decimation IP**를 설계하고, Zynq-7020(Zybo Z7-20)
  에서 PS–PL DMA 연동 실시간 데모까지 end-to-end로 검증한다.
- 신호 사양: 입력 100MS/s(16-bit), 출력 50MS/s. 통과대역 0~20MHz, Nyquist-edge
  25MHz에서 −6dB, 저지대역 alias 억제.
- 최종 상태: SD boot 기반 실시간 데모 경로 통과, 정량 스펙 검증 완료, 보드 실측
  완료(v1@115MHz / v2@145MHz), 보조 지표(ASIC·전력·CPU 비교) 확보.

## 2. 설계

### 2.1 FIR 코어 (transposed form)

- 구조: transposed direct form, 계수 Q1.15 (ties-away-from-zero 반올림), 내부 누산
  z[k] 48-bit(Q2.30), 출력 반올림 1회 + 포화 1회.
- **v1** (3-stage): Stage1 곱셈→prod_reg / Stage2 누산 z[k] 갱신 + round 동시 계산 /
  Stage3 포화→출력. FPGA 자원: DSP48 16개, 코어 단독 LUT 1792 / FF 2113.
- **v2** (4-stage): 120MHz 타이밍 실패(WNS −0.783ns)의 크리티컬 패스 분석(log 39)
  결과, 병목 = 누산 add와 라운딩이 한 사이클에 겹친 `z_reg[1]→round_reg` 경로
  (CARRY4 캐리 체인). 라운딩을 별도 스테이지로 분리(레지스터 참조 방식)해 해결.
  Fmax 116 → 146MHz (+26%).

### 2.2 시스템 통합

- AXI-Stream 래퍼 + AXI DMA로 PS–PL 연동, bare-metal C 펌웨어(UART 제어) + SD BOOT.
- PC Python 도구: 벡터 생성/골든 모델/FFT 시각화/정량 판정 자동화.

## 3. 검증 방법론 (프로젝트의 강점)

### 3.1 계층적 검증

고정소수점 골든 모델 ↔ RTL 비트단위 일치(iverilog TB) → AXIS 래퍼 robustness
TB(.sv) → 보드 UART 캡처 vs 골든 모델 비교(자동 판정).

### 3.2 사례 1 — DMA MM2S timeout 근본 원인 (log 31/32)

- 증상: 모든 BD(main/debug/smoke)에서 MM2S DMA timeout.
- 근본 원인: 전송량 8192샘플×2B = **16384B가 AXI DMA 기본 length 필드(14-bit,
  최대 16383B)를 정확히 1바이트 초과.**
- 수정: `c_sg_length_width=23` 명시. smoke → main FIR → Python FFT plot 전 경로 복구.

### 3.3 사례 2 — AXIS 래퍼 프레이밍 버그와 hold-back (log 41~44)

- 시뮬레이션으로 skid buffer 버그 4건 재현·수정 후, 코드 리뷰에서 잔존 데드락 발견:
  래퍼는 패킷 길이를 tlast 입력 도착 시점에야 알 수 있는데 코어 latency 때문에 마지막
  출력이 먼저 나올 수 있음 — tlast 직전 tvalid 버블이 임계값(v1 3, v2 4사이클) 이상이면
  마지막 출력이 TLAST 없이 나가고 래퍼 영구 정지.
- 해결(hold-back): 최신 출력을 "마지막 여부 확정 시까지" 보류 — 타이밍 운에 의존하지
  않는 구조적 해결.
- 검증 방법론: **새 TB를 수정 전 RTL에 먼저 돌려 예측 임계값과 정확히 일치하는 FAIL을
  확인한 뒤** 수정으로 PASS 전환 — "테스트가 버그를 실제로 잡는다"부터 증명.
  버블 스윕 회귀(`make run_bug`) + 전체 회귀(`run_all`) PASS.

## 4. FPGA 구현 결과

### 4.1 타이밍/자원

| 항목 | v1 | v2 |
| --- | ---: | ---: |
| Fmax (clk_wiz 정밀 스윕, log 40) | 116 MHz | 146 MHz |
| 배포 클럭 | 115 MHz | 145 MHz |
| 코어 단독 자원 (routed DCP 계층 스코프) | (v2와 동급) | LUT 1792 / FF 2113 / DSP 16 |
| Vivado 전력 추정 (전체 비트스트림) | 1.699 W | 1.705 W |

- 수정 RTL 골든 재빌드에서 WNS·자원이 수정 전과 완전 동일 + 크리티컬 패스 불변 →
  래퍼 수정은 타이밍 중립, Fmax 수치 유효 (`sweep_summary*.md` 재빌드 검증 절).

### 4.2 보드 실측 (기능 동작)

- v1@115MHz / v2@145MHz 모두 SD boot + `mode 1-1` 데모 정상 동작.
- 정량 판정 (scenario 1-1, 보드 출력 vs 골든): PASS — max error 6 LSB, RMSE 1.4 LSB,
  SNR 74.9dB, correlation 1.000. 톤별(5/20/30MHz) 감쇠 판정 표 포함
  (`docs/report/fir_n43/summary/scenario1_1.md`, 1-2도 동일 구조).
- 25MHz Nyquist-edge −6dB, 45MHz alias 억제 수치 확인 (scenario1_2.md).

### 4.3 CPU 대비 (§8-2)

- Windows 데모 노트북(i5-1340P), numpy float64 `np.convolve`, convolve 구간만 측정:
  CPU median **162.0µs** vs FPGA **83.0µs** (8192샘플 window).
  스펙·방법론은 PNG(`cpu_vs_fpga_timing_window.png`) 하단에 명기.

## 5. 보조 지표 (§8 교수님 지시)

### 5.1 ASIC flow (§8-1) — 완료

- 환경: Tanner Generic 250nm, Oasys-RTL 합성, v1/v2 **동일 제약 페어 sweep**
  (20000→6000ps, 6페어). 상세: `asic/oasys/results/sweep_report.md`, log 47.
- 결과: **전 구간 v1 ≈ v2** (slack 차 노이즈 수준, 순위 요동), 둘 다 ≥166.7MHz에서
  PASS (250nm임에도 28nm FPGA의 146MHz 초과). 면적·전력도 Δ1% 안팎 동률.
- **핵심 결론**: v1의 FPGA 병목 경로(z_reg[1]→round_reg)를 FPGA CARRY4는 8.664ns에
  처리했지만 ASIC 표준셀 합성은 carry-save 재구조화로 5.719ns에 흡수 —
  **v2 분할의 26% 이득은 FPGA 물리 구조(고정 캐리 체인)에 종속된 타겟 특화 최적화**
  임을 실측으로 증명. "최적화는 아키텍처가 아니라 타겟에 속한다."
- Nitro P&R은 서버 툴(2020.2) placer 내부 버그(SDA101 assertion)로 중단 — 시도·원인
  문서화 (`log 47 §4`). 비교 결론은 합성 결과로 완결.
- FPGA 대비 표: `docs/report/fir_n43/summary/asic_vs_fpga.md`.

### 5.2 전력 실측 (§8-3) — [TrackB: 수요일 실측 후 채움]

- 방법(확정, log 46): 보드 5V 입력 직렬 DMM(HDS242) + 상태 차분
  (S0 PL 미구성 / S1 boot idle / S2 mode 1-1 실행), 상태당 5회 판독 중앙값.
- [TrackB] 측정 표 (S0/S1/S2 V·I·P) —
- [TrackB] Vivado 추정(1.705W, on-chip) 대비 해석 — S1−S0 차분 = PL 구성+클럭+앱 몫,
  S2 ≈ S1이면 "µs 스케일 burst는 평균 전력에 안 잡힘" 자체를 결과로 기록.

### 5.3 CPU 스펙 명기 (§8-2) — 완료 (§4.3에 반영)

## 6. 한계 및 향후 과제

- run이 타임아웃으로 **abort된 뒤의 복구는 불가** (펌웨어에 PL 래퍼 리셋 수단 없음) —
  정상 반복 실행 경로는 v22 수정으로 해소(시뮬 검증 + 보드 mode 1-2 반복 확인
  [TrackB: 수요일 실보드 확인 결과 반영]).
- Fmax 정밀 측정(오실로스코프 등)은 미포함 — 기능 동작 실측까지 수행.
- ASIC P&R은 툴 내부 버그로 중단 (절차 보존, 재개 가능).

## 7. 결론

- 스펙 충족을 정량 판정으로 증명한 실시간 FIR decimation IP (SNR 74.9dB, PASS).
- 버그를 "재현 → 임계값 예측 → 구조적 수정 → 회귀"로 다루는 검증 방법론.
- v1→v2 개선을 FPGA에서 실측(+26%)하고, 그 이득의 타겟 종속성을 ASIC 합성으로
  교차 검증 — 단일 RTL을 두 타겟에서 조명한 보조 지표 3종(§8) 완비.
