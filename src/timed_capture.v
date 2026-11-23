// SPDX-License-Identifier: Apache-2.0
// BLK-CAPTURE: One observation slot per context, after pad synchronization.

`default_nettype none

module timed_capture (
    input  wire        clk, rst_n, flush,
    input  wire [23:0] cycle,
    input  wire [7:0]  pin_sample,
    input  wire        capture_arm, capture_consume, capture_ctx,
    input  wire [2:0]  capture_pin,
    input  wire [1:0]  capture_mode, capture_polarity,
    input  wire        capture_level, capture_guarded,
    input  wire [23:0] capture_target,
    input  wire [15:0] capture_timeout,
    output wire        capture_arm_reject,
    output wire [1:0]  capture_ready,
    output wire        capture_bit, capture_expired,
    output wire [23:0] capture_stamp
);
    localparam [1:0] SAMPLE=0, LEVEL=1, EDGE=2;
    localparam [1:0] EMPTY=0, ARMED=1, RESULT=2;

    reg [7:0] previous;
    wire [1:0] occupied, result_bit, result_expired;
    wire [23:0] result_stamp [0:1];
    wire enabled = rst_n && !flush;
    wire [23:0] distance = capture_target - cycle;
    wire future_target = distance != 0 && !distance[23];
    wire guarded_level = capture_mode == LEVEL && capture_guarded;
    wire guard_initially_open = !guarded_level || !future_target;
    wire [15:0] arm_limit = guarded_level ? capture_timeout : 16'd0;
    wire [23:0] arm_deadline = guard_initially_open ?
        capture_target + {2'b0, arm_limit, 6'b0} : capture_target;

    assign capture_arm_reject = enabled && capture_arm && (occupied[capture_ctx] ||
        (capture_mode == SAMPLE && !future_target) ||
        (capture_mode == EDGE && capture_polarity == 2'd3) || capture_mode == 2'd3);
    assign capture_bit = capture_ready[capture_ctx] && result_bit[capture_ctx];
    assign capture_expired = capture_ready[capture_ctx] && result_expired[capture_ctx];
    assign capture_stamp = capture_ready[capture_ctx] ? result_stamp[capture_ctx] : 24'd0;

    // Update at the arm edge too: that transition is outside the observation window.
    always @(posedge clk) begin
        if (!rst_n) previous <= 0;
        else previous <= pin_sample;
    end

    genvar i;
    generate for (i = 0; i < 2; i = i + 1) begin : slot
        localparam [0:0] CTX = i == 1;
        reg [1:0] state, mode, polarity;
        reg [2:0] pin;
        reg level, guard_open;
        reg [23:0] deadline, stamp;
        reg [15:0] limit;
        reg sampled_bit, expired;
        wire mine = capture_ctx == CTX;
        wire due = cycle == deadline;
        wire current = pin_sample[pin];
        wire transition = current != previous[pin];
        wire matched = (mode == SAMPLE && due) ||
            (mode == LEVEL && (guard_open || due) && current == level) ||
            (mode == EDGE && transition && (polarity == 2'd2 || current == polarity[0]));

        assign occupied[i] = state != EMPTY;
        assign capture_ready[i] = state == RESULT;
        assign result_bit[i] = sampled_bit;
        assign result_expired[i] = expired;
        assign result_stamp[i] = stamp;

        // State protects the slot fields until the next arm or observation writes them.
        always @(posedge clk) begin
            if (!enabled || (mine && capture_consume && state == RESULT)) begin
                state <= EMPTY;
                guard_open <= 0;
            end else if (mine && capture_arm && !capture_arm_reject) begin
                state <= ARMED;
                pin <= capture_pin;
                mode <= capture_mode;
                polarity <= capture_polarity;
                level <= capture_level;
                guard_open <= guard_initially_open;
                deadline <= arm_deadline;
                limit <= arm_limit;
            end else if (state == ARMED) begin
                if (matched) begin
                    state <= RESULT;
                    sampled_bit <= current;
                    expired <= 0;
                    stamp <= cycle;
                end else if (!guard_open && due) begin
                    guard_open <= 1;
                    deadline <= deadline + {2'b0, limit, 6'b0};
                end else if (mode == LEVEL && due && limit != 0) begin
                    state <= RESULT;
                    sampled_bit <= 0;
                    expired <= 1;
                    stamp <= cycle;
                end
            end
        end
    end endgenerate
endmodule

`default_nettype wire
