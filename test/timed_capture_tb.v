`default_nettype none

module timed_capture_tb;
    reg clk, rst_n, flush, detect_fault;
    reg fault_pending;
    reg [23:0] cycle, capture_target;
    reg [7:0] pin_sample;
    reg capture_arm, capture_consume, capture_ctx, capture_level, capture_guarded;
    reg [2:0] capture_pin;
    reg [1:0] capture_mode, capture_polarity;
    reg [15:0] capture_timeout;
    wire capture_arm_reject, capture_bit, capture_expired;
    wire [1:0] capture_ready;
    wire [23:0] capture_stamp;

    always @(posedge clk)
        fault_pending <= rst_n && detect_fault;

    timed_capture u (
        .clk(clk), .rst_n(rst_n), .flush(flush || fault_pending),
        .cycle(cycle), .pin_sample(pin_sample), .capture_arm(capture_arm),
        .capture_consume(capture_consume), .capture_ctx(capture_ctx), .capture_pin(capture_pin),
        .capture_mode(capture_mode), .capture_polarity(capture_polarity), .capture_level(capture_level),
        .capture_guarded(capture_guarded), .capture_target(capture_target), .capture_timeout(capture_timeout),
        .capture_arm_reject(capture_arm_reject), .capture_ready(capture_ready), .capture_bit(capture_bit),
        .capture_expired(capture_expired), .capture_stamp(capture_stamp)
    );
endmodule

`default_nettype wire
