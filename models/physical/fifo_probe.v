// EVAL-014 exploration (BLK-HOST, BLK-CORE): payload FIFO depth and same-edge
// host/core access. Not production RTL.
//
// BYPASS = 0: push is accepted only if the count before the edge is below DEPTH,
//             and pop only if it is above zero. A push and a pop on one edge both
//             happen when 0 < count < DEPTH. No path from one side to the other.
// BYPASS = 1: also accept a push when full if a pop happens on the same edge, and
//             a pop when empty if a push happens on the same edge (pass-through).
module fifo_probe_queue #(parameter DEPTH = 8, BYPASS = 0) (
    input clk, rst_n, clear,
    input push, pop,
    input [15:0] wdata,
    output [15:0] rdata,
    output can_push, can_pop,
    output do_push, do_pop
);
    localparam AW = DEPTH <= 2 ? 1 : DEPTH <= 4 ? 2 : DEPTH <= 8 ? 3 : DEPTH <= 16 ? 4 : 5;
    reg [15:0] mem [0:DEPTH-1];
    reg [AW-1:0] rp, wp;
    reg [AW:0] count;
    wire empty = count == 0;
    wire full = count == DEPTH;
    assign can_push = !full || (BYPASS != 0 && pop && !empty);
    assign can_pop = !empty || (BYPASS != 0 && push);
    assign do_push = push && can_push;
    assign do_pop = pop && can_pop;
    wire through = BYPASS != 0 && empty && do_push && do_pop;
    assign rdata = through ? wdata : mem[rp];
    wire [AW-1:0] wp_next = wp == DEPTH - 1 ? 0 : wp + 1'b1;
    wire [AW-1:0] rp_next = rp == DEPTH - 1 ? 0 : rp + 1'b1;

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            rp <= 0;
            wp <= 0;
            count <= 0;
        end else if (!through) begin
            if (do_push) begin
                mem[wp] <= wdata;
                wp <= wp_next;
            end
            if (do_pop)
                rp <= rp_next;
            count <= count + do_push - do_pop;
        end
    end
endmodule

// Four queues: ingress and egress for each of two contexts.
module fifo_probe #(parameter DEPTH = 8, BYPASS = 0) (
    input clk, rst_n, clear,
    input [3:0] push, pop,
    input [63:0] wdata,
    output [63:0] rdata,
    output [3:0] can_push, can_pop
);
    genvar q;
    generate
        for (q = 0; q < 4; q = q + 1) begin : queue
            wire unused_push, unused_pop;
            fifo_probe_queue #(.DEPTH(DEPTH), .BYPASS(BYPASS)) u (
                clk, rst_n, clear, push[q], pop[q], wdata[16*q +: 16], rdata[16*q +: 16],
                can_push[q], can_pop[q], unused_push, unused_pop);
        end
    endgenerate
endmodule
