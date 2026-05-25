# 34. Python demo/report 모듈화와 evidence pipeline 정리

- 작성일: 2026-05-25
- 선행 문서:
  - `33_pipeline_folder_reorganization.md`
  - `../workflow/workflow_v16.md`
- 관련 커밋:
  - `896a0f0` `refactor: split FIR live demo modules`
  - `45d83bb` `feat: add FIR decimator metrics module`
  - `b7ce756` `feat: add FIR N43 report pipeline`

---

## 결론

오늘의 핵심 결정은 Python demo script를 하나의 큰 파일로 계속 키우지 않고, live demo와 evidence 저장 pipeline을 분리하는 것이다.

확정한 구조:

```text
sw/
  fir_decimator_demo.py          # official live demo entrypoint
  fir_decimator_capture.py       # UART capture module
  fir_decimator_fft_viewer.py    # live FFT viewer and plot helper
  fir_decimator_metrics.py       # board-free numeric metrics
  fir_decimator_report.py        # save-only report/evidence pipeline
```

사용자 관점의 top-level entrypoint는 두 개다.

```text
1. live 시연:
   python sw/fir_decimator_demo.py --mode 0|1-1|1-2|2

2. evidence 저장:
   python sw/fir_decimator_report.py --mode 1-1|1-2|all
```

`demo.py`는 공식 live demo 명령으로 남긴다. 단, 내부 구현을 다시 비대하게 만들지 않고 `fir_decimator_fft_viewer.py`에 위임한다.

`report.py`는 저장 전용 top pipeline이다. PC 화면에 FFT 창을 띄우지 않고, PNG/JSON/Markdown만 저장한다.

---

## 배경

기존 `fir_decimator_demo.py`는 다음 역할이 한 파일에 섞여 있었다.

```text
- tone 생성
- UART command 전송
- board packet 수신
- FFT 계산과 plot 표시
- scenario CLI 처리
```

여기에 metric 계산, fixed-point golden 비교, JSON/Markdown report 저장까지 넣으면 demo script가 계속 커지고 책임 경계가 흐려진다.

오늘 논의한 방향은 다음과 같다.

1. demo는 사람이 보는 live 시연에 집중한다.
2. capture, metric, report는 보드 증거 저장/검증용 pipeline에서 재사용한다.
3. metric 계산은 UART/plot/file 저장을 모르는 순수 모듈로 둔다.
4. report는 capture와 metrics, plot helper를 조합하는 top wrapper로 둔다.
5. 너무 엄밀하게 `plot.py`까지 새로 분리하는 것은 현재 규모에서는 과하다.

따라서 최종 구조는 다음 의존성으로 확정했다.

```text
fir_decimator_demo.py
  -> fir_decimator_fft_viewer.py
       -> fir_decimator_capture.py

fir_decimator_report.py
  -> fir_decimator_capture.py
  -> fir_decimator_metrics.py
  -> fir_decimator_fft_viewer.py  # plot helper only

fir_decimator_metrics.py
  -> model/q1_15.py
  -> model/fixed/transposed_form/fir_decimator_golden.py

fir_decimator_capture.py
  -> pyserial
```

이 구조는 `demo -> fft_viewer -> capture`라는 live 시연 경로와, `report -> capture + metrics + plot helper`라는 저장 경로를 분리한다.

---

## 모듈별 역할

### `fir_decimator_demo.py`

공식 live demo entrypoint다.

역할:

- 사용자가 직접 실행하는 시연 명령을 제공한다.
- `--mode 0`, `--mode 1-1`, `--mode 1-2`, `--mode 2`를 기존처럼 지원한다.
- 내부 구현은 `fir_decimator_fft_viewer.py`에 위임한다.

중요한 결정:

- 이 파일을 legacy dead wrapper로 보지 않는다.
- 공식 demo command로 유지한다.
- 다만 capture/plot/metric/report 로직을 모두 직접 품지 않는다.

### `fir_decimator_capture.py`

UART capture 전용 모듈이다.

역할:

- UART open
- tone command 전송
- board output packet 수신
- DMA error text 해석
- Q1.15 int16 packet 반환
- normalized float 변환 helper 제공

중요한 결정:

- plot을 하지 않는다.
- metric을 계산하지 않는다.
- file/report artifact를 저장하지 않는다.
- packet header의 sample count를 검증하는 guard를 둔다.

sample-count guard:

```text
[MAGIC 4 bytes][N 4 bytes][int16 sample * N]
```

보드 packet sync가 깨졌을 때 이상한 `N`을 믿고 payload를 읽지 않도록 `expected_samples` 또는 `max_samples`를 지원한다. `report.py`는 `expected_samples=N_OUT`으로 4096개 출력을 강제한다.

### `fir_decimator_fft_viewer.py`

live FFT viewer와 plot helper 모듈이다.

역할:

- demo tone 생성
- FFT dB 계산
- tone marker/alias marker 생성
- scenario 0 PC-only aliasing plot
- scenario 1-1/1-2 board-measured FFT plot
- scenario 2 interactive FFT viewer

중요한 결정:

- PC 화면에 FFT를 띄우는 책임은 viewer/demo 경로에만 있다.
- metrics/report에는 의존하지 않는다.
- capture module만 사용해서 board output을 얻는다.
- report는 여기서 low-level plot helper만 재사용하고 `plt.show()`는 호출하지 않는다.

### `fir_decimator_metrics.py`

board-free numeric metrics 모듈이다.

역할:

- input tone을 Q1.15로 생성
- Python fixed-point FIR+decimator golden output 생성
- board output과 golden output sample-domain 비교
- FFT peak extraction
- tone peak 비교
- in-memory report dict 생성

metric 항목:

```text
sample-domain:
  n_samples_compared
  max_abs_error_lsb
  rmse_lsb
  snr_db
  correlation
  mean_error_lsb
  max_error_lsb
  min_error_lsb
  saturation_count
  clipping_count
  trim/alignment metadata

frequency-domain:
  tone_hz
  expected_output_hz
  input_peak_db
  board_peak_db
  golden_peak_db
  board_vs_golden_peak_delta_db
  board_attenuation_db
  golden_attenuation_db
  region
  verdict
```

중요한 결정:

- UART를 모른다.
- matplotlib를 모른다.
- JSON/CSV/Markdown 저장을 하지 않는다.
- PASS 기준은 fixed-point golden과 board output 비교가 기준이다.
- transition-band tone은 hard PASS/FAIL이 아니라 `INFO`로 둔다.

### `fir_decimator_report.py`

저장 전용 evidence/report pipeline이다.

역할:

- `--mode 1-1`, `--mode 1-2`, `--mode all` 지원
- board output Q15 capture
- fixed Q15 reference/golden 생성
- metrics report dict 생성
- FFT PNG 저장
- metrics JSON 저장
- root summary Markdown 재생성

저장 구조:

```text
docs/report/fir_n43/
  summary.md
  plot/
    scenario1_1_fft.png
    scenario1_2_fft.png
  metrics/
    scenario1_1_metrics.json
    scenario1_2_metrics.json
```

중요한 결정:

- `plt.show()`를 호출하지 않는다.
- `plot/`과 `metrics/` 폴더가 없으면 자동 생성한다.
- raw `.npy` 저장은 이번 범위에서 제외했다.
- CSV 저장도 이번 범위에서 제외했다. `metrics.json` 안에 tone metrics list를 포함한다.
- `summary.md`는 append가 아니라 현재 실행 결과 기준으로 재생성한다.

---

## report mode 정책

report 대상은 board-measured fixed scenario만 둔다.

```text
지원:
  1-1
  1-2
  all

제외:
  0  # PC-only aliasing demo
  2  # interactive viewer
```

이유:

- mode 0은 보드 evidence가 아니라 설명용 PC-only plot이다.
- mode 2는 사용자가 임의 tone을 넣는 interactive path라 자동 report 대상이 아니다.
- portfolio/report evidence는 재현 가능한 fixed scenario 1-1, 1-2를 기준으로 한다.

`all`은 1-1 후 1-2를 연속 실행한다. 다만 보드 reset이 scenario 사이에 필요할 수 있으므로, 필요하면 1-1과 1-2를 따로 실행한다.

---

## FFT plot 표시 정책

PC 화면에 FFT를 띄우는 것은 demo/viewer의 책임이다.

```text
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1
python sw/fir_decimator_demo.py --mode 2 --port /dev/ttyUSB1
```

report script는 화면 표시를 하지 않는다.

```text
python sw/fir_decimator_report.py --mode 1-1 --port /dev/ttyUSB1 --timeout 30
```

이 명령은 다음만 수행한다.

```text
1. board output capture
2. fixed-point golden generation
3. metrics 계산
4. PNG 저장
5. JSON 저장
6. summary.md 재생성
```

---

## 테스트와 검증

새로 추가/정리한 테스트:

```text
sw/test/test_fir_decimator_capture.py
sw/test/test_fir_decimator_fft_viewer.py
sw/test/test_fir_decimator_metrics.py
sw/test/test_fir_decimator_report.py
sw/test/test_fir_decimator_demo.py
```

`test_fir_decimator_demo.py`는 이제 demo wrapper 동작만 확인한다. capture/viewer/metrics/report 테스트는 각 모듈별 파일로 분리했다.

검증 결과:

```bash
python -m py_compile sw/fir_decimator_capture.py   sw/fir_decimator_fft_viewer.py   sw/fir_decimator_metrics.py   sw/fir_decimator_report.py   sw/fir_decimator_demo.py

.venv/bin/pytest -q sw/test
```

결과:

```text
79 passed
```

---

## 남은 작업

1. 실제 보드에서 report script 실행:

   ```bash
   python sw/fir_decimator_report.py --mode 1-1 --port /dev/ttyUSB1 --timeout 30
   python sw/fir_decimator_report.py --mode 1-2 --port /dev/ttyUSB1 --timeout 30
   ```

2. 생성된 `docs/report/fir_n43/summary.md`, PNG, JSON을 문서화에 반영한다.
3. 필요하면 나중에 raw Q15 `.npy` 저장 또는 CSV export를 추가한다.
4. plot helper가 더 커질 경우에만 `fir_decimator_plot.py` 분리를 재검토한다. 현재는 과한 분리로 판단했다.
