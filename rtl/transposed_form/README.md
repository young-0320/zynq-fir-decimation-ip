# Transposed Form FIR (N=43)

메인 파이프라인. 100MHz 타이밍 클로저 확인 (WNS=+0.278ns, DSP48=16, LUT=1827).

---

## 파일 구조

```
transposed_form/
├── decimator_m2_phase0.v   # M=2 phase-0 decimator (direct_form/에 복사본 존재)
└── n43/
    ├── fir_n43.v               # N=43 FIR 코어
    ├── fir_decimator_n43.v     # FIR + decimator 연결
    └── fir_decimator_n43_axis.v  # AXI-Stream 래퍼 (PS-PL 연동용)
```

## 계층 구조

```
fir_decimator_n43_axis        ← AXI-Stream 래퍼
  └── fir_decimator_n43       ← FIR + M=2 decimation
        ├── fir_n43            ← N=43 Transposed Form FIR
        └── decimator_m2_phase0
```

## 인터페이스

| 모듈 | 인터페이스 |
|------|-----------|
| `fir_n43` | `clk/rst`, `in_valid/in_sample`, `out_valid/out_sample` |
| `fir_decimator_n43` | 동일 (출력은 M=2 decimated) |
| `fir_decimator_n43_axis` | AXI4-Stream slave/master + `aclk/aresetn` |
