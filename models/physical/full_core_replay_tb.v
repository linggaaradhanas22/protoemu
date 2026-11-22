`timescale 1ns/1ps
module full_core_replay_tb #(parameter OPT=2);
    localparam STDIN = 32'h80000000;
    reg clk=0, rst_n=0, start=0, image_valid=0, load_word=0;
    reg [6:0] load_addr, entry0, entry1;
    reg [23:0] load_data, epoch;
    reg [7:0] image_count, owner0, owner1, open_drain, pins;
    reg [1:0] enabled, ingress_ready, egress_ready;
    reg [31:0] ingress_words;
    wire [1:0] ingress_pop, egress_push;
    wire [15:0] egress_word;
    wire [7:0] pad_value, pad_oe, fault_pc;
    wire done, faulted, fault_ctx;
    wire [2:0] fault_cause;
    full_core_probe #(.OPT(OPT)) dut (
        .clk(clk), .rst_n(rst_n), .start(start), .stop(1'b0), .image_valid(image_valid), .load_word(load_word),
        .load_addr(load_addr), .load_data(load_data), .entry0(entry0), .entry1(entry1), .image_count(image_count),
        .owner0(owner0), .owner1(owner1), .open_drain(open_drain), .raw_pins(pins), .enable_ctx(enabled),
        .ingress_ready(ingress_ready), .egress_ready(egress_ready), .ingress_words(ingress_words),
        .ingress_pop(ingress_pop), .egress_push(egress_push), .egress_word(egress_word),
        .pad_value(pad_value), .pad_oe(pad_oe), .done(done), .faulted(faulted),
        .fault_ctx(fault_ctx), .fault_pc(fault_pc), .fault_cause(fault_cause)
    );

    task tick;
        begin #1; clk=1; #1; clk=0; end
    endtask

    integer n, scanned;
    reg [1:0] popped, pushed;
    reg [15:0] result;
    reg sample_valid;
    reg [2:0] sampled_pin;
    reg sampled_bit;
    initial begin
        scanned = $fscanf(STDIN, "%h %h %h %h %h %h %h %h %h",
                          image_count, entry0, entry1, enabled, owner0, owner1, open_drain, pins, epoch);
        if (scanned != 9) $fatal(1, "bad replay header");
        tick;
        rst_n=1;
        for (n=0; n<image_count; n=n+1) begin
            scanned = $fscanf(STDIN, "%h", load_data);
            if (scanned != 1) $fatal(1, "bad replay program word");
            load_addr=n;
            load_word=1;
            tick;
        end
        load_word=0; image_valid=1; start=1;
        tick;
        dut.cycle=epoch;
        start=0;
        $display("READY");
        $fflush;
        forever begin
            // No trailing whitespace in this scan: stdin has one request per clock.
            scanned = $fscanf(STDIN, "%h %h %h %h", pins, ingress_ready, egress_ready, ingress_words);
            if (scanned == -1) $finish;
            if (scanned != 4) $fatal(1, "bad replay tick");
            #1;
            popped=ingress_pop; pushed=egress_push; result=(|pushed) ? egress_word : 0;
            sample_valid=0; sampled_pin=0; sampled_bit=0;
            if (!dut.flush && dut.capture.live[0] && !dut.cap_ready[0] &&
                dut.capture.slot[0].select_mode == 0 && dut.capture.slot[0].due) begin
                sample_valid=1;
                sampled_pin=dut.capture.slot[0].select_pin;
                sampled_bit=dut.capture.slot[0].current;
            end
            clk=1; #1; clk=0;
            $display("%h %h %h %h %h %h %h %h %h %h %h %h %h", pad_value, pad_oe, popped, pushed,
                     result, done, faulted, fault_ctx, fault_pc, fault_cause, sample_valid, sampled_pin, sampled_bit);
            $fflush;
        end
    end
endmodule
