`timescale 1ns/1ps

module pad_path_probe_tb;
    reg clk = 0;
    always #8.333 clk = ~clk;
    reg rst_n = 0;
    reg issue_in = 0;
    reg [23:0] insn_in = 0, stamp_in = 0;
    reg [22:0] offset_in = 0;
    reg rf_write = 0;
    reg [3:0] rf_addr = 0;
    reg [15:0] rf_data = 0;
    reg [7:0] owner0 = 8'hff;
    wire [7:0] pad_value, pad_oe;
    wire accepted, rejected, blocked;

    pad_path_probe #(.FORMAT(2)) dut (
        .clk(clk), .rst_n(rst_n), .issue_in(issue_in), .ctx_in(1'b0),
        .insn_in(insn_in), .stamp_in(stamp_in), .offset_in(offset_in),
        .rf_write(rf_write), .rf_addr(rf_addr), .rf_data(rf_data),
        .open_drain_in(8'h80), .owner0_in(owner0), .owner1_in(8'h00),
        .pad_value(pad_value), .pad_oe(pad_oe), .accepted(accepted),
        .rejected(rejected), .blocked(blocked)
    );

    function [23:0] pair;
        input [2:0] a, b;
        begin pair = {9'd0, 1'b1, 1'b0, b, 1'b1, 1'b1, a, 5'd19}; end
    endfunction

    task send;
        input [23:0] code, deadline;
        input [2:0] expect_status;
        begin
            @(negedge clk);
            issue_in = 1;
            insn_in = code;
            stamp_in = deadline;
            @(negedge clk);
            issue_in = 0;
            @(negedge clk);
            if ({accepted, rejected, blocked} !== expect_status)
                $fatal(1, "deadline %d: expected flags %b, got %b", deadline,
                       expect_status, {accepted, rejected, blocked});
        end
    endtask

    initial begin
        repeat (3) @(negedge clk);
        rst_n = 1;
        rf_write = 1;
        rf_data = 16'hf0ff;
        @(negedge clk);
        rf_write = 0;
        send(pair(0, 1), 24'd30, 3'b100);
        send(pair(2, 3), 24'd30, 3'b100);
        send(pair(4, 5), 24'd30, 3'b100);
        send(pair(6, 7), 24'd30, 3'b100);
        send(pair(0, 1), 24'd30, 3'b010);
        send({8'd0, 8'hff, 3'd0, 5'd22}, 24'd36, 3'b001);
        while (dut.timer != 29) @(negedge clk);
        issue_in = 1;
        insn_in = {8'd0, 8'hff, 3'd0, 5'd22};
        stamp_in = 36;
        @(negedge clk);
        issue_in = 0;
        if ({pad_value, pad_oe} !== 16'h0000) $fatal(1, "early pad change");
        @(negedge clk);
        if (!accepted || {pad_value, pad_oe} !== 16'h55ff)
            $fatal(1, "same-edge merge or slot reuse failed");
        while (dut.timer != 37) @(negedge clk);
        if ({pad_value, pad_oe} !== 16'h707f) $fatal(1, "vector or open-drain release failed");
        send(pair(0, 1), 24'd39, 3'b010);
        owner0 = 8'h01;
        send(pair(0, 1), 24'd56, 3'b010);
        $display("PASS: four-way retirement, slot reuse, vector OE, collision, full, late and ownership");
        $finish;
    end
    initial begin
        #1600 $fatal(1, "probe test timeout");
    end
endmodule
