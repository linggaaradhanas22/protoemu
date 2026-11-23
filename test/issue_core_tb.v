`default_nettype none

module issue_core_tb;
    reg clk, rst_n, start, flush;
    reg [23:0] cycle;
    reg [1:0] enable_ctx;
    reg [6:0] entry0, entry1;
    wire running, done, faulted, fault_safe, fault_ctx;
    wire [7:0] fault_pc;
    wire [2:0] fault_cause;
    wire fetch_req_valid;
    wire [6:0] fetch_pc;
    reg fetch_rsp_valid, fetch_rsp_fault;
    reg [23:0] fetch_instruction;
    wire drive_valid, drive_ctx;
    wire [23:0] drive_deadline;
    wire [7:0] drive_mask, drive_value, drive_oe;
    reg drive_credit, drive_ready, drive_reject, drive_empty;
    wire capture_arm, capture_consume, capture_ctx;
    wire [2:0] capture_pin;
    wire [1:0] capture_mode, capture_polarity;
    wire capture_level, capture_guarded;
    wire [23:0] capture_target;
    wire [15:0] capture_timeout;
    reg capture_arm_reject, capture_bit, capture_expired;
    reg [1:0] capture_ready;
    reg [23:0] capture_stamp;
    reg [1:0] ingress_ready, egress_ready;
    reg [31:0] ingress_words;
    wire [1:0] ingress_pop, egress_push;
    wire [15:0] egress_word;

    issue_core u (
        .clk(clk), .rst_n(rst_n), .cycle(cycle), .start(start), .flush(flush),
        .enable_ctx(enable_ctx), .entry0(entry0), .entry1(entry1), .running(running),
        .done(done), .faulted(faulted), .fault_safe(fault_safe), .fault_ctx(fault_ctx),
        .fault_pc(fault_pc), .fault_cause(fault_cause),
        .fetch_req_valid(fetch_req_valid), .fetch_pc(fetch_pc), .fetch_rsp_valid(fetch_rsp_valid),
        .fetch_rsp_fault(fetch_rsp_fault), .fetch_instruction(fetch_instruction),
        .drive_valid(drive_valid), .drive_ctx(drive_ctx), .drive_deadline(drive_deadline),
        .drive_mask(drive_mask), .drive_value(drive_value), .drive_oe(drive_oe),
        .drive_credit(drive_credit), .drive_ready(drive_ready), .drive_reject(drive_reject),
        .drive_empty(drive_empty), .capture_arm(capture_arm), .capture_consume(capture_consume),
        .capture_ctx(capture_ctx), .capture_pin(capture_pin), .capture_mode(capture_mode),
        .capture_polarity(capture_polarity), .capture_level(capture_level),
        .capture_guarded(capture_guarded), .capture_target(capture_target), .capture_timeout(capture_timeout),
        .capture_arm_reject(capture_arm_reject), .capture_ready(capture_ready), .capture_bit(capture_bit),
        .capture_expired(capture_expired), .capture_stamp(capture_stamp), .ingress_ready(ingress_ready),
        .egress_ready(egress_ready), .ingress_words(ingress_words), .ingress_pop(ingress_pop),
        .egress_push(egress_push), .egress_word(egress_word)
    );
endmodule

`default_nettype wire
