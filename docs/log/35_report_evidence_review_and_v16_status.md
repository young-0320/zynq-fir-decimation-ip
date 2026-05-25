# 35. Report evidence review와 workflow v16 마무리 상태

- 작성일: 2026-05-26
- 선행 문서:
  - `34_python_demo_report_modularization.md`
  - `../workflow/workflow_v16.md`
- 관련 커밋:
  - `8ec72dd` `Improve FIR demo FFT visualization`
  - `7a793d6` `Remove report all mode`
  - `1c8fbf9` `Write per-scenario report summaries`
  - `eb5dd3b` `Simplify report summary filenames`
  - `89d59ab` `Expand report scenario summaries`

---

## 결론

오늘 작업은 Python demo/report polish의 구현 측면에서는 대부분 마무리 단계까지 왔다. 다만 `docs/report/fir_n43` 산출물을 최종 evidence로 커밋하기 전에는 한 가지 해석 리스크를 더 정리해야 한다.

핵심 리스크는 scenario 1-1의 출력 FFT bin overlap이다.

```text
input 20 MHz -> output fs=50 MHz 기준 20 MHz
input 30 MHz -> output fs=50 MHz 기준 20 MHz
```

따라서 `scenario1_1`의 tone-level FFT peak table에서 20 MHz와 30 MHz가 같은 output bin을 공유한다. 현재 sample-domain board-vs-golden 비교는 PASS로 해석해도 되지만, tone-level row만 보면 30 MHz stopband 성분이 독립적으로 측정된 것처럼 오해할 수 있다.

즉, report 산출물 구조와 링크는 정상이나, 최종 커밋 전에는 shared output bin을 summary/metrics에 명시하거나 해당 tone-level verdict를 보수적으로 다루는 개선이 필요하다.

---

## 오늘 완료한 작업

### FFT viewer 개선

`sw/fir_decimator_fft_viewer.py`는 presentation-quality demo viewer에 가까워졌다.

완료한 항목:

- input/output FFT 축 정책 분리
- output FFT는 표시 축을 0-50 MHz로 맞추되 25-50 MHz를 invalid/comparison-only 영역으로 shade
- output alias marker 반영
- 25 MHz Nyquist edge 표시
- plot title 정리
  - figure title: scenario와 tone list 중심
  - subtitle: FIR pass/transition/stop band와 output valid/shaded band
  - subplot title: 각 FFT의 `fs`, `Nyq`
- plot tuning 상수 상단 배치
- passband/stopband boundary line을 input FFT에 표시
- scenario 2는 one-shot 동작으로 고정
- scenario 2 입력 계약을 docs 기준으로 복구
  - `1 MHz <= f < 50 MHz`
  - 최대 8 tones
  - 50 MHz 이상 reject

### report pipeline 정책 정리

`sw/fir_decimator_report.py`는 board reset 현실에 맞게 단일 scenario 실행만 지원하도록 정리했다.

완료한 항목:

- `--mode all` 제거
- `--mode {1-1,1-2}`만 허용
- scenario마다 board reset 후 따로 실행하는 정책으로 변경
- `summary/` 폴더 아래 scenario별 Markdown 생성

현재 산출 구조:

```text
docs/report/fir_n43/
  plot/
    scenario1_1_fft.png
    scenario1_2_fft.png
  metrics/
    scenario1_1_metrics.json
    scenario1_2_metrics.json
  summary/
    scenario1_1.md
    scenario1_2.md
```

### Markdown summary 확장

초기 summary는 너무 축약형이었다. 이제 scenario별 summary에는 다음 내용을 포함한다.

- sample-domain board-vs-golden metrics
  - compared samples
  - max/mean/RMSE error
  - SNR
  - correlation
  - saturation count
  - latency/trim metadata
- tone-level board-vs-golden FFT peak table
  - input tone
  - region
  - expected output frequency
  - input peak
  - board peak
  - golden peak
  - board-golden delta
  - board/golden attenuation
  - verdict
- notes
  - board reset limitation
  - transition-band tones are INFO

표와 본문은 영어 중심으로 유지한다. 프로젝트 대화와 보조 설명은 한국어로 하되, report artifact는 JSON key/metric 용어와 맞추기 위해 영어를 기본으로 한다.

---

## docs/report/fir_n43 산출물 검토 결과

현재 생성된 파일:

```text
docs/report/fir_n43/metrics/scenario1_1_metrics.json
docs/report/fir_n43/metrics/scenario1_2_metrics.json
docs/report/fir_n43/plot/scenario1_1_fft.png
docs/report/fir_n43/plot/scenario1_2_fft.png
docs/report/fir_n43/summary/scenario1_1.md
docs/report/fir_n43/summary/scenario1_2.md
```

확인한 사항:

- PNG 파일은 존재하며 정상 PNG로 인식된다.
- summary의 상대 링크는 PNG/JSON 파일을 올바르게 가리킨다.
- scenario 1-1 sample-domain 결과:
  - overall: PASS
  - max_abs_error_lsb: 6
  - RMSE: 1.403 LSB
  - SNR: 74.863 dB
  - correlation: 1.000000
- scenario 1-2 sample-domain 결과:
  - overall: PASS
  - max_abs_error_lsb: 7
  - RMSE: 1.805 LSB
  - SNR: 72.216 dB
  - correlation: 1.000000

해석상 주의:

- scenario 1-1의 20 MHz transition tone과 30 MHz stopband tone은 output 20 MHz bin을 공유한다.
- 현재 board와 golden은 그 공유 bin에서 매우 잘 일치한다.
- 그러나 tone-level table이 30 MHz stopband 단독 감쇠를 증명한다고 읽히면 부정확하다.
- 최종 evidence commit 전 shared-bin/overlap 표시를 추가해야 한다.

---

## workflow v16 기준 상태

`workflow_v16.md`의 주요 목표별 상태는 다음과 같다.

| v16 항목 | 상태 | 판단 |
| --- | --- | --- |
| Clean FFT visualization | 거의 완료 | viewer plot은 제목, 축, marker, invalid 영역, pass/stop 경계까지 정리됨 |
| Numeric peak/attenuation summaries | 부분 완료 | report summary/JSON에는 있음. live viewer console 출력은 별도 compact table로는 아직 없음 |
| Board output vs Python reference | 완료 | metrics/report가 fixed-point golden과 sample/tone-domain 비교 수행 |
| Saved evidence under docs | 진행 중 | 산출물은 생성됐지만 shared-bin 이슈 정리 전이라 아직 최종 커밋 보류 |
| Final demo commands/PASS criteria 문서화 | 부분 완료 | log 34/35에는 정리됨. README 또는 최종 사용 문서 반영은 남음 |
| Scenario 3 결정 | 완료 | 현재는 추가하지 않는 방향이 맞음 |

따라서 오늘 할 일을 모두 끝냈다고 말하기에는 이르다. 코드 구현과 테스트는 상당 부분 완료됐지만, v16 completion criteria 관점에서는 최종 evidence와 최종 사용자 문서화가 아직 남았다.

---

## 남은 작업

1. shared output bin 처리

   `tone_metrics` 또는 Markdown summary에서 같은 `expected_output_mhz`를 공유하는 tone들을 표시한다.

   가능한 정책:

   ```text
   output_bin_sources_mhz = "20, 30"
   attribution = "shared-bin"
   verdict = INFO 또는 PASS_WITH_SHARED_BIN_NOTE
   ```

   권장: sample-domain overall PASS는 유지하되, shared bin tone row는 hard PASS처럼 보이지 않도록 `INFO` 또는 별도 note를 붙인다.

2. report 재생성

   보드 reset을 scenario마다 수행한다.

   ```bash
   .venv/bin/python sw/fir_decimator_report.py --mode 1-1 --port /dev/ttyUSB1
   # board reset
   .venv/bin/python sw/fir_decimator_report.py --mode 1-2 --port /dev/ttyUSB1
   ```

3. 산출물 재검토

   - `summary/scenario1_1.md`
   - `summary/scenario1_2.md`
   - `metrics/*.json`
   - `plot/*.png`

   위 파일들이 shared-bin 해석까지 반영하는지 확인한다.

4. 최종 evidence commit

   shared-bin 표현이 정리된 뒤 `docs/report/fir_n43` 산출물을 의도적으로 커밋한다.

5. 최종 command/PASS criteria 문서화

   README 또는 최종 workflow/usage 문서에 다음을 반영한다.

   - live demo command
   - report command
   - board reset requirement
   - pass/transition/stopband 기준
   - INFO/WARN/PASS 의미

---

## 현재 판단

- RTL/BOOT/baremetal 쪽을 더 건드릴 필요는 없다.
- Python viewer/report 쪽 구조는 대체로 안정됐다.
- 최종 마무리 전 가장 중요한 것은 새로운 기능 추가가 아니라 report 해석을 더 정직하게 만드는 것이다.
- 특히 overlapping output bin은 교수/리뷰어가 질문할 가능성이 높은 지점이므로, 이것을 먼저 명시하고 산출물을 다시 생성해야 한다.
