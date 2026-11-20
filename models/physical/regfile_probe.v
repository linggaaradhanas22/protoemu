// EVAL-013 exploration (BLK-CORE): register-file write options for the
// two-word edge_delta result. Not production RTL.
//
// Two contexts, eight 16-bit registers each. All variants share:
//   - port A: one 16-bit write to any register of the issuing context;
//   - the offset pair: R0 <= off[15:0], R6 <= {9'b0, off[22:16]} (addoff, clear);
//   - clear: START/flush clears every register;
//   - two read ports and the 23-bit offset for the selected context.
// The low edge_delta word always uses port A. Only the high word differs:
//   VARIANT 0: hold it, then write it through port A in a later issue slot;
//   VARIANT 1: a narrow port writes {9'b0, hi[6:0]} to R2..R5 in the same edge;
//   VARIANT 2: a general second 16-bit write port to any register.
module regfile_probe #(parameter VARIANT = 0) (
    input clk, rst_n, clear,
    input ctx_a, we_a,
    input [2:0] addr_a,
    input [15:0] data_a,
    input off_we,
    input [22:0] off_data,
    input delta_we,
    input [1:0] delta_rd,      // Rd = R1..R4, so Rd + 1 = delta_rd + 2
    input [6:0] delta_hi,
    input wb_go,               // VARIANT 0: the held word owns this issue slot
    input we_b,                // VARIANT 2
    input [2:0] addr_b,
    input [15:0] data_b,
    input ctx_r,
    input [2:0] raddr_x, raddr_y,
    output [15:0] rx, ry,
    output [22:0] offset,
    output wb_pending
);
    reg [15:0] regs [0:15];    // {context, index}

    // VARIANT 0 holding register for the high word.
    reg hv, hctx;
    reg [1:0] hrd;
    reg [6:0] hdata;
    wire wb = (VARIANT == 0) && wb_go && hv;
    wire w0 = we_a || wb;
    wire c0 = wb ? hctx : ctx_a;
    wire [2:0] a0 = wb ? {1'b0, hrd} + 3'd2 : addr_a;
    wire [15:0] d0 = wb ? {9'b0, hdata} : data_a;
    wire [2:0] hi_addr = {1'b0, delta_rd} + 3'd2;
    assign wb_pending = (VARIANT == 0) && hv;

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            hv <= 1'b0;
            hctx <= 1'b0;
            hrd <= 2'd0;
            hdata <= 7'd0;
        end else if (VARIANT == 0) begin
            if (delta_we) begin
                hv <= 1'b1;
                hctx <= ctx_a;
                hrd <= delta_rd;
                hdata <= delta_hi;
            end else if (wb) begin
                hv <= 1'b0;
            end
        end
    end

    genvar i;
    generate
        for (i = 0; i < 16; i = i + 1) begin : reg_slot
            localparam [0:0] CTX = i / 8;
            localparam [2:0] IDX = i % 8;
            wire mine_a = w0 && c0 == CTX && a0 == IDX;
            wire mine_o = off_we && ctx_a == CTX && (IDX == 3'd0 || IDX == 3'd6);
            wire mine_n = VARIANT == 1 && delta_we && ctx_a == CTX && hi_addr == IDX;
            wire mine_b = VARIANT == 2 && we_b && ctx_a == CTX && addr_b == IDX;
            wire [15:0] off_word = IDX == 3'd0 ? off_data[15:0] : {9'b0, off_data[22:16]};
            always @(posedge clk) begin
                if (!rst_n || clear)
                    regs[i] <= 16'd0;
                else if (mine_a)
                    regs[i] <= d0;
                else if (mine_o)
                    regs[i] <= off_word;
                else if (mine_n)
                    regs[i] <= {9'b0, delta_hi};
                else if (mine_b)
                    regs[i] <= data_b;
            end
        end
    endgenerate

    assign rx = regs[{ctx_r, raddr_x}];
    assign ry = regs[{ctx_r, raddr_y}];
    assign offset = {regs[{ctx_r, 3'd6}][6:0], regs[{ctx_r, 3'd0}]};
endmodule
