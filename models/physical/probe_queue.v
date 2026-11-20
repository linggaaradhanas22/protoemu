// EVAL-002: four timestamped writes and one capture slot per context.
module probe_queue (
    input clk, rst_n, issue, capture, ctx,
    input [15:0] stamp, timer,
    input [4:0] pins, mask, data,
    output reg [4:0] out_mask, out_data,
    output reg [9:0] captured,
    output full
);
    reg [3:0] valid;
    reg [15:0] deadline [0:3];
    reg [4:0] masks [0:3];
    reg [4:0] values [0:3];
    reg [1:0] armed;
    reg [15:0] cap_deadline [0:1];
    wire [3:0] due;
    wire [3:0] take;
    wire [3:0] free = ~valid | due;
    genvar n;
    generate for (n = 0; n < 4; n = n + 1) begin: slot
        assign due[n] = valid[n] && deadline[n] == timer;
        if (n == 0) assign take[n] = issue && free[n];
        else assign take[n] = issue && free[n] && !(|free[n-1:0]);
    end endgenerate
    assign full = !(|free);
    integer i;
    reg [2:0] j;
    always @* begin
        out_mask = 0;
        out_data = 0;
        for (j = 0; j < 4; j = j + 1) if (due[j]) begin
            out_mask = out_mask | masks[j];
            out_data = (out_data & ~masks[j]) | (values[j] & masks[j]);
        end
    end
    always @(posedge clk) begin
        if (!rst_n) begin
            valid <= 0;
            armed <= 0;
            captured <= 0;
        end else begin
            valid <= (valid & ~due) | take;
            for (i = 0; i < 4; i = i + 1) if (take[i]) begin
                deadline[i] <= stamp;
                masks[i] <= mask;
                values[i] <= data;
            end
            for (i = 0; i < 2; i = i + 1) if (armed[i] && cap_deadline[i] == timer) begin
                captured[5*i+:5] <= pins;
                armed[i] <= 0;
            end
            if (capture) begin
                armed[ctx] <= 1;
                cap_deadline[ctx] <= stamp;
            end
        end
    end
endmodule
