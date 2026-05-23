# 28. AXI-Stream TB 업데이트 — log 25 RTL 재설계 반영

- 작성일: 2026-05-14
- 선행 문서: `25_axi_stream_tlast_deadlock_troubleshooting.md`, `18_axis_buffer_overflow_fix_and_tb_robustness.md`

---

## 배경

log 25에서 `fir_decimator_n43_axis.v`를 전면 재설계했다 (하드코딩 TLAST_N 제거 → 동적 TLAST + auto-flush 상태 머신). 그러나 TB(`tb_fir_decimator_n43_axis.sv`)는 log 18 버전에 머물러 있어, 새 RTL의 핵심 기능을 실제로 검증하지 못하는 상태였다.

bottom-up 재검증(workflow_v13 Step A) 과정에서 이 불일치를 발견하고 TB를 전면 업데이트했다.

---

## 구 TB의 문제점

### 문제 1: 없어진 파라미터 참조

```systemverilog
// 구 TB
localparam integer TLAST_N = 512;
fir_decimator_n43_axis #(.TLAST_N(TLAST_N)) dut ( ... );
```

log 25 재설계에서 `TLAST_N` 파라미터는 RTL에서 삭제됐다. 파라미터 오버라이드가 무시되므로 컴파일은 되지만 의도와 다르게 동작할 수 있다.

### 문제 2: `s_axis_tlast` 미구동

```systemverilog
// 구 TB — drive_all_samples 내부
for (int i = 0; i < IN_LEN; i++)
    drive_one($signed(input_mem[i]), max_bubble);  // tlast 인자 없음
for (int i = 0; i < FLUSH_LEN; i++)
    drive_one(16'sd0, max_bubble);                 // 수동 0 주입
```

`s_axis_tlast_in`을 어디서도 1로 올리지 않는다. RTL의 auto-flush 상태 머신은 `s_axis_tlast`를 수신해야 활성화되므로, 핵심 기능이 전혀 테스트되지 않는다.

### 문제 3: 수동 flush로 하드웨어 auto-flush 우회

FLUSH_LEN=42개의 0을 수동으로 주입해서 파이프라인을 비워줬다. 이는 log 18 시절(TLAST_N 하드코딩) 방식이고, log 25에서 하드웨어가 이 역할을 맡는다. TB가 수동 flush를 하면 새 RTL의 auto-flush 경로가 검증되지 않는다.

### 문제 4: TLAST 체크 로직 불일치

```systemverilog
// 구 TB — 구 RTL(TLAST_N=512) 기준
if (((obs_cnt + 1) % TLAST_N == 0) && !m_axis_tlast) ...  // 512샘플마다 TLAST 기대
```

새 RTL은 패킷 끝(`s_axis_tlast` 수신)에 `target_out_cnt`를 계산해 딱 한 번 TLAST를 생성한다. 8192입력 기준으로 4096번째 출력(obs_cnt=4095)에서 한 번만 TLAST가 나와야 한다. 구 체크 로직은 obs_cnt=511에서 TLAST를 기대하므로 새 RTL 실행 시 즉시 FAIL한다.

### 문제 5: EXP_LEN 오설정

```systemverilog
localparam integer EXP_LEN = 4117;  // IN_LEN(8192) + FLUSH_LEN(42) → 4117 outputs
```

수동 flush 42개까지 포함한 값이다. 새 RTL은 8192입력 → 정확히 4096출력만 생성한다.

---

## 수정 내용

### 제거

- `TLAST_N`, `FLUSH_LEN` localparam
- `#(.TLAST_N(TLAST_N))` DUT 파라미터 오버라이드
- `drive_all_samples` 태스크 (수동 flush 포함)

### 변경

| 항목 | 구 | 신 |
|---|---|---|
| `EXP_LEN` | 4117 | 4096 |
| `DRAIN_TO` | 200 | 10000 |
| watchdog 임계 | 1000 사이클 | 3000 사이클 |

### 추가: `drive_one` tlast 인자

```systemverilog
task automatic drive_one(input logic signed [15:0] sample,
                         input int max_bubble, input logic tlast);
    if (max_bubble > 0) begin
        @(negedge aclk);
        s_axis_tvalid   = 1'b0;
        s_axis_tlast_in = 1'b0;  // 버블 구간에 tlast 클리어
        repeat ($urandom_range(0, max_bubble)) @(posedge aclk);
    end
    @(negedge aclk);
    s_axis_tdata    = sample;
    s_axis_tvalid   = 1'b1;
    s_axis_tlast_in = tlast;
    @(posedge aclk);
    while (!s_axis_tready) @(posedge aclk);
endtask
```

### 추가: `drive_packet` (auto-flush 전용)

```systemverilog
task automatic drive_packet(input int max_bubble);
    for (int i = 0; i < IN_LEN; i++)
        drive_one($signed(input_mem[i]), max_bubble, (i == IN_LEN - 1));
    @(negedge aclk);
    s_axis_tvalid   = 1'b0;
    s_axis_tlast_in = 1'b0;
endtask
```

마지막 샘플(i=IN_LEN-1)에서만 `s_axis_tlast=1`. 이후는 RTL auto-flush에 전적으로 위임한다.

### 변경: TLAST 체크 로직

```systemverilog
// 신 TB — 4096번째 출력에서 정확히 한 번 TLAST
if (obs_cnt == EXP_LEN - 1 && !m_axis_tlast) begin
    $display("FAIL: missing TLAST at obs_cnt=%0d", obs_cnt);  $fatal(1);
end
if (obs_cnt < EXP_LEN - 1 && m_axis_tlast) begin
    $display("FAIL: unexpected TLAST at obs_cnt=%0d", obs_cnt);  $fatal(1);
end
```

---

## 기댓값 벡터 호환성

`expected_decim_q15.hex`는 4117줄이지만 신 TB는 `exp_mem[0:4095]`(4096엔트리)만 선언한다. `$readmemh`는 첫 4096엔트리만 읽고 나머지는 경고(WARNING)를 출력한다. 이는 의도된 동작이며 결과에 영향 없다.

첫 4096 기댓값은 수동 flush 방식과 auto-flush 방식에서 동일하다. 출력 k(k=0..4095)는 `y[k] = Σ h[j]·x[2k-j]`이며, x[0]..x[8190]만 참조한다(최소 인덱스: 8190-42=8148). flush 방식은 이 값에 영향을 주지 않는다.

---

## 시나리오 및 결과

| 시나리오 | 내용 | 결과 |
|---|---|---|
| S1 | TREADY=1 고정, 데이터+TLAST 검증 | ✅ PASS (4096샘플) |
| S2 | 30% 다운스트림 백프레셔 + 업스트림 버블, 데이터+TLAST 검증 | ✅ PASS (4096샘플) |
| S3 | 스트리밍 중 aresetn 인가 후 재구동, 데이터+TLAST 검증 | ✅ PASS (4096샘플) |

```
make clean && make run_all 결과:
PASS [S1] TREADY=1 data+TLAST: 4096 samples
PASS [S2] Random Backpressure + Bubble: 4096 samples
PASS [S3] Reset Recovery: 4096 samples
PASS tb_fir_decimator_n43_axis: all scenarios
```

5개 TB 전부 PASS.

---

## 핵심 교훈

**RTL을 재설계하면 TB를 즉시 같이 업데이트해야 한다.** log 25 재설계 이후 TB가 방치되면서, 약 3일간 핵심 기능(dynamic TLAST, auto-flush)이 전혀 검증되지 않은 상태로 남아 있었다. TB가 컴파일되고 PASS하더라도, RTL의 동작 방식과 TB의 전제가 어긋나면 의미 없는 테스트가 된다.
