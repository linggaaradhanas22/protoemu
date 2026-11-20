// EVAL-013: drive one random instruction stream into all three register-file
// variants and a reference model. Each instruction takes two cycles; VARIANT 0
// writes the held edge_delta high word in the second one.
`timescale 1ns / 1ps
module regfile_probe_tb;
    reg clk = 0, rst_n = 0, clear = 0;
    reg ctx_a = 0, we_a = 0, off_we = 0, delta_we = 0, wb_go = 0, we_b = 0;
    reg [2:0] addr_a = 0, addr_b = 0;
    reg [15:0] data_a = 0, data_b = 0;
    reg [22:0] off_data = 0;
    reg [1:0] delta_rd = 0;
    reg [6:0] delta_hi = 0;
    reg [15:0] expected [0:15];
    wire [15:0] rx0, ry0, rx1, ry1, rx2, ry2;
    wire [22:0] of0, of1, of2;
    wire p0, p1, p2;
    integer n, k, op, errors, seed, deltas;

    regfile_probe #(.VARIANT(0)) v0 (clk, rst_n, clear, ctx_a, we_a, addr_a, data_a, off_we, off_data,
        delta_we, delta_rd, delta_hi, wb_go, we_b, addr_b, data_b, 1'b0, 3'd0, 3'd0, rx0, ry0, of0, p0);
    regfile_probe #(.VARIANT(1)) v1 (clk, rst_n, clear, ctx_a, we_a, addr_a, data_a, off_we, off_data,
        delta_we, delta_rd, delta_hi, 1'b0, 1'b0, addr_b, data_b, 1'b0, 3'd0, 3'd0, rx1, ry1, of1, p1);
    regfile_probe #(.VARIANT(2)) v2 (clk, rst_n, clear, ctx_a, we_a, addr_a, data_a, off_we, off_data,
        1'b0, delta_rd, delta_hi, 1'b0, we_b, addr_b, data_b, 1'b0, 3'd0, 3'd0, rx2, ry2, of2, p2);

    always #5 clk = ~clk;

    task idle;
        begin
            {clear, we_a, off_we, delta_we, wb_go, we_b} = 0;
        end
    endtask

    initial begin
        errors = 0;
        deltas = 0;
        seed = 13;
        for (k = 0; k < 16; k = k + 1) expected[k] = 0;
        idle;
        @(negedge clk) rst_n = 1;
        for (n = 0; n < 4000; n = n + 1) begin
            @(negedge clk);
            idle;
            op = {$random(seed)} % 16;
            ctx_a = $random(seed);
            if (op == 0) begin
                clear = 1;
                for (k = 0; k < 16; k = k + 1) expected[k] = 0;
            end else if (op < 7) begin
                we_a = 1;
                addr_a = $random(seed);
                data_a = $random(seed);
                expected[{ctx_a, addr_a}] = data_a;
            end else if (op < 11) begin
                off_we = 1;
                off_data = $random(seed);
                expected[{ctx_a, 3'd0}] = off_data[15:0];
                expected[{ctx_a, 3'd6}] = {9'b0, off_data[22:16]};
            end else begin
                // edge_delta: Rd low through port A, offset pair cleared, Rd + 1 high.
                deltas = deltas + 1;
                delta_rd = $random(seed);
                delta_hi = $random(seed);
                we_a = 1;
                addr_a = {1'b0, delta_rd} + 3'd1;
                data_a = $random(seed);
                off_we = 1;
                off_data = 0;
                delta_we = 1;
                we_b = 1;
                addr_b = {1'b0, delta_rd} + 3'd2;
                data_b = {9'b0, delta_hi};
                expected[{ctx_a, addr_a}] = data_a;
                expected[{ctx_a, 3'd0}] = 0;
                expected[{ctx_a, 3'd6}] = 0;
                expected[{ctx_a, addr_b}] = data_b;
            end
            @(negedge clk);
            idle;
            wb_go = 1;  // Free issue slot for the VARIANT 0 held word.
            @(posedge clk);
            #1;
            for (k = 0; k < 16; k = k + 1) begin
                if (v0.regs[k] !== expected[k] || v1.regs[k] !== expected[k] || v2.regs[k] !== expected[k]) begin
                    errors = errors + 1;
                    if (errors < 5)
                        $display("step %0d reg %0d expected %h got %h %h %h", n, k, expected[k],
                                 v0.regs[k], v1.regs[k], v2.regs[k]);
                end
            end
            if (p0) begin
                errors = errors + 1;
                $display("step %0d: VARIANT 0 still holds a word", n);
            end
        end
        $display("regfile_probe_tb: %0d instructions, %0d edge_delta, %0d errors", n, deltas, errors);
        $finish;
    end
endmodule
