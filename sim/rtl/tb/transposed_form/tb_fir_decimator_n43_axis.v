`timescale 1ns / 1ps
`default_nettype none

module tb_fir_decimator_n43_axis;

    localparam integer CLK_HALF  = 5;
    localparam integer TLAST_N   = 512;
    localparam integer IN_LEN    = 8192;
    localparam integer FLUSH_LEN = 42;
    localparam integer EXP_LEN   = 4117;
    localparam integer DRAIN_TO  = 200;

    reg  aclk;
    reg  aresetn;

    reg  s_axis_tvalid;
    wire s_axis_tready;
    reg  signed [15:0] s_axis_tdata;
    reg  s_axis_tlast_in;

    wire        m_axis_tvalid;
    reg         m_axis_tready;
    wire signed [15:0] m_axis_tdata;
    wire        m_axis_tlast;

    reg [15:0] input_mem [0:IN_LEN-1];
    reg [15:0] exp_mem   [0:EXP_LEN-1];

    integer obs_cnt;
    integer check_mode;  // 0=off  1=data  2=data+TLAST
    reg     bp_en;
    integer bp_phase;

    // -------------------------------------------------------------------------
    // DUT
    // -------------------------------------------------------------------------
    fir_decimator_n43_axis #(.TLAST_N(TLAST_N)) dut (
        .aclk         (aclk),
        .aresetn      (aresetn),
        .s_axis_tvalid(s_axis_tvalid),
        .s_axis_tready(s_axis_tready),
        .s_axis_tdata (s_axis_tdata),
        .s_axis_tlast (s_axis_tlast_in),
        .m_axis_tvalid(m_axis_tvalid),
        .m_axis_tready(m_axis_tready),
        .m_axis_tdata (m_axis_tdata),
        .m_axis_tlast (m_axis_tlast)
    );

    // -------------------------------------------------------------------------
    // 클럭
    // -------------------------------------------------------------------------
    initial begin
        aclk = 1'b0;
        forever #(CLK_HALF) aclk = ~aclk;
    end

    // -------------------------------------------------------------------------
    // TREADY 제어 (단일 always block — 다중 드라이버 방지)
    // bp_en=0: tready=1 고정
    // bp_en=1: 3사이클 HIGH, 1사이클 LOW 반복
    // -------------------------------------------------------------------------
    always @(posedge aclk) begin
        if (!aresetn) begin
            bp_phase      <= 0;
            m_axis_tready <= 1'b1;
        end else if (bp_en) begin
            bp_phase      <= (bp_phase == 3) ? 0 : bp_phase + 1;
            m_axis_tready <= (bp_phase < 3);
        end else begin
            bp_phase      <= 0;
            m_axis_tready <= 1'b1;
        end
    end

    // -------------------------------------------------------------------------
    // M_AXIS 모니터: 핸드셰이크 성사(tvalid & tready) 시점에만 비교
    // -------------------------------------------------------------------------
    always @(posedge aclk) begin
        if (aresetn && m_axis_tvalid && m_axis_tready) begin
            if (check_mode >= 1) begin
                if (obs_cnt >= EXP_LEN) begin
                    $display("FAIL: extra output obs_cnt=%0d data=%0d",
                             obs_cnt, $signed(m_axis_tdata));
                    $fatal(1);
                end
                if ($signed(m_axis_tdata) !== $signed(exp_mem[obs_cnt])) begin
                    $display("FAIL: idx=%0d actual=%0d (0x%04h) expected=%0d (0x%04h)",
                             obs_cnt,
                             $signed(m_axis_tdata), m_axis_tdata,
                             $signed(exp_mem[obs_cnt]), exp_mem[obs_cnt]);
                    $fatal(1);
                end
            end
            if (check_mode >= 2) begin
                // TLAST는 512번째, 1024번째... 전송(1-based)에서 1이어야 함
                if (((obs_cnt + 1) % TLAST_N == 0) && !m_axis_tlast) begin
                    $display("FAIL: missing TLAST at obs_cnt=%0d", obs_cnt);
                    $fatal(1);
                end
                if (((obs_cnt + 1) % TLAST_N != 0) && m_axis_tlast) begin
                    $display("FAIL: unexpected TLAST at obs_cnt=%0d", obs_cnt);
                    $fatal(1);
                end
            end
            obs_cnt = obs_cnt + 1;
        end
    end

    // -------------------------------------------------------------------------
    // 태스크
    // -------------------------------------------------------------------------
    task do_reset;
        begin
            aresetn         = 1'b0;
            s_axis_tvalid   = 1'b0;
            s_axis_tdata    = 16'sd0;
            s_axis_tlast_in = 1'b0;
            obs_cnt         = 0;
            repeat (4) @(negedge aclk);
            aresetn = 1'b1;
            @(negedge aclk);
        end
    endtask

    task automatic drive_one;
        input signed [15:0] sample;
        begin
            @(negedge aclk);
            s_axis_tdata  = sample;
            s_axis_tvalid = 1'b1;
            @(posedge aclk);
            while (!s_axis_tready) @(posedge aclk);
        end
    endtask

    task drive_all_samples;
        integer i;
        begin
            for (i = 0; i < IN_LEN; i = i + 1)
                drive_one($signed(input_mem[i]));
            for (i = 0; i < FLUSH_LEN; i = i + 1)
                drive_one(16'sd0);
            @(negedge aclk);
            s_axis_tvalid = 1'b0;
        end
    endtask

    task drain_and_check;
        input integer expected;
        integer d;
        begin
            d = 0;
            while (obs_cnt < expected && d < DRAIN_TO) begin
                @(posedge aclk);
                d = d + 1;
            end
            if (obs_cnt != expected) begin
                $display("FAIL: expected %0d samples, got %0d after %0d drain cycles",
                         expected, obs_cnt, d);
                $fatal(1);
            end
        end
    endtask

    // -------------------------------------------------------------------------
    // 메인 시퀀스
    // -------------------------------------------------------------------------
    initial begin
        $readmemh("sim/vectors/transposed_form/n43/input_q15.hex",          input_mem);
        $readmemh("sim/vectors/transposed_form/n43/expected_decim_q15.hex",  exp_mem);

        bp_en      = 1'b0;
        check_mode = 0;

        // ---- S1: TREADY=1 고정, 데이터 + TLAST 검증 ----
        check_mode = 2;
        bp_en      = 1'b0;
        do_reset;
        drive_all_samples;
        drain_and_check(EXP_LEN);
        $display("PASS [S1] TREADY=1 data+TLAST: %0d samples", obs_cnt);

        // ---- S2: 백프레셔 (3:1 패턴), 데이터 검증 ----
        check_mode = 1;
        bp_en      = 1'b1;
        do_reset;
        drive_all_samples;
        drain_and_check(EXP_LEN);
        bp_en = 1'b0;
        $display("PASS [S2] backpressure: %0d samples", obs_cnt);

        // ---- S3: aresetn 복구 후 정상 출력 ----
        check_mode = 0;
        bp_en      = 1'b0;
        do_reset;
        begin : s3_partial
            integer i;
            for (i = 0; i < 200; i = i + 1)
                drive_one($signed(input_mem[i]));
        end
        @(negedge aclk);
        s_axis_tvalid = 1'b0;
        // 중간 리셋
        aresetn = 1'b0;
        repeat (4) @(negedge aclk);
        aresetn = 1'b1;
        @(posedge aclk);
        if (!s_axis_tready) begin
            $display("FAIL [S3]: s_axis_tready not 1 after aresetn recovery");
            $fatal(1);
        end
        // 처음부터 재구동
        check_mode    = 1;
        obs_cnt       = 0;
        s_axis_tvalid = 1'b0;
        @(negedge aclk);
        drive_all_samples;
        drain_and_check(EXP_LEN);
        $display("PASS [S3] aresetn recovery: %0d samples", obs_cnt);

        $display("PASS tb_fir_decimator_n43_axis: all scenarios");
        $finish;
    end

endmodule

`default_nettype wire
/* superset tb
`timescale 1ns / 1ps
`default_nettype none

module tb_fir_decimator_n43_axis;

    localparam integer CLK_HALF  = 5;
    localparam integer TLAST_N   = 512;
    localparam integer IN_LEN    = 8192;
    localparam integer FLUSH_LEN = 42;
    localparam integer EXP_LEN   = 4117;
    localparam integer DRAIN_TO  = 200;

    reg  aclk;
    reg  aresetn;

    reg  s_axis_tvalid;
    wire s_axis_tready;
    reg  signed [15:0] s_axis_tdata;
    reg  s_axis_tlast_in;

    wire        m_axis_tvalid;
    reg         m_axis_tready;
    wire signed [15:0] m_axis_tdata;
    wire        m_axis_tlast;

    reg [15:0] input_mem [0:IN_LEN-1];
    reg [15:0] exp_mem   [0:EXP_LEN-1];

    // --- 추가된 SV 자료구조 및 타이머 ---
    int expected_q [$];      // Scoreboard Queue
    int obs_cnt;             // 누적 관측 개수
    int timeout_cnt;         // Watchdog 카운터

    integer check_mode;      // 0=off  1=data  2=data+TLAST
    reg  bp_en;              // 무작위 백프레셔 활성화 플래그
    int  bp_prob = 30;       // TREADY가 1일 확률 (%)

    // -------------------------------------------------------------------------
    // DUT 인스턴스
    // -------------------------------------------------------------------------
    fir_decimator_n43_axis #(.TLAST_N(TLAST_N)) dut (
        .aclk         (aclk),
        .aresetn      (aresetn),
        .s_axis_tvalid(s_axis_tvalid),
        .s_axis_tready(s_axis_tready),
        .s_axis_tdata (s_axis_tdata),
        .s_axis_tlast (s_axis_tlast_in),
        .m_axis_tvalid(m_axis_tvalid),
        .m_axis_tready(m_axis_tready),
        .m_axis_tdata (m_axis_tdata),
        .m_axis_tlast (m_axis_tlast)
    );

    // -------------------------------------------------------------------------
    // 클럭 생성
    // -------------------------------------------------------------------------
    initial begin
        aclk = 1'b0;
        forever #(CLK_HALF) aclk = ~aclk;
    end

    // -------------------------------------------------------------------------
    // TREADY 제어 (무작위 백프레셔 주입)
    // -------------------------------------------------------------------------
    always @(posedge aclk) begin
        if (!aresetn) begin
            m_axis_tready <= 1'b0;
        end else if (bp_en) begin
            // 0~99 사이의 난수를 생성하여 지정된 확률로 TREADY=1
            m_axis_tready <= ($urandom_range(0, 99) < bp_prob);
        end else begin
            m_axis_tready <= 1'b1;
        end
    end

    // -------------------------------------------------------------------------
    // 워치독 타이머 (Deadlock 방지)
    // -------------------------------------------------------------------------
    always @(posedge aclk) begin
        if (!aresetn) begin
            timeout_cnt <= 0;
        end else begin
            if (m_axis_tvalid && m_axis_tready) begin
                timeout_cnt <= 0; // 전송 성공 시 타이머 리셋
            end else begin
                timeout_cnt <= timeout_cnt + 1;
            end

            if (timeout_cnt > 1000) begin
                $display("FATAL: Watchdog Timeout! System in deadlock.");
                $fatal(1);
            end
        end
    end

    // -------------------------------------------------------------------------
    // M_AXIS 스코어보드 모니터 (동적 검증)
    // -------------------------------------------------------------------------
    always @(posedge aclk) begin
        if (aresetn && m_axis_tvalid && m_axis_tready) begin
            if (check_mode >= 1) begin
                // 큐가 비어있는데 출력이 나오면 오동작
                if (expected_q.size() == 0) begin
                    $display("FAIL: Extra output detected at obs_cnt=%0d data=%0d", 
                             obs_cnt, $signed(m_axis_tdata));
                    $fatal(1);
                end
                
                // 정답 Pop 및 비교
                begin
                    int exp_val = expected_q.pop_front();
                    if ($signed(m_axis_tdata) !== $signed(exp_val)) begin
                        $display("FAIL: Mismatch at obs_cnt=%0d. Actual=%0d Expected=%0d",
                                 obs_cnt, $signed(m_axis_tdata), $signed(exp_val));
                        $fatal(1);
                    end
                end
            end
            
            if (check_mode >= 2) begin
                // TLAST 타이밍 검증
                if (((obs_cnt + 1) % TLAST_N == 0) && !m_axis_tlast) begin
                    $display("FAIL: Missing TLAST at obs_cnt=%0d", obs_cnt);
                    $fatal(1);
                end
                if (((obs_cnt + 1) % TLAST_N != 0) && m_axis_tlast) begin
                    $display("FAIL: Unexpected TLAST at obs_cnt=%0d", obs_cnt);
                    $fatal(1);
                end
            end
            obs_cnt++;
        end
    end

    // -------------------------------------------------------------------------
    // 태스크 (Task)
    // -------------------------------------------------------------------------
    task automatic do_reset;
        begin
            aresetn         = 1'b0;
            s_axis_tvalid   = 1'b0;
            s_axis_tdata    = 16'sd0;
            s_axis_tlast_in = 1'b0;
            obs_cnt         = 0;
            expected_q.delete(); // 스코어보드 초기화
            repeat (4) @(negedge aclk);
            aresetn = 1'b1;
            @(negedge aclk);
        end
    endtask

    task automatic drive_one(input signed [15:0] sample, input int max_bubble);
        begin
            // 무작위 버블(Bubble) 주입 - Idle 상태일 때만 지연
            if (max_bubble > 0) begin
                s_axis_tvalid = 1'b0; 
                repeat($urandom_range(0, max_bubble)) @(posedge aclk);
            end

            s_axis_tdata  = sample;
            s_axis_tvalid = 1'b1;
            
            @(posedge aclk);
            while (!s_axis_tready) @(posedge aclk);
        end
    endtask

    task automatic drive_all_samples(input int max_bubble);
        integer i;
        begin
            for (i = 0; i < IN_LEN; i++) begin
                drive_one($signed(input_mem[i]), max_bubble);
            end
            for (i = 0; i < FLUSH_LEN; i++) begin
                drive_one(16'sd0, max_bubble);
            end
            s_axis_tvalid = 1'b0;
        end
    endtask

    task automatic drain_and_check();
        integer d = 0;
        begin
            // 큐가 다 비워질 때까지(모든 결과가 나올 때까지) 대기
            while (expected_q.size() > 0 && d < DRAIN_TO) begin
                @(posedge aclk);
                d++;
            end
            if (expected_q.size() != 0) begin
                $display("FAIL: Queue not empty. Missing %0d expected outputs.", expected_q.size());
                $fatal(1);
            end
        end
    endtask

    // -------------------------------------------------------------------------
    // 메인 시퀀스
    // -------------------------------------------------------------------------
    initial begin
        // 랜덤 시드 설정 (필요 시 vsim -sv_seed <번호> 로 재현 가능)
        $display("Start Testbench (Seed: %0d)", $get_initial_random_seed());

        $readmemh("sim/vectors/transposed_form/n43/input_q15.hex",  input_mem);
        $readmemh("sim/vectors/transposed_form/n43/expected_decim_q15.hex", exp_mem);

        bp_en = 1'b0;
        check_mode = 0;

        // ---- S1: Happy Path (No backpressure, No bubbles) ----
        check_mode = 2;
        bp_en      = 1'b0;
        do_reset;
        for(int i=0; i<EXP_LEN; i++) expected_q.push_back(exp_mem[i]); // 큐에 정답 적재
        drive_all_samples(0); // max_bubble = 0
        drain_and_check();
        $display("PASS [S1] Happy Path: %0d samples", obs_cnt);

        // ---- S2: Stress Test (Random Backpressure & Bubbles) ----
        check_mode = 1;
        bp_en      = 1'b1;
        bp_prob    = 30; // 30% 확률로 데이터 Accept
        do_reset;
        for(int i=0; i<EXP_LEN; i++) expected_q.push_back(exp_mem[i]);
        drive_all_samples(3); // 최대 3사이클의 무작위 입력 버블
        drain_and_check();
        bp_en = 1'b0;
        $display("PASS [S2] Random Stress Test: %0d samples", obs_cnt);

        // ---- S3: Reset Recovery ----
        check_mode = 0;
        bp_en      = 1'b0;
        do_reset;
        for (int i = 0; i < 200; i++) begin
            drive_one($signed(input_mem[i]), 0);
        end
        @(negedge aclk);
        s_axis_tvalid = 1'b0;
        
        // Mid-operation Reset
        aresetn = 1'b0;
        repeat (4) @(negedge aclk);
        aresetn = 1'b1;
        @(posedge aclk);
        
        check_mode = 1;
        do_reset;
        for(int i=0; i<EXP_LEN; i++) expected_q.push_back(exp_mem[i]);
        drive_all_samples(1); 
        drain_and_check();
        $display("PASS [S3] Reset Recovery: %0d samples", obs_cnt);

        $display("PASS All Scenarios Successfully.");
        $finish;
    end

endmodule
`default_nettype wire
*/