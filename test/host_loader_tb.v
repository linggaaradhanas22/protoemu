`default_nettype none

module host_loader_tb;
    reg clk, rst_n, selected, host_cs_n, host_sck, host_mosi;
    wire host_miso, host_ready;
    wire prog_write_valid, load_active, image_valid, running, start, flush, safe;
    wire [6:0] prog_write_index, entry0, entry1;
    wire [23:0] prog_write_word;
    wire [7:0] word_count, owner0, owner1, open_drain;
    wire [1:0] enable_ctx, ingress_ready, egress_ready;
    wire [31:0] ingress_words;
    reg core_done, core_faulted, core_fault_safe, core_fault_ctx;
    reg [7:0] core_fault_pc;
    reg [2:0] core_fault_cause;
    reg [1:0] ingress_pop, egress_push;
    reg [15:0] egress_word;

    host_loader u (
        .clk(clk), .rst_n(rst_n), .selected(selected), .host_cs_n(host_cs_n), .host_sck(host_sck), .host_mosi(host_mosi),
        .host_miso(host_miso), .host_ready(host_ready), .prog_write_valid(prog_write_valid),
        .prog_write_index(prog_write_index), .prog_write_word(prog_write_word), .load_active(load_active),
        .image_valid(image_valid), .running(running), .word_count(word_count), .start(start), .flush(flush), .safe(safe),
        .enable_ctx(enable_ctx), .entry0(entry0), .entry1(entry1), .owner0(owner0), .owner1(owner1), .open_drain(open_drain),
        .core_done(core_done), .core_faulted(core_faulted), .core_fault_safe(core_fault_safe), .core_fault_ctx(core_fault_ctx),
        .core_fault_pc(core_fault_pc), .core_fault_cause(core_fault_cause), .ingress_pop(ingress_pop), .egress_push(egress_push),
        .egress_word(egress_word), .ingress_ready(ingress_ready), .egress_ready(egress_ready), .ingress_words(ingress_words)
    );
endmodule

`default_nettype wire
