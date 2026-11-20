// EVAL-015 exploration (BLK-HOST): payload FIFOs with multi-word host access.
// Not production RTL. DEPTH must be a power of two. Same registered-status
// rule as EVAL-014 for the core side.
//
// Egress (core pushes one word, host reads many): the host reads entry
// rp + peek while it sends a reply, then frees `free_n` words when the reply
// frame closes.
// Ingress (host writes many, core pops one): the host writes tentative words
// to wp + slot while its request arrives, then commits `commit_n` words when the
// frame is validated. Tentative slots lie beyond the tail, so the core never
// reads them. The host only writes slots below the free count at frame start.
module fifo_multi_egress #(parameter DEPTH = 8) (
    input clk, rst_n, clear,
    input push,
    input [15:0] wdata,
    input [$clog2(DEPTH)-1:0] peek,
    input [$clog2(DEPTH):0] free_n,
    output [15:0] rdata,
    output can_push,
    output [$clog2(DEPTH):0] count_out
);
    localparam AW = $clog2(DEPTH);
    reg [15:0] mem [0:DEPTH-1];
    reg [AW-1:0] rp, wp;
    reg [AW:0] count;
    assign can_push = count != DEPTH;
    assign rdata = mem[rp + peek];
    assign count_out = count;
    wire do_push = push && can_push;
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            rp <= 0;
            wp <= 0;
            count <= 0;
        end else begin
            if (do_push) begin
                mem[wp] <= wdata;
                wp <= wp + 1'b1;
            end
            rp <= rp + free_n[AW-1:0];
            count <= count + do_push - free_n;
        end
    end
endmodule

module fifo_multi_ingress #(parameter DEPTH = 8) (
    input clk, rst_n, clear,
    input write,
    input [$clog2(DEPTH)-1:0] slot,
    input [15:0] wdata,
    input [$clog2(DEPTH):0] commit_n,
    input pop,
    output [15:0] rdata,
    output can_pop,
    output [$clog2(DEPTH):0] count_out
);
    localparam AW = $clog2(DEPTH);
    reg [15:0] mem [0:DEPTH-1];
    reg [AW-1:0] rp, wp;
    reg [AW:0] count;
    assign can_pop = count != 0;
    assign rdata = mem[rp];
    assign count_out = count;
    wire do_pop = pop && can_pop;
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            rp <= 0;
            wp <= 0;
            count <= 0;
        end else begin
            if (write)
                mem[wp + slot] <= wdata;
            if (do_pop)
                rp <= rp + 1'b1;
            wp <= wp + commit_n[AW-1:0];
            count <= count + commit_n - do_pop;
        end
    end
endmodule

// Two contexts: an ingress and an egress queue each.
module fifo_multi_probe #(parameter DEPTH = 8) (
    input clk, rst_n, clear,
    input [1:0] in_write, in_pop, eg_push,
    input [2*$clog2(DEPTH)-1:0] in_slot, eg_peek,
    input [2*($clog2(DEPTH)+1)-1:0] in_commit, eg_free,
    input [31:0] in_wdata, eg_wdata,
    output [31:0] in_rdata, eg_rdata,
    output [1:0] in_can_pop, eg_can_push,
    output [2*($clog2(DEPTH)+1)-1:0] in_count, eg_count
);
    localparam AW = $clog2(DEPTH);
    genvar c;
    generate
        for (c = 0; c < 2; c = c + 1) begin : ctx
            fifo_multi_ingress #(.DEPTH(DEPTH)) ingress (
                clk, rst_n, clear, in_write[c], in_slot[AW*c +: AW], in_wdata[16*c +: 16],
                in_commit[(AW+1)*c +: AW+1], in_pop[c], in_rdata[16*c +: 16], in_can_pop[c],
                in_count[(AW+1)*c +: AW+1]);
            fifo_multi_egress #(.DEPTH(DEPTH)) egress (
                clk, rst_n, clear, eg_push[c], eg_wdata[16*c +: 16], eg_peek[AW*c +: AW],
                eg_free[(AW+1)*c +: AW+1], eg_rdata[16*c +: 16], eg_can_push[c], eg_count[(AW+1)*c +: AW+1]);
        end
    endgenerate
endmodule
