# Direct Form FIR (Bring-up, N=5)

초기 기능 검증용 모듈. 메인 파이프라인은 Fmax 확보를 위해 Transposed Form을 사용하므로 이 디렉토리는 적극적으로 유지보수하지 않는다.

---

## 파일 구조

```
direct_form/
├── decimator_m2_phase0.v          # M=2 phase-0 decimator (rtl/transposed_form/에 복사본 존재)
└── bringup_n5/
    ├── fir_direct_n5.v            # N=5 Direct Form FIR 코어
    ├── fir_decimator_direct_n5_top.v  # FIR + decimator 최상위
    ├── top_zybo_bringup_n5.v      # Zybo 보드 bringup 최상위
    ├── bringup_vector_source.v    # 테스트 벡터 소스
    ├── bringup_output_checker.v   # 출력 검증기
    └── reset_conditioner.v        # 리셋 동기화
```

## 계층 구조

```
top_zybo_bringup_n5
└── fir_decimator_direct_n5_top
    ├── fir_direct_n5
    └── decimator_m2_phase0
```
