`default_nettype none

module host_payload_tb;
    reg clk, rst_n, clear;
    reg [1:0] ingress_pop, egress_push;
    reg [15:0] egress_word, host_word;
    wire [1:0] ingress_ready, egress_ready;
    wire [31:0] ingress_words;
    reg host_ctx, host_write, host_stage, host_commit, host_abort;
    reg [1:0] host_stage_index, host_peek;
    reg [2:0] host_release;
    wire host_write_ready, host_stage_ready;
    wire [2:0] host_staged_count;
    wire [3:0] host_egress_count;
    wire [15:0] host_egress_word;

    host_payload u (
        .clk(clk), .rst_n(rst_n), .clear(clear), .ingress_pop(ingress_pop), .egress_push(egress_push),
        .egress_word(egress_word), .ingress_ready(ingress_ready), .egress_ready(egress_ready), .ingress_words(ingress_words),
        .host_ctx(host_ctx), .host_word(host_word), .host_write(host_write), .host_stage(host_stage),
        .host_commit(host_commit), .host_abort(host_abort), .host_stage_index(host_stage_index),
        .host_write_ready(host_write_ready), .host_stage_ready(host_stage_ready), .host_staged_count(host_staged_count),
        .host_peek(host_peek), .host_release(host_release), .host_egress_count(host_egress_count),
        .host_egress_word(host_egress_word)
    );
endmodule

`default_nettype wire
