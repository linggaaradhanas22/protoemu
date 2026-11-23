`default_nettype none

module timed_drive_tb;
    reg clk, rst_n, flush, detect_fault;
    reg fault_pending;
    reg [23:0] cycle, drive_deadline;
    reg [7:0] owner0, owner1, drive_mask, drive_value, drive_oe;
    reg drive_ctx, drive_valid;
    wire drive_credit, drive_ready, drive_reject, drive_empty;
    wire [7:0] update_mask, update_value, update_oe;

    always @(posedge clk)
        fault_pending <= rst_n && detect_fault;

    timed_drive u (
        .clk(clk), .rst_n(rst_n), .flush(flush || fault_pending), .cycle(cycle),
        .owner0(owner0), .owner1(owner1), .drive_valid(drive_valid), .drive_ctx(drive_ctx),
        .drive_deadline(drive_deadline), .drive_mask(drive_mask), .drive_value(drive_value),
        .drive_oe(drive_oe), .drive_credit(drive_credit), .drive_ready(drive_ready),
        .drive_reject(drive_reject), .drive_empty(drive_empty), .update_mask(update_mask),
        .update_value(update_value), .update_oe(update_oe)
    );
endmodule

`default_nettype wire
