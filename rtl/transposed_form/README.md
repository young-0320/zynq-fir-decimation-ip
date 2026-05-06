# Transposed Form FIR (N=43)

메인 파이프라인. 100MHz 타이밍 클로저 확인 (WNS=+0.278ns, DSP48=16, LUT=1827).
Block Design 통합 후 WNS=+1.239ns (Step 6).

---

## 파일 구조

```
transposed_form/
├── decimator_m2_phase0.v       M=2 phase-0 decimator
└── n43/
    ├── fir_n43.v               N=43 FIR 코어
    ├── fir_decimator_n43.v     FIR + decimator 연결
    ├── fir_decimator_n43_axis.v  AXI-Stream 래퍼 (PS-PL 연동용 top)
    └── constrs/
        └── zybo_n43.xdc        ⚠️ 단독 합성 전용 — Block Design 프로젝트에 포함 금지
```

## 계층 구조

```
fir_decimator_n43_axis        ← AXI-Stream 래퍼 (Block Design top)
  └── fir_decimator_n43       ← FIR + M=2 decimation
        ├── fir_n43            ← N=43 Transposed Form FIR
        └── decimator_m2_phase0
```

## 인터페이스

| 모듈                       | 인터페이스                                                                         |
| -------------------------- | ---------------------------------------------------------------------------------- |
| `fir_n43`                | `clk/rst`, `in_valid/in_sample[15:0]`, `out_valid/out_sample[15:0]`          |
| `fir_decimator_n43`      | 동일 (출력은 M=2 decimated, 4117 samples)                                          |
| `fir_decimator_n43_axis` | AXI4-Stream slave(`s_axis`) / master(`m_axis`), `aclk/aresetn`, tdata 16-bit |

## zybo_n43.xdc 사용 주의

단독 FIR 합성(Step 4) 시 `clk` 포트 타이밍 제약용으로 작성된 파일이다. Block Design 프로젝트에 이 파일이 포함되면 합성 top이 `fir_decimator_n43_axis`로 설정되어 Block Design이 무시되고 비트스트림 생성이 실패한다. Block Design 프로젝트에서는 아예 추가를 하지 않거나, 추가했다면 반드시 `Disable File` 처리해야 한다.
