# 15. RTL Vector Pipeline Extension for Transposed Form

- 작성일: 2026-05-03
- 단계: 7
- 목적: N=43 Transposed Form RTL 검증 환경 구축을 위해 기존 bring-up 파이프라인을 확장한 의사결정 과정을 기록한다
- 선행 문서: `docs/log/14_transposed_form_rtl_decisions.md`

## 1) 배경

N=43 Transposed Form RTL의 iverilog self-checking 시뮬레이션을 위해
Python 골든 출력을 RTL testbench용 hex 벡터로 변환하는 파이프라인이 필요했다.

기존 N=5 Direct Form bring-up 파이프라인은 아래 2단계로 구성돼 있다.

[1단계] `run_compare_ideal_vs_fixed.py`
→ sim/output/ideal_vs_fixed_n{N}/ 에 .npy 생성

[2단계] `export_rtl_bringup_vectors.py`
→ .npy 읽어서 sim/vectors/direct_form/bringup_n5/ 에 .hex 생성

이 파이프라인을 N=43 Transposed Form에 재사용하는 방향을 검토했다.

## 2) 검토 과정 및 의사결정

### 검토 1: export_rtl_bringup_vectors.py 재사용 가능 여부

`export_rtl_bringup_vectors.py`는 `.npy → .hex` 포맷 변환만 수행하는 스크립트다.
변환 로직 자체는 FIR 구조와 무관하다.

문제는 `_default_output_dir()`가 `direct_form/bringup_n5/`로 하드코딩돼 있다는 점이었다.
그러나 이미 `--output-dir` 인수가 구현돼 있으므로, 명시적으로 경로를 넘기면 그대로 재사용할 수 있다.

```bash
.venv/bin/python -m sim.python.export_rtl_bringup_vectors \
    --num-taps 43 \
    --input-dir sim/output/ideal_vs_fixed_trans_n43 \
    --output-dir sim/vectors/transposed_form/n43
```

→ **기존 스크립트 수정 없이 재사용 가능. 신규 스크립트 불필요.**

### 검토 2: run_compare_ideal_vs_fixed.py 재사용 가능 여부

`run_compare_ideal_vs_fixed.py` 내부에서 호출하는 golden 함수가 문제였다.

```python
from model.fixed.direct_form.fir_decimator_golden import run_fir_decimator_golden
```

이 스크립트는 **Direct Form golden만 호출**하도록 고정돼 있다.
따라서 이 스크립트로 생성한 `fixed_fir_q15.npy`, `fixed_decim_q15.npy`는
**Direct Form 출력**이 된다.

N=43 Transposed Form RTL의 expected 벡터로 쓰려면
**Transposed Form golden 출력**이 필요하다.

이미 `model/fixed/transposed_form/fir_decimator_transposed_golden.py`가
완성돼 있으므로, 스크립트에 `--form` 인수를 추가해서 golden 함수를 분기하는 것으로
해결 가능하다고 판단했다.

### 검토 3: 전면 재설계 vs 최소 수정

전면 재설계(가변 탭 + 구조 선택 범용 파이프라인 신규 작성) 방향도 검토했으나 아래 이유로 기각했다.

- 이미 검증된 N=5 파이프라인을 건드리면 재검증 비용이 발생한다
- 실제 문제는 `run_compare_ideal_vs_fixed.py`의 golden 함수 고정 딱 하나다
- `--form` 인수 하나 추가로 동일한 목적을 달성할 수 있다
- 일정 압박 상황에서 최소 변경이 리스크가 낮다

## 3) 확정 결정

`run_compare_ideal_vs_fixed.py`에 `--form` 인수를 추가한다.

| 항목             | 결정                                                                                     |
| ---------------- | ---------------------------------------------------------------------------------------- |
| 변경 대상        | `sim/python/run_compare_ideal_vs_fixed.py` 단일 파일                                   |
| 추가 인수        | `--form {direct, transposed}` (default: `direct`)                                    |
| default save-dir | `direct` → `ideal_vs_fixed_n{N}/`, `transposed` → `ideal_vs_fixed_trans_n{N}/` |
| 기존 동작        | `--form` 생략 시 기존과 완전 동일 (하위 호환 보장)                                     |
| 신규 스크립트    | 없음 (기존 스크립트 재사용)                                                              |

## 4) 변경 내용 상세

### 추가된 인수

```python
parser.add_argument(
    "--form",
    type=str,
    choices=["direct", "transposed"],
    default="direct",
    help=(
        "FIR golden model to use. "
        "'direct' uses Direct Form golden (default), "
        "'transposed' uses Transposed Form golden. "
        "Affects default save-dir name."
    ),
)
```

### _default_save_dir() 수정

```python
# 변경 전
def _default_save_dir(num_taps: int) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "sim" / "output" / f"ideal_vs_fixed_n{num_taps}"

# 변경 후
def _default_save_dir(num_taps: int, form: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    if form == "transposed":
        return repo_root / "sim" / "output" / f"ideal_vs_fixed_trans_n{num_taps}"
    return repo_root / "sim" / "output" / f"ideal_vs_fixed_n{num_taps}"
```

### golden 함수 분기

```python
# 변경 전
fixed_fir_q15, fixed_decim_q15 = run_fir_decimator_golden(
    x=x_q15, h=h_q15, m=m, phase=phase, return_intermediate=True,
)

# 변경 후
if form == "transposed":
    fixed_fir_q15, fixed_decim_q15 = run_fir_decimator_transposed_golden(
        x=x_q15, h=h_q15, m=m, phase=phase, return_intermediate=True,
    )
else:
    fixed_fir_q15, fixed_decim_q15 = run_fir_decimator_golden(
        x=x_q15, h=h_q15, m=m, phase=phase, return_intermediate=True,
    )
```

### summary에 form 필드 추가

```python
"config": {
    ...
    "form": form,   # 신규 추가
    ...
}
```

## 5) 확정된 N=43 Transposed Form 벡터 생성 명령어

```bash
# 1단계: Transposed Form golden 실행 → .npy 생성
.venv/bin/python -m sim.python.run_compare_ideal_vs_fixed \
    --num-taps 43 \
    --form transposed
# → sim/output/ideal_vs_fixed_trans_n43/

# 2단계: .npy → .hex 변환
.venv/bin/python -m sim.python.export_rtl_bringup_vectors \
    --num-taps 43 \
    --input-dir sim/output/ideal_vs_fixed_trans_n43 \
    --output-dir sim/vectors/transposed_form/n43
# → sim/vectors/transposed_form/n43/
```

## 6) 기존 N=5 파이프라인 재현 명령어 (변경 없음)

```bash
.venv/bin/python -m sim.python.run_compare_ideal_vs_fixed --num-taps 5
.venv/bin/python -m sim.python.export_rtl_bringup_vectors --num-taps 5
```
