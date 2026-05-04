`timescale 1ns / 1ps
`default_nettype none

module tb_fir_decimator_transposed_n43_axis_top;

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
    fir_decimator_transposed_n43_axis_top #(.TLAST_N(TLAST_N)) dut (
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

        $display("PASS tb_fir_decimator_transposed_n43_axis_top: all scenarios");
        $finish;
    end

endmodule

`default_nettype wire
