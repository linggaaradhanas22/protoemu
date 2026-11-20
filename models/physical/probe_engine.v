// EVAL-002: fetch/execute staging, context register mux, ALU, and return stack proxy.
module probe_engine #(parameter N = 2, AW = 7) (
    input clk, rst_n, run, stall,
    input [23:0] code,
    input [15:0] timer,
    input [4:0] pins,
    output [AW-1:0] fetch_addr,
    output fetch, issue, capture, lane_arm, ctx,
    output [15:0] stamp,
    output [4:0] mask, data,
    output [3:0] descriptor_index,
    output reg [15:0] result
);
    reg phase, context_sel;
    wire select = N == 2 ? context_sel : 1'b0;
    reg [AW-1:0] pc [0:N-1];
    reg [AW-1:0] returns [0:2*N-1];
    reg [1:0] depth [0:N-1];
    reg [15:0] regs [0:N*8-1];
    wire [3:0] a = {select, code[7:5]};
    wire [3:0] b = {select, code[10:8]};
    wire [3:0] zero = {select, 3'b000};
    wire [15:0] src = regs[a];
    wire [15:0] input_word = {11'b0, pins};
    wire [15:0] imm = code[23:8];
    wire [4:0] op = code[4:0];
    integer i;

    assign fetch = run && !phase;
    assign fetch_addr = pc[select];
    assign ctx = select;
    assign issue = run && phase && (op == 3 || op == 4);
    assign capture = run && phase && (op == 5 || op == 6);
    assign lane_arm = run && phase && op == 13;
    assign descriptor_index = code[8:5];
    assign stamp = regs[zero] + {7'b0, code[23:15]};
    assign mask = code[9:5];
    assign data = op == 4 ? {4'b0, src[15]} | code[14:10] : code[14:10];

    always @(posedge clk) begin
        if (!rst_n || !run) begin
            phase <= 0;
            context_sel <= 0;
            result <= 0;
            for (i = 0; i < N; i = i + 1) begin
                pc[i] <= 0;
                depth[i] <= 0;
            end
            for (i = 0; i < 2*N; i = i + 1) returns[i] <= 0;
            for (i = 0; i < 8*N; i = i + 1) regs[i] <= 0;
        end else if (!stall) begin
            phase <= !phase;
            if (phase) begin
                context_sel <= !context_sel;
                pc[select] <= pc[select] + 1'b1;
                case (op)
                    1: regs[a] <= imm;
                    2: regs[a] <= src + imm;
                    4: regs[a] <= src << 1;
                    5: regs[b] <= {regs[b][14:0], pins[code[7:5]]};
                    6: regs[zero] <= timer;
                    7: if (depth[select] < 2) begin
                        returns[{select, depth[select][0]}] <= pc[select] + 1'b1;
                        depth[select] <= depth[select] + 1'b1;
                        pc[select] <= code[5+:AW];
                    end
                    8: if (depth[select] != 0) begin
                        pc[select] <= returns[{select, !depth[select][0]}];
                        depth[select] <= depth[select] - 1'b1;
                    end
                    9: begin
                        regs[a] <= src - 1'b1;
                        if (src != 16'd1) pc[select] <= code[8+:AW];
                    end
                    10: if (src != 0) pc[select] <= code[8+:AW];
                    12: result <= src;
                    15: result <= input_word ^ regs[b];
                    default: begin end
                endcase
            end
        end
    end
endmodule
