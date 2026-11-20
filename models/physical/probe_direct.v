// EVAL-002: wait until a staged direct pin update or sample reaches its timestamp.
module probe_direct (
    input clk, rst_n, issue, capture,
    input [15:0] timer, stamp,
    input [4:0] pins, mask, data,
    output [4:0] out_mask, out_data,
    output reg [4:0] sampled,
    output stall
);
    reg pending, sample;
    reg [15:0] at;
    reg [4:0] m, d;
    wire due = pending && timer == at;
    assign stall = (issue || capture) && !due;
    assign out_mask = due && !sample ? m : 5'b0;
    assign out_data = d;
    always @(posedge clk) begin
        if (!rst_n) begin
            pending <= 0;
            sampled <= 0;
        end else if (due) begin
            pending <= 0;
            if (sample) sampled <= pins;
        end else if ((issue || capture) && !pending) begin
            pending <= 1;
            sample <= capture;
            at <= stamp;
            m <= mask;
            d <= data;
        end
    end
endmodule
