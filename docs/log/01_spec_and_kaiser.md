# 01. Spec 확정 + Kaiser 계수 생성

- 작성일: 2026-03-08
- 단계: 1
- ideal 모델 초기 설계(anti-alias FIR 중심)
- 후속 업데이트(2026-03-18): 이 문서의 초기 tap-count 판단 중 `N=41` 제출용 가정은 이후 `docs/log/07_coeff_stopband_spec_check.md`에서 strict coefficient-based stopband 기준으로 재검증되었고, 현재 공식 spec-check tap은 `N=43`이다.

## 1) 이번 주 핵심 결정

1. FIR Decimator ideal 모델의 스펙 잠정 확정(anti-alias FIR + decimation, `Fs=100e6, fp=15e6, fs=25e6, As=60, M=2`).
2. 구현 순서를 `anti_alias_fir -> decimator -> fir_decimator_ideal`으로 확정.
3. golden 모델의 데이터 포맷은 당시 우선 `signed 16-bit, Q4.12`를 작업 가정으로 두었고, 이후 문서에서 `Q1.15`로 재결정했다.
4. 필터 계수 생성 방식을 Kaiser window 기반으로 확정함.
5. Kaiser 기반 LPF 계수 생성 함수를 먼저 구현하고 `num_taps`를 가변 파라미터로 열어둠(5/15/35/37/39/41/43 실험 가능).

## 2) 결정 근거

### 1. 스펙 잠정 확정 근거

- Fs=100MHz, M=2: 1 sample/cycle @ 100MHz 아키텍처에서 자동 결정.
- 그렇다면 왜 1 sample/cycle @ 100MHz인가? -> ZZybo Z7-20에서 구현 가능성이 충분하면서도 FIR 파이프라이닝과 timing closure를 요구하므로 학부 수준에서 적절히 도전적인 설계 조건이다. 200 MHz 이상의 더 높은 동작 주파수도 가능할 수 있으나, 본 프로젝트의 목표 throughput 대비 필요 이상으로 복잡도를 증가시킬 수 있어 채택하지 않았다.
- fs=25MHz: Fs_out=50MSps의 나이퀴스트 주파수(Fs_out/2)와 일치.
- fp=15MHz: 천이대역 10MHz(fs-fp=25-15) 확보로 타이밍 클로저
  난이도 완화. fp=20MHz도 가능하나 천이대역 5MHz는 N이 급증해
  완주 리스크 증가.
- As=60dB: alias 억제 1/1000 수준. 40dB(1/100)는 부족,
  80dB(1/10000)는 N이 지나치게 증가. 학부 설계 완주 가능 범위
  내 합리적 선택.
- 왜 Kaiser window인가? -> 재현성때문.
- Kaiser 공식 최솟값: 37.22 (order 기준 36.22 + 1)
- 최초 홀수: 39 (Type-I linear-phase 조건 만족)
- 당시 작업 가정: 41 (고정소수점 양자화 오차 감안 보수적 여유 +2)
- 후속 재검증 결과: strict coefficient-based worst-case stopband 기준에서는 `N=41`이 미달이었고, `N=43`이 현재 기준 첫 만족 tap으로 갱신되었다.

### 2. 구현 순서 확정 근거

- anti_alias_fir를 먼저 구현해야 fp/fs/As 스펙이 실제로
  만족되는지 확인 가능.
- decimator 단독 검증만으로는 alias 억제 여부를 확인할 수 없어
  FIR 없는 순서는 제외.

### 3. golden 모델의 `signed 16-bit, Q4.12`를 작업 가정으로 둔 근거

- 현재까지 확인한 필터 계수의 동적 범위와 `As=60dB` 요구만 보면
  `Q4.12`는 유력한 후보 포맷이다.
- As=60dB 달성에 필요한 최소 소수부 비트수 약 10bit 대비
  12bit 소수부는 충분한 여유를 제공한다.
- 다만 입력 멀티톤의 진폭 배분, headroom, crest factor, phase 정책이
  아직 확정되지 않았으므로 현재 시점에서는 최종 포맷으로 단정할 수 없다.
- 따라서 이 시점의 `Q4.12`는 fixed/golden 구현 초기 실험을 위한 작업 가정으로만 두었다.
- 이후 FIR coefficient 검토와 입력 포맷 검토를 거쳐 현재 기준은 `Q1.15`로 갱신되었다(`03_coeff_qformat.md`, `04_input_qformat.md`).

### 4. 필터 계수 생성 방식을 Kaiser window 기반으로 확정한 근거

- Kaiser window는 As가 결정되면 N이 수학적으로
  결정되므로 설계 재현성이 보장됨.
- `β=5.65326`와 tap 수 두 숫자만 결정되면 Python/MATLAB 등 어떤
  환경에서도 동일한 계수 재현 가능 → 오픈소스 튜토리얼 목적에
  직접 부합.
- 대안 비교:
  - Hamming/Hanning: 파라미터 없어 As를 정밀하게 제어 불가.
    As=60dB 보장 어려움.
  - Parks-McClellan(등리플 최적): 성능은 우수하나 수치
    최적화 알고리즘 특성상 툴/구현 방식에 따라 계수가
    미세하게 달라져 재현성 보장 불가.
  - Kaiser: As → β → N 순서로 수식 기반 결정 가능.
    재현성과 As 제어 모두 만족.

### 5. num_taps 가변 파라미터로 열어둔 근거

- N 고정 시 단일 합성 결과만 얻어 PPA trade-off 분석 불가.
- `N=5/15/35/37/39/41/43` 단계적 실험으로 탭 수 증가에 따른
  DSP/LUT/Fmax 변화 곡선 도출 가능.
- 현재 기준에서는 `N=39/41` near-spec 비교와 `N=43` spec-satisfying candidate의 PPA 차이가
  핵심 비교 데이터다.

## 3) 구현/검증 결과 (숫자 중심)

- 구현 파일: `/model/design_kaiser_coeff.py`
- 추가 함수:
  - `kaiser_beta(as_db)`
  - `estimate_num_taps(fs_in_hz, fp_hz, fs_hz, as_db)`
  - `design_kaiser_lpf(fs_in_hz, fp_hz, fs_hz, as_db, num_taps=None)`
- 스펙 예시 검증 (`Fs=100e6, fp=15e6, fs=25e6, As=60`)
  - 추정 탭수: `39`
  - `num_taps=41` 시 `sum(h)=1.0`, 대칭성 확인(`h == h[::-1]`)
  - strict stopband 재검증 결과는 `docs/log/07_coeff_stopband_spec_check.md`를 따른다
