`timescale 1ns/1ps
module full_core_probe_tb #(parameter OPT = 0);
    reg clk = 0;
    always #5 clk = !clk;

    reg rst_n = 0, start = 0, stop = 0, image_valid = 0, load_word = 0;
    reg [6:0] load_addr = 0, entry1 = 0;
    reg [23:0] load_data = 0;
    reg [7:0] image_count = 0, pins = 0;
    reg [1:0] enable_ctx = 1, ingress_ready = 0;
    wire [1:0] ingress_pop, egress_push;
    wire [15:0] egress_word;
    wire [7:0] pad_value, pad_oe, fault_pc;
    wire done, faulted, fault_ctx;
    wire [2:0] fault_cause;
    full_core_probe #(.OPT(OPT)) dut (
        .clk(clk), .rst_n(rst_n), .start(start), .stop(stop), .image_valid(image_valid), .load_word(load_word),
        .load_addr(load_addr), .entry0(7'd0), .entry1(entry1), .load_data(load_data), .image_count(image_count),
        .owner0(8'h01), .owner1(8'h02), .open_drain(8'd0), .raw_pins(pins), .enable_ctx(enable_ctx),
        .ingress_ready(ingress_ready), .egress_ready(2'b11), .ingress_words(32'hcafe_00a5),
        .ingress_pop(ingress_pop), .egress_push(egress_push), .egress_word(egress_word),
        .pad_value(pad_value), .pad_oe(pad_oe), .done(done), .faulted(faulted),
        .fault_ctx(fault_ctx), .fault_pc(fault_pc), .fault_cause(fault_cause)
    );

    localparam QUEUE = 1, TIMEOUT = 2, MATCH = 3, FAULT = 4, LATE = 5, WRITEBACK = 6, BAD_HOST = 7;
    integer run_case = 0;
    integer out0 = 0, out1 = 0, pops = 0, accepted = 0, checked = 0;
    reg did_block = 0, saved_retry = 0;
    reg [23:0] frozen_target = 0;
    reg [4:0] expected_bits = 5'b00101;

    function [23:0] set_word;
        input [2:0] rd;
        input [15:0] value;
        begin set_word = {value, rd, 5'd1}; end
    endfunction
    function [23:0] shift_lsb;
        input [8:0] delay;
        begin shift_lsb = {3'b0, 1'b1, delay, 3'd0, 3'd1, 5'd20}; end
    endfunction

    task reset;
        begin
            @(negedge clk);
            run_case = 0;
            rst_n = 0;
            image_valid = 0;
            pins = 0;
            ingress_ready = 0;
            repeat (2) @(negedge clk);
            rst_n = 1;
            out0 = 0;
            out1 = 0;
            pops = 0;
            accepted = 0;
            checked = 0;
            did_block = 0;
            saved_retry = 0;
        end
    endtask
    task load;
        input [6:0] index;
        input [23:0] word;
        begin
            load_word = 1;
            load_addr = index;
            load_data = word;
            @(negedge clk);
            load_word = 0;
        end
    endtask
    task launch;
        input [7:0] count;
        input [1:0] contexts;
        begin
            image_count = count;
            image_valid = 1;
            enable_ctx = contexts;
            start = 1;
            @(negedge clk);
            start = 0;
        end
    endtask

    always @(posedge clk) if (run_case != 0) begin
        if (run_case == BAD_HOST && (|ingress_pop || |egress_push))
            $fatal(1, "malformed host instruction transferred payload");
        if (OPT >= 5 && (dut.execute || dut.retry)) begin
            if (dut.fast_we !== (dut.retire && dut.write_a)) $fatal(1, "write enable differs from control");
            if (dut.fast_we && dut.fast_data !== dut.word_a) $fatal(1, "writeback data differs from control");
        end
        if ($test$plusargs("trace") && (dut.fetch || dut.execute || dut.retry || |dut.drive.due ||
            dut.fault_pending || done))
            $display("TRACE case=%0d cycle=%h fetch=%b exec=%b retry=%b ctx=%b pc=%h retire=%b accept=%b cause=%h due=%h pins=%h oe=%h cap=%b pop=%b push=%b data=%h",
                     run_case, dut.cycle, dut.fetch, dut.execute, dut.retry, dut.ctx, dut.cur_pc, dut.retire,
                     dut.drive_accept, dut.cause, dut.drive.due, pad_value, pad_oe, dut.cap_ready,
                     ingress_pop, egress_push, (|egress_push) ? egress_word : 16'b0);
        if (ingress_pop[1]) pops = pops + 1;
        if (egress_push[0]) begin
            out0 = out0 + 1;
            if (egress_word !== ((run_case == WRITEBACK || run_case == MATCH) ? 16'd1 : 16'd0))
                $fatal(1, "unexpected output %h in case %0d", egress_word, run_case);
        end
        if (egress_push[1]) begin
            out1 = out1 + 1;
            if (egress_word !== 16'hcafe) $fatal(1, "wrong context-1 payload");
        end
        if (run_case == QUEUE || run_case == LATE) begin
            if (dut.execute && dut.next_wait == 1) begin
                did_block = 1;
                frozen_target = dut.deadline;
            end
            if (dut.drive_accept) begin
                accepted = accepted + 1;
                if (dut.retry) begin
                    if (dut.drive.deadline !== frozen_target) $fatal(1, "retry changed deadline");
                    saved_retry = 1;
                end
            end
            if (run_case == QUEUE && |dut.drive.due) begin
                #1;
                if (pad_value[0] !== expected_bits[checked] || pad_oe[0] !== 1'b1)
                    $fatal(1, "wrong registered drive %0d", checked);
                checked = checked + 1;
            end
        end
    end

    integer i;
    initial begin
        reset;
        load(0, set_word(1, 5));
        load(1, 24'd15);
        for (i = 0; i < 4; i = i + 1) load(7'd2 + i, shift_lsb(9'd50 + i));
        load(6, shift_lsb(80));
        load(7, 24'd56);
        load(8, 0);
        load(9, 24'd55);
        load(10, 24'd56);
        load(11, 0);
        entry1 = 9;
        dut.cycle = 24'hffffe0;
        run_case = QUEUE;
        launch(12, 2'b11);
        repeat (25) @(negedge clk);
        ingress_ready = 2'b10;
        repeat (120) @(negedge clk);
        if (!done || faulted || !did_block || !saved_retry || accepted != 5 || checked != 5 ||
            pops != 1 || out0 != 1 || out1 != 1) $fatal(1, "saved request or context isolation failed");

        reset;
        load(0, set_word(1, 5));
        load(1, 24'd15);
        for (i = 0; i < 4; i = i + 1) load(7'd2 + i, shift_lsb(9'd80 + i));
        load(6, shift_lsb(50));
        load(7, 0);
        load(8, 24'd55);
        load(9, 24'd56);
        load(10, 0);
        entry1 = 8;
        run_case = LATE;
        launch(11, OPT >= 3 ? 2'b11 : 2'b01);
        if (OPT >= 3) begin
            wait (did_block && dut.cycle == frozen_target + 24'd1);
            @(negedge clk);
            ingress_ready = 2'b10;
            @(posedge clk);
            if (!dut.runnable[1] || ingress_pop != 0 || dut.fetch || !dut.retry || dut.ctx || dut.cause != 5)
                $fatal(1, "expired retry did not exclude the now-runnable context on fault edge F");
        end
        wait (dut.fault_pending);
        @(negedge clk);
        if (!did_block || accepted != 4 || dut.drive_credit ||
            dut.cycle !== frozen_target + (OPT >= 3 ? 24'd2 : 24'd1))
            $fatal(1, "wrong expired-retry edge with the queue still full");
        @(negedge clk);
        if (!faulted || fault_pc != 6 || fault_cause != 5 || pad_oe != 0 || dut.active != 0 || pops != 0)
            $fatal(1, "late request changed pins or did not report a drive fault");

        for (i = TIMEOUT; i <= MATCH; i = i + 1) begin
            reset;
            load(0, set_word(1, 1));
            load(1, 24'd15);
            load(2, {3'b0, 3'd1, 9'd12, 1'b1, 3'd0, 5'd6});
            load(3, 24'd56);
            load(4, 0);
            run_case = i;
            pins = i == MATCH ? 1 : 0;
            launch(5, 2'b01);
            repeat (100) @(negedge clk);
            if (!done || faulted || out0 != 1) $fatal(1, "guarded wait case %0d failed", i);
        end

        reset;
        load(0, 24'd15);
        load(1, {5'b0, (OPT == 4 ? 9'd6 : 9'd4), 1'b1, 1'b1, 3'd0, 5'd18});
        load(2, 24'd12);
        run_case = FAULT;
        launch(3, 2'b01);
        wait (dut.fault_pending);
        @(negedge clk);
        if (pad_value !== 8'h01 || pad_oe !== 8'h01 || faulted)
            $fatal(1, "due work did not complete on edge F");
        @(negedge clk);
        if (pad_value !== 8'h00 || pad_oe !== 8'h00 || !faulted || fault_ctx || fault_pc != 2 || fault_cause != 2)
            $fatal(1, "fault safe edge F+1 or fault record failed");
        reset;
        load(0, set_word(1, 16'hfffe));
        load(1, {1'b0, 15'd3, 3'd1, 5'd2});
        load(2, {13'b0, 3'd1, 3'd2, 5'd31});
        load(3, {13'b0, 3'd1, 3'd2, 5'd29});
        load(4, {12'b0, 4'd1, 3'd2, 5'd27});
        load(5, {16'd2, 3'd2, 5'd30});
        load(6, {9'b0, 7'd6, 3'd1, 5'd9});
        load(7, {16'b0, 3'd2, 5'd24});
        load(8, 0);
        run_case = WRITEBACK;
        launch(9, 2'b01);
        repeat (40) @(negedge clk);
        if (!done || faulted || out0 != 1 || dut.rf.regs[1] != 0 || dut.rf.regs[2] != 1)
            $fatal(1, "writeback program did not retire correctly");

        reset;
        load(0, 24'h000137);
        load(1, 0);
        run_case = BAD_HOST;
        ingress_ready = 2'b01;
        launch(2, 2'b01);
        repeat (10) @(negedge clk);
        if (!faulted || fault_cause != 2 || fault_pc != 0 || dut.rf.regs[1] != 0)
            $fatal(1, "malformed host instruction did not fault without side effects");
        $display("PASS: saved retry, added writeback and malformed-host checks, guarded waits, F/F+1");
        $finish;
    end

    initial begin
        #20000;
        $fatal(1, "probe simulation timed out");
    end
endmodule
