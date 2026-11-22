`timescale 1ns/1ps
module capture_expiry_probe_tb;
    reg clk=0, rst_n=0, flush=0, ctx=0, arm=0, consume=0, level=1, guarded=1;
    reg [23:0] cycle=0, target=0;
    reg [7:0] pins=0;
    reg [2:0] pin=0;
    reg [1:0] mode=1, polarity=2;
    reg [15:0] timeout=0;
    wire [1:0] a_ready, b_ready;
    wire a_occ, b_occ, a_bit, b_bit, a_exp, b_exp;
    wire [23:0] a_stamp, b_stamp;
    wire [23:0] expiry = target + {2'b0, timeout, 6'b0};
    integer cases=0, ticks=0, c, s;

    full_core_capture a(clk, rst_n, flush, cycle, target, pins, ctx, arm, consume, pin, mode, polarity,
                       level, guarded, timeout, a_ready, a_occ, a_bit, a_exp, a_stamp);
    capture_expiry_probe b(clk, rst_n, flush, cycle, target, expiry, pins, ctx, arm, consume, pin,
                           mode, polarity, level, guarded, |timeout, b_ready, b_occ, b_bit, b_exp, b_stamp);

    task tick;
        begin
            #1; clk=1; #1;
            if ({a_ready,a_occ,a_exp} !== {b_ready,b_occ,b_exp} ||
                (a_ready[ctx] && !a_exp && {a_bit,a_stamp} !== {b_bit,b_stamp}))
                $fatal(1, "capture variants differ on edge %h, context %0d", cycle, ctx);
            clk=0; cycle=cycle+1'b1; ticks=ticks+1;
        end
    endtask

    task timed_case;
        input [23:0] start_at;
        input integer distance, match_tick;
        input [15:0] units;
        integer t, expected, observe_at;
        reg [23:0] expected_stamp;
        reg expect_expiry;
        begin
            flush=1; tick; flush=0;
            cycle=start_at; target=start_at+distance; pins=0; timeout=units;
            arm=1; tick; arm=0;
            observe_at=match_tick < distance ? distance : match_tick;
            expect_expiry=units!=0 && observe_at>distance+64*units;
            expected=expect_expiry ? distance+64*units : observe_at;
            expected_stamp=start_at+expected;
            for (t=1; t<=expected; t=t+1) begin
                if (t==match_tick) pins[pin]=1;
                tick;
                if (a_ready[ctx] !== (t==expected)) $fatal(1, "wrong ready edge %0d, expected %0d", t, expected);
            end
            if (a_exp !== expect_expiry || (!a_exp && a_stamp !== expected_stamp))
                $fatal(1, "wrong timeout/match result");
            consume=1; tick; consume=0;
            if (|a_ready || a_occ) $fatal(1, "consume did not clear slot");
            cases=cases+1;
        end
    endtask

    initial begin
        tick; rst_n=1;
        for (c=0; c<2; c=c+1) begin
            ctx=c; pin=c+2;
            for (s=0; s<2; s=s+1) begin
                timed_case(s ? 24'hfffff0 : 24'd100, 8, 2, 1);
                timed_case(s ? 24'hfffff0 : 24'd100, 8, 72, 1);
                timed_case(s ? 24'hfffff0 : 24'd100, 8, 73, 1);
                timed_case(s ? 24'hfffff0 : 24'd100, -4, 60, 1);
                timed_case(s ? 24'hfffff0 : 24'd100, -4, 61, 1);
                timed_case(s ? 24'hfffff0 : 24'd100, 0, 65, 1);
                timed_case(s ? 24'hfffff0 : 24'd100, 8, 220, 0);
            end
        end
        // Two pending timeouts share the expiry edge without sharing result state.
        cycle=0; pins=0; target=3; timeout=1; ctx=0; arm=1; tick;
        ctx=1; arm=1; tick; arm=0;
        repeat (65) tick;
        if (a_ready !== 0) $fatal(1, "timeout arrived early");
        tick;
        if (a_ready !== 2'b11 || !a_exp) $fatal(1, "timeout did not arrive in both slots");
        ctx=0; consume=1; tick; consume=0;
        if (a_ready !== 2'b10) $fatal(1, "consume touched the other slot");
        flush=1; tick;
        if (|a_ready) $fatal(1, "flush kept a result");
        $display("PASS capture: %0d directed cases and %0d checked edges", cases+1, ticks);
        $finish;
    end
endmodule
