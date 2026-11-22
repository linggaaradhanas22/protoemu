// Exploration for BLK-CAPTURE: store the guard target and precomputed expiry.
module capture_expiry_probe (
    input clk, rst_n, flush,
    input [23:0] cycle, target, expiry,
    input [7:0] pins,
    input ctx, arm, consume,
    input [2:0] pin,
    input [1:0] mode, polarity,
    input level, guarded, timed,
    output [1:0] ready,
    output occupied, sample, expired,
    output [23:0] stamp
);
    localparam SAMPLE = 2'd0, LEVEL = 2'd1, EDGE = 2'd2;
    reg [7:0] previous;
    reg [1:0] live, observed, lost, bit_value;
    reg [23:0] seen [0:1];
    wire [23:0] distance = target - cycle;

    always @(posedge clk)
        if (!rst_n) previous <= 0;
        else previous <= pins;

    assign occupied = live[ctx];
    assign ready = observed | lost;
    assign sample = bit_value[ctx];
    assign expired = lost[ctx];
    assign stamp = seen[ctx];

    genvar i;
    generate
        for (i = 0; i < 2; i = i + 1) begin : slot
            localparam CTX = i == 1;
            reg [2:0] select_pin;
            reg [1:0] select_mode, select_edge;
            reg select_level, open, has_expiry;
            reg [23:0] guard_at, expiry_at;
            wire due = cycle == guard_at;
            wire current = pins[select_pin];
            wire changed = current != previous[select_pin];
            wire match = (select_mode == SAMPLE && due) ||
                         (select_mode == LEVEL && (open || due) && current == select_level) ||
                         (select_mode == EDGE && changed && (select_edge == 2 || current == select_edge[0]));

            always @(posedge clk) begin
                if (!rst_n || flush || (consume && ctx == CTX)) begin
                    live[i] <= 0;
                    observed[i] <= 0;
                    lost[i] <= 0;
                end else if (arm && ctx == CTX) begin
                    live[i] <= 1;
                    select_pin <= pin;
                    select_mode <= mode;
                    select_edge <= polarity;
                    select_level <= level;
                    has_expiry <= timed;
                    open <= !guarded || distance == 0 || distance[23];
                    guard_at <= target;
                    expiry_at <= expiry;
                end else if (live[i] && !ready[i]) begin
                    if (match) begin
                        observed[i] <= 1;
                        seen[i] <= cycle;
                        bit_value[i] <= current;
                    end else if (!open && due) begin
                        open <= 1;
                    end else if (select_mode == LEVEL && open && cycle == expiry_at && has_expiry) begin
                        lost[i] <= 1;
                    end
                end
            end
        end
    endgenerate
endmodule
