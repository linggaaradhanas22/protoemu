// EVAL-017: directed checks for the wait-slot probe. Override TIMEOUT with -P.
`timescale 1ns / 1ps
module wait_timeout_probe_tb;
    parameter TIMEOUT = 1;
    reg clk = 0, rst_n = 0, flush = 0, level = 1, guarded = 0;
    reg [23:0] cycle = 0, target = 0;
    reg [7:0] pins = 0;
    reg [1:0] arm = 0, consume = 0;
    reg [2:0] pinsel = 3;
    reg [15:0] tmo = 0;
    wire [1:0] done, expired;
    wire [47:0] stamp;
    integer errors = 0, at;
    wait_timeout_probe #(.TIMEOUT(TIMEOUT)) dut (clk, rst_n, flush, cycle, pins, arm, consume, target, level,
                                                 guarded, pinsel, tmo, done, expired, stamp);
    always #5 clk = ~clk;
    always @(posedge clk) cycle <= cycle + 1;

    // Arm slot 0, run until done or a limit, and return the cycle it finished.
    task trial(input g, input [23:0] t, input [15:0] m, input integer rise_at, input expect_expired,
               input integer expect_at);
        begin
            @(negedge clk); consume = 1; @(negedge clk); consume = 0;
            pins = 0; guarded = g; target = cycle + t; tmo = m; arm = 1;
            @(negedge clk); arm = 0;
            at = -1;
            repeat (8000) begin
                @(negedge clk);
                if (rise_at >= 0 && cycle >= target - t + rise_at) pins[3] = 1;
                if (done[0] && at < 0) at = cycle;
            end
            if (at < 0 || expired[0] !== expect_expired || (expect_at >= 0 && (at - (target - t)) !== expect_at)) begin
                errors = errors + 1;
                $display("trial g=%0d t=%0d tmo=%0d: done at %0d (offset %0d), expired %b", g, t, m, at,
                         at - (target - t), expired[0]);
            end
        end
    endtask

    initial begin
        @(negedge clk) rst_n = 1;
        if (TIMEOUT == 1) begin
            trial(1, 20, 2, -1, 1, 20 + 128 + 1);  // Guard opens at 20, expires 128 later.
            trial(1, 20, 2, 50, 0, -1);            // Level arrives before expiry.
        end else if (TIMEOUT == 2) begin
            trial(0, 300, 1, -1, 1, 300 + 1);      // Unguarded: expires at the given cycle.
            trial(0, 300, 1, 100, 0, -1);
            trial(1, 20, 0, 50, 0, -1);            // Guarded waits still work.
        end
        $display("wait_timeout_probe_tb TIMEOUT=%0d: %0d errors", TIMEOUT, errors);
        $finish;
    end
endmodule
