# 18. AXI-Stream Output Buffer Overflow Fix and TB Robustness

- 작성일: 2026-05-05
- 단계: 10
- 목적: 랜덤 백프레셔 스트레스 테스트가 노출한 출력 버퍼 오버플로 버그를 수정하고 TB를 강건하게 재작성
- 선행 문서: `docs/log/17_axi_stream_wrapper_design_decisions.md`

## 1. 배경

Step 5-2 목표는 AXI-Stream 래퍼의 버그 수정 및 TB 강건성 강화다. 기존 TB는 happy path 위주의 검증만 수행했다. 이를 강건하게 재작성하는 과정에서, 기존 TB가 발견하지 못했던 실제 RTL 버그가 드러났다.

---

## 2. TB 재작성 — NBA 버그 및 기타 이슈

기존 `.v` TB에는 task 내부에서 non-blocking assignment(`<=`)를 사용하는 패턴이 있었다.

```verilog
// 잘못된 패턴 (task 내부)
in_valid <= 1'b1;
in_sample <= sample;
@(posedge clk);
```

`initial` 블록에서 호출하는 task에서 `<=`를 쓰면 NBA update region에서 값이 반영된다. `always @(posedge clk)` 모니터는 같은 posedge의 active region에서 평가되므로, 드라이브한 값이 1 클럭 늦게 DUT에 보인다.

수정: task 내 모든 stimulus는 `=` (blocking) + `@(negedge clk)` 앵커로 통일한다.

그 외 확인된 이슈:

| 이슈 | 영향 |
|------|------|
| drain loop에 timeout 없음 (`tb_fir_decimator_n43`) | 버그 시 시뮬레이션 무한 hang |
| watchdog 없음 (`tb_fir_decimator_n43`) | driving 중 파이프라인 stall 감지 불가 |
| `int` 변수를 `always` 블록 내부에서 선언 | static lifetime always 블록에서 기술적 비정상 |
| `expected_mem` push 시 `$signed()` 누락 | 16-bit unsigned → 32-bit int 변환 시 부호 불일치로 모든 음수 샘플 FAIL |
| `$get_initial_random_seed()` 사용 | iverilog 미지원 |

모든 TB를 `.sv`로 확장자 변경하고 위 이슈를 수정했다. 추가된 기능:
- Scoreboard 큐 (`int expected_q[$]`): pop_front 방식으로 순서 검증
- Watchdog timer: 1000 사이클 비활성 시 fatal
- S2 랜덤 버블: `$urandom_range`로 0~3 사이클 입력 갭 무작위 주입

---

## 3. AXI-Stream 버그 발견

`tb_fir_decimator_n43_axis.sv` S2 시나리오 (무작위 TREADY 30%, 입력 버블)에서 실패:

```
FAIL tb_fir_decimator_n43_axis: idx=288 actual=-5061 expected=-9830
```

`actual`과 `expected`가 완전히 다른 값이다. 부호 불일치가 아닌 실제 데이터 손실이다. S1 (TREADY=1 고정)은 통과했으므로 DUT 연산 자체는 정상이다. 30% TREADY 백프레셔 조건에서만 출력 샘플이 DROP되는 상황이다.

---

## 4. 버그 원인 분석

**핵심: `s_axis_tready = ~valid2`의 1-cycle 전파 지연**

출력 버퍼에서 `valid2`는 registered 신호다. `s_axis_tready`는 `assign s_axis_tready = ~valid2`로 combinational하게 연결되어 있으나, `valid2`가 NBA update region에서 0→1로 바뀌는 posedge의 active region에서는 여전히 `valid2_old = 0`이다.

```
posedge K (active region):  valid2_old = 0 → s_axis_tready = 1 → in_valid = 1  ← 1개 샘플 누출
posedge K (NBA region):     valid2 ← 1
posedge K+1 (active region): s_axis_tready = ~1 = 0  (입력 차단)
```

버퍼가 full 상태(valid0=1, valid1=1, valid2=1)가 되는 시점에, 이미 1개 샘플이 FIR에 진입해 있다. 이 샘플은 2-stage 파이프라인 + M=2 decimation을 거쳐 posedge K+2에서 `core_out_valid=1`로 나온다.

이때 버퍼가 여전히 full이면 해당 출력은 어디에도 저장되지 못하고 **silently drop**된다:

```verilog
else if (core_out_valid) begin
    if (!valid0)      valid0 <= 1; // 이미 1
    else if (!valid1) valid1 <= 1; // 이미 1
    else if (!valid2) valid2 <= 1; // 이미 1
    // else: 조건 없음 → 출력 소실
end
```

TREADY가 30% 확률이면 K+1에서 transfer가 일어나지 않을 확률이 70%다. K+2까지 연속으로 transfer가 없을 확률은 0.7² = 49%로, 재현성이 높다.

기존 분석 (`s_axis_tready = ~valid2`, depth-3이 충분하다는 근거)은 오류였다. `~valid2` 기준으로 backpressure가 걸리는 시점은 이미 버퍼 3슬롯이 전부 찬 직후이므로, 누출된 in-flight 출력을 흡수할 여유가 없다.

---

## 5. 수정

**`fir_decimator_n43_axis.v`**

```verilog
// 수정 전
assign s_axis_tready = ~valid2;

// 수정 후
assign s_axis_tready = ~valid1;
```

`valid1`이 찰 때 입력을 차단하면, backpressure 전환 직후 누출된 1개 샘플의 in-flight 출력이 `valid2`(빈 슬롯)에 흡수된다.

동작 검증:

| 시점 | 버퍼 상태 | 이벤트 |
|------|-----------|--------|
| posedge M (active) | [1,0,0] | `core_out_valid` → valid1 NBA 예정. `s_axis_tready=~valid1_old=1`. 1샘플 누출 |
| posedge M+1 | [1,1,0] | `s_axis_tready=0`. 입력 차단. `core_out_valid=0` (dec phase=1) |
| posedge M+2 | [1,1,0] | 누출 샘플의 FIR 출력. `core_out_valid=1` → valid2 채움 |
| 결과 | [1,1,1] | 버퍼 full이지만 오버플로 없음 ✓ |

TREADY=1 고정(S1) 조건에서는 M=2 decimation으로 2 사이클에 1개 출력이 나오고, transfer도 매 사이클 일어나므로 valid1이 거의 채워지지 않는다. 기존 S1 동작에 영향 없음.

---

## 6. 검증 결과

```
PASS [S1] Happy Path: 8234 samples          (tb_fir_n43)
PASS [S2] Random Bubble: 8234 samples       (tb_fir_n43)
PASS [S1] Happy Path: 4117 samples          (tb_fir_decimator_n43)
PASS [S2] Random Bubble: 4117 samples       (tb_fir_decimator_n43)
PASS [S1] TREADY=1 data+TLAST: 4117 samples (tb_fir_decimator_n43_axis)
PASS [S2] Random Backpressure + Bubble: 4117 samples
PASS [S3] Reset Recovery: 4117 samples
PASS tb_fir_decimator_n43_axis: all scenarios
```

---

## 7. 의미

이번 버그는 기존 TB의 deterministic 3:1 backpressure 패턴으로는 재현되지 않는 조건이었다. 75% TREADY에서는 2 사이클 내 transfer가 일어날 확률이 높아 in-flight 출력이 드레인되기 때문이다. 30% 무작위 TREADY로 전환하자 49% 확률로 재현 가능한 버그가 됐다.

버그의 본질은 설계 단계의 분석 오류다. "depth-3이 안전하다"는 근거는 `~valid2` 기준 stall이 이미 버퍼를 다 채운 시점에서 발동한다는 사실을 간과했다. `~valid1`으로 1슬롯 일찍 stall하면 `valid2`가 in-flight 출력의 완충 역할을 한다. 이 수정으로 임의의 TREADY 패턴에 대해 데이터 무손실이 보장된다.
