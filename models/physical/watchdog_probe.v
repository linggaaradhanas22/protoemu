// EVAL-017 exploration (BLK-CORE): per-context blocked-issue watchdog.
// Not production RTL. A shared 6-bit prescaler ticks every 64 cycles. Each
// context counts ticks since its last issue and fires at its host-set limit
// (0 = off). Firing requests the CHG-008 global fault.
module watchdog_probe (
    input clk, rst_n, clear,
    input [1:0] issued, running,
    input [1:0] set_limit,
    input [15:0] limit_in,
    output [1:0] fire
);
    reg [5:0] prescale;
    always @(posedge clk)
        if (!rst_n || clear) prescale <= 0;
        else prescale <= prescale + 1'b1;
    wire tick = prescale == 6'd63;
    genvar c;
    generate
        for (c = 0; c < 2; c = c + 1) begin : ctx
            reg [15:0] limit, count;
            reg fired;
            always @(posedge clk) begin
                if (!rst_n) begin
                    limit <= 0; count <= 0; fired <= 0;
                end else begin
                    if (set_limit[c]) limit <= limit_in;
                    if (clear || issued[c] || !running[c]) begin
                        count <= 0; fired <= 0;
                    end else if (tick && limit != 0) begin
                        count <= count + 1'b1;
                        if (count + 1'b1 == limit) fired <= 1;
                    end
                end
            end
            assign fire[c] = fired;
        end
    endgenerate
endmodule
