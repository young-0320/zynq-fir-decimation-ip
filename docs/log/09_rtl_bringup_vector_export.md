# 09. RTL Bring-up Vector Export 추가

- 작성일: 2026-03-31
- 단계: 5
- 목적: `N=5` direct-form RTL bring-up을 위한 self-checking vector를 `hex` 형식으로 재현 가능하게 export한다

## 1) 이번 세션 핵심 결정

1. `run_compare_ideal_vs_fixed.py`는 계속 `ideal vs fixed` 비교 스크립트로 둔다.
2. RTL용 vector 준비는 별도 스크립트 `sim/python/export_rtl_bringup_vectors.py`로 분리한다.
3. 새 export 스크립트는 계산을 다시 하지 않고, 기존 `sim/output/ideal_vs_fixed_n5/`의 `Q1.15` artifact를 `hex`로 변환만 한다.
4. 기본 vector 출력 경로는 `sim/vectors/direct_form/bringup_n5/`로 둔다.

## 2) 추가한 파일

- `sim/python/export_rtl_bringup_vectors.py`
- `sim/python/test/test_export_rtl_bringup_vectors.py`
- `sim/vectors/direct_form/bringup_n5/input_q15.hex`
- `sim/vectors/direct_form/bringup_n5/coeff_q15.hex`
- `sim/vectors/direct_form/bringup_n5/expected_fir_q15.hex`
- `sim/vectors/direct_form/bringup_n5/expected_decim_q15.hex`

## 3) 입력 / 출력 계약

입력 artifact:

- `sim/output/ideal_vs_fixed_n5/input_q15.npy`
- `sim/output/ideal_vs_fixed_n5/coeff_q15.npy`
- `sim/output/ideal_vs_fixed_n5/fixed_fir_q15.npy`
- `sim/output/ideal_vs_fixed_n5/fixed_decim_q15.npy`

출력 vector:

- `sim/vectors/direct_form/bringup_n5/input_q15.hex`
- `sim/vectors/direct_form/bringup_n5/coeff_q15.hex`
- `sim/vectors/direct_form/bringup_n5/expected_fir_q15.hex`
- `sim/vectors/direct_form/bringup_n5/expected_decim_q15.hex`

hex format:

- 한 줄에 한 샘플
- ASCII text
- `0x` prefix 없음
- 4자리 zero-padded lowercase hex
- signed `int16` 값을 16-bit two's complement로 기록

즉, RTL testbench에서는 `$readmemh`로 바로 읽을 수 있는 형식을 기본으로 잡았다.

## 4) 구현 내용

`sim/python/export_rtl_bringup_vectors.py`는 아래 동작만 수행한다.

1. 입력 `.npy` 4개를 읽는다.
2. 각 배열이 `1-D` 정수 배열이며 `Q1.15/int16` 범위 안에 있는지 검사한다.
3. 각 값을 `16-bit two's complement hex` 문자열로 변환한다.
4. bring-up vector 디렉터리에 `hex` 파일로 저장한다.

이번 세션에서는 export 책임만 분리했고, golden 계산 책임은 기존 비교 스크립트에 남겨 두었다.

## 5) 검증 커맨드

```bash
cd /home/young/dev/10_zynq-fir-decimation-ip
.venv/bin/pytest -q sim/python/test/test_export_rtl_bringup_vectors.py
.venv/bin/python -m sim.python.export_rtl_bringup_vectors
.venv/bin/pytest -q
```

## 6) 확인 결과

테스트 결과:

- `sim/python/test/test_export_rtl_bringup_vectors.py`: `3 passed`
- 전체 pytest: `64 passed in 0.56s`

export 결과:

- `input_q15.hex`: `8192` lines
- `coeff_q15.hex`: `5` lines
- `expected_fir_q15.hex`: `8196` lines
- `expected_decim_q15.hex`: `4098` lines

해석:

- 이제 Python fixed golden 결과를 RTL testbench가 직접 소비할 수 있는 vector 형식으로 고정했다.
- 아직 RTL self-checking testbench 자체는 없지만, 비교 기준 벡터는 준비되었다.

## 7) 현재 기준 다음 액션

1. `rtl/direct_form/`에 `N=5` baseline RTL을 추가한다.
2. `sim/rtl` 또는 이에 준하는 testbench 위치를 정하고, 위 `hex` vector를 읽는 self-checking testbench를 만든다.
3. FIR core와 `FIR -> Decimator` top-level 각각에 대해 Python-vs-RTL bit-exact loop를 닫는다.
