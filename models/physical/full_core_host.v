// Exploratory host boundary for EVAL-025. The configuration and run-control
// registers stand in for BLK-HOST's committed start_cfg and run_ctl flops.
module full_core_host #(parameter OPT = 10) (
    input clk, rst_n, start, stop, image_valid, load_word,
    input [6:0] load_addr, entry0, entry1,
    input [23:0] load_data,
    input [7:0] image_count, owner0, owner1, open_drain, raw_pins,
    input [1:0] enable_ctx, ingress_ready, egress_ready,
    input [31:0] ingress_words,
    output [1:0] ingress_pop, egress_push,
    output [15:0] egress_word,
    output [7:0] pad_value, pad_oe,
    output done, faulted, fault_ctx,
    output [7:0] fault_pc,
    output [2:0] fault_cause
);
    reg s_start, s_stop, s_valid;
    reg [6:0] s_entry0, s_entry1;
    reg [7:0] s_count, s_owner0, s_owner1, s_open_drain;
    reg [1:0] s_enable;

    always @(posedge clk) begin
        if (!rst_n) begin
            s_start <= 0;
            s_stop <= 0;
            s_valid <= 0;
            s_entry0 <= 0;
            s_entry1 <= 0;
            s_count <= 0;
            s_owner0 <= 0;
            s_owner1 <= 0;
            s_open_drain <= 0;
            s_enable <= 0;
        end else begin
            s_start <= start;
            s_stop <= stop;
            s_valid <= image_valid;
            s_entry0 <= entry0;
            s_entry1 <= entry1;
            s_count <= image_count;
            s_owner0 <= owner0;
            s_owner1 <= owner1;
            s_open_drain <= open_drain;
            s_enable <= enable_ctx;
        end
    end

    full_core_probe #(.OPT(OPT)) dut (
        .clk(clk), .rst_n(rst_n), .start(s_start), .stop(s_stop),
        .image_valid(s_valid), .load_word(load_word),
        .load_addr(load_addr), .load_data(load_data),
        .entry0(s_entry0), .entry1(s_entry1), .image_count(s_count),
        .owner0(s_owner0), .owner1(s_owner1), .open_drain(s_open_drain),
        .raw_pins(raw_pins), .enable_ctx(s_enable),
        .ingress_ready(ingress_ready), .egress_ready(egress_ready), .ingress_words(ingress_words),
        .ingress_pop(ingress_pop), .egress_push(egress_push), .egress_word(egress_word),
        .pad_value(pad_value), .pad_oe(pad_oe), .done(done), .faulted(faulted),
        .fault_ctx(fault_ctx), .fault_pc(fault_pc), .fault_cause(fault_cause)
    );
endmodule
