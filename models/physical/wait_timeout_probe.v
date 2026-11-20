// EVAL-017 exploration (BLK-CAPTURE): guarded level wait slots, with and
// without a timeout. Not production RTL. Two slots, one per context.
// TIMEOUT = 1: the arm stores a 16-bit timeout (units of 64 cycles). When the
// guard opens, the slot reloads its deadline with target + timeout x 64 and
// ends the wait as expired if that cycle arrives before a match.
// TIMEOUT = 2: an unguarded timed wait. The core passes the expiry cycle as
// `target` (from its existing deadline adder); the slot reuses its deadline
// compare and stores only a mode bit.
module wait_timeout_probe #(parameter TIMEOUT = 0) (
    input clk, rst_n, flush,
    input [23:0] cycle,
    input [7:0] pin_sample,
    input [1:0] arm, consume,
    input [23:0] target,
    input level, guarded,
    input [2:0] pinsel,
    input [15:0] tmo,
    output [1:0] done, expired,
    output [47:0] stamp
);
    genvar c;
    generate
        for (c = 0; c < 2; c = c + 1) begin : slot
            reg armed, open, hit, lost, want, timed;
            reg [2:0] pin;
            reg [23:0] deadline, seen;
            reg [15:0] limit;
            wire match = armed && open && pin_sample[pin] == want;
            wire due = cycle == deadline;
            always @(posedge clk) begin
                if (!rst_n || flush || consume[c]) begin
                    armed <= 0; open <= 0; hit <= 0; lost <= 0; want <= 0; pin <= 0; timed <= 0;
                    deadline <= 0; seen <= 0; limit <= 0;
                end else if (arm[c]) begin
                    armed <= 1; open <= !guarded; hit <= 0; lost <= 0; want <= level;
                    pin <= pinsel;
                    // Mode 2: a timed wait is unguarded; guarded waits work as before.
                    timed <= TIMEOUT == 2 && !guarded && tmo != 0;
                    deadline <= TIMEOUT != 1 || guarded ? target : target + {2'b0, tmo, 6'b0};
                    limit <= TIMEOUT == 1 ? tmo : 16'd0;
                end else if (armed && !hit && !lost) begin
                    if (match) begin
                        hit <= 1; seen <= cycle;
                    end else if (!open && due) begin
                        open <= 1;
                        if (TIMEOUT == 1) deadline <= deadline + {2'b0, limit, 6'b0};
                    end else if (open && due && ((TIMEOUT == 1 && limit != 0) || (TIMEOUT == 2 && timed))) begin
                        lost <= 1;
                    end
                end
            end
            assign done[c] = hit || lost;
            assign expired[c] = lost;
            assign stamp[24*c +: 24] = seen;
        end
    endgenerate
endmodule
