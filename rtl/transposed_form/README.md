# Transposed Form FIR (N=43)

메인 파이프라인 RTL. v1(3-stage)과 v2(4-stage, round 분리) 두 버전을 유지한다.
타이밍·자원 수치는 `vivado/reports/sweep_summary.md`(v1) / `sweep_summary_v2.md`(v2) 참고.

---

## 파일 구조

```
transposed_form/
├── decimator_m2_phase0.v            M=2 phase-0 decimator (v1/v2 공용)
└── n43/
    ├── fir_n43.v                    v1 FIR 코어 (3-stage 파이프라인)
    ├── fir_decimator_n43.v          v1 FIR + decimator
    ├── fir_decimator_n43_axis.v     v1 AXI-Stream 래퍼 (Block Design top)
    ├── fir_n43_v2.v                 v2 FIR 코어 (4-stage, round 스테이지 분리)
    ├── fir_decimator_n43_v2.v       v2 FIR + decimator
    ├── fir_decimator_n43_axis_v2.v  v2 AXI-Stream 래퍼
    └── constrs/
        └── zybo_n43.xdc             단독 합성 전용 — Block Design 프로젝트에 포함 금지
```

## 계층 구조 (v1/v2 동일)

```
fir_decimator_n43_axis[_v2]      ← AXI-Stream 래퍼 (Block Design top)
  └── fir_decimator_n43[_v2]     ← FIR + M=2 decimation
        ├── fir_n43[_v2]         ← N=43 Transposed Form FIR
        └── decimator_m2_phase0
```

## v1 ↔ v2

- v2는 v1의 누산+라운딩 병합 경로(FPGA CARRY4 체인 병목)를 별도 스테이지로 분리한
  구조다. FIR latency 3→4 cycle, Fmax 116→146 MHz. 설계 근거는 `docs/log/39`,
  스윕 데이터는 `vivado/reports/sweep_summary_v2.md`.
- AXI-Stream 래퍼는 두 버전 모두 skid 4칸 + 마지막 출력 hold-back 구조다
  (`docs/log/42`~`44` 수정 반영).

## 인터페이스

| 모듈 | 인터페이스 |
| --- | --- |
| `fir_n43[_v2]` | `clk/rst`, `in_valid/in_sample[15:0]`, `out_valid/out_sample[15:0]` |
| `fir_decimator_n43[_v2]` | 동일 (출력은 M=2 decimated) |
| `fir_decimator_n43_axis[_v2]` | AXI4-Stream slave(`s_axis`) / master(`m_axis`), `aclk/aresetn`, tdata 16-bit |

## zybo_n43.xdc 사용 주의

단독 FIR 합성 시 `clk` 포트 타이밍 제약용으로 작성된 파일이다. Block Design
프로젝트에 이 파일이 포함되면 합성 top이 래퍼로 설정되어 Block Design이 무시되고
비트스트림 생성이 실패한다. Block Design 프로젝트에서는 추가하지 않거나, 추가했다면
반드시 `Disable File` 처리해야 한다.
