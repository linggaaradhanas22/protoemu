// EVAL-002: a word-at-a-time descriptor staging port and a two-phase shift lane.
module probe_lane (
    input clk, rst_n, arm,
    input [23:0] descriptor,
    input [15:0] seed,
    input [4:0] pins,
    output reg [4:0] mask, data,
    output reg [15:0] captured,
    output reg done
);
    reg [2:0] loading;
    reg active;
    reg [15:0] period, phase, capture_at, tx, tick;
    reg [6:0] left;
    reg [2:0] clk_pin, tx_pin, rx_pin;
    reg polarity, lsb;

    always @* begin
        mask = 0;
        data = 0;
        if (active && tick == 0) begin
            if (clk_pin < 5) begin
                mask[clk_pin] = 1;
                data[clk_pin] = polarity;
            end
            if (tx_pin < 5) begin
                mask[tx_pin] = 1;
                data[tx_pin] = lsb ? tx[0] : tx[15];
            end
        end
        if (active && tick == phase && clk_pin < 5) begin
            mask[clk_pin] = 1;
            data[clk_pin] = !polarity;
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            loading <= 0;
            active <= 0;
            done <= 0;
            tick <= 0;
            captured <= 0;
        end else if (arm) begin
            loading <= 4;
            active <= 0;
            done <= 0;
            tx <= seed;
        end else if (loading != 0) begin
            loading <= loading - 1'b1;
            case (loading)
                3: {left, period} <= descriptor[22:0];
                2: {capture_at, phase} <= {descriptor[23:8], 8'b0, descriptor[7:0]};
                1: begin
                    {lsb, rx_pin, tx_pin, polarity, clk_pin} <=
                        {descriptor[16], descriptor[12:10], descriptor[6:4], descriptor[3:0]};
                    active <= left != 0;
                    tick <= 0;
                    captured <= 0;
                end
                default: begin end
            endcase
        end else if (active) begin
            if (tick == capture_at && rx_pin < 5) begin
                captured <= lsb ? {pins[rx_pin], captured[15:1]} : {captured[14:0], pins[rx_pin]};
            end
            if (tick + 16'd1 == period) begin
                tick <= 0;
                tx <= lsb ? tx >> 1 : tx << 1;
                left <= left - 1'b1;
                if (left == 1) begin
                    active <= 0;
                    done <= 1;
                end
            end else tick <= tick + 1'b1;
        end
    end
endmodule
