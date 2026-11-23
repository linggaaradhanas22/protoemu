// SPDX-License-Identifier: Apache-2.0
// BLK-TIMER: Shared cycle timebase. WIDTH is reduced only in wrap tests.

`default_nettype none

module cycle_timer #(
    parameter integer WIDTH = 24
) (
    input  wire             clk,
    input  wire             rst_n,
    output reg  [WIDTH-1:0] cycle
);
    always @(posedge clk) begin
        if (!rst_n)
            cycle <= 0;
        else
            cycle <= cycle + 1'b1;
    end
endmodule

`default_nettype wire
