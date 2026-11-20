// EVAL-002: loadable flop memory with a registered read port.
module probe_store #(parameter W = 24, AW = 6) (
    input clk, wr, rd,
    input [AW-1:0] waddr, raddr,
    input [W-1:0] wdata,
    output reg [W-1:0] word
);
    reg [W-1:0] mem [0:(1<<AW)-1];
    always @(posedge clk) begin
        if (wr) mem[waddr] <= wdata;
        if (rd) word <= mem[raddr];
    end
endmodule
