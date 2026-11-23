// SPDX-License-Identifier: Apache-2.0
// BLK-DRIVE: Four unordered deadline slots and masked pad updates.

`default_nettype none

module timed_drive (
    input  wire        clk, rst_n, flush,
    input  wire [23:0] cycle,
    input  wire [7:0]  owner0, owner1,
    input  wire        drive_valid, drive_ctx,
    input  wire [23:0] drive_deadline,
    input  wire [7:0]  drive_mask, drive_value, drive_oe,
    output wire        drive_credit, drive_ready, drive_reject, drive_empty,
    output wire [7:0]  update_mask, update_value, update_oe
);
    reg [3:0] live;
    reg [23:0] due_at [0:3];
    reg [7:0] mask [0:3], value [0:3], oe [0:3];
    wire [3:0] due, free_slot, conflict;
    wire [7:0] due_mask [0:3], due_value [0:3], due_oe [0:3];

    wire enabled = rst_n && !flush;
    wire [7:0] owner = drive_ctx ? owner1 : owner0;
    wire [23:0] delta = drive_deadline - cycle;
    wire legal = delta != 0 && !delta[23] && drive_mask != 0 &&
                 (drive_mask & ~owner) == 0 && !(|conflict);

    // Credit depends on the slots, not the selected request. The core uses it to select a retry.
    assign drive_credit = enabled && (|free_slot);
    assign drive_ready = drive_valid && drive_credit && legal;
    assign drive_reject = enabled && drive_valid && !legal;
    assign drive_empty = live == 0;
    assign update_mask = due_mask[0] | due_mask[1] | due_mask[2] | due_mask[3];
    assign update_value = due_value[0] | due_value[1] | due_value[2] | due_value[3];
    assign update_oe = due_oe[0] | due_oe[1] | due_oe[2] | due_oe[3];

    genvar i;
    generate for (i = 0; i < 4; i = i + 1) begin : slot
        assign due[i] = enabled && live[i] && due_at[i] == cycle;
        assign free_slot[i] = !live[i] || due[i];
        assign conflict[i] = live[i] && due_at[i] == drive_deadline && (|(mask[i] & drive_mask));
        assign due_mask[i] = due[i] ? mask[i] : 8'b0;
        assign due_value[i] = due[i] ? value[i] : 8'b0;
        assign due_oe[i] = due[i] ? oe[i] : 8'b0;

        wire allocate;
        if (i == 0) begin : first
            assign allocate = drive_ready && free_slot[i];
        end else begin : later
            assign allocate = drive_ready && free_slot[i] && !(|free_slot[i-1:0]);
        end

        // Clearing live is sufficient: invalid slot data cannot reach either interface.
        always @(posedge clk) begin
            if (!enabled) live[i] <= 0;
            else if (allocate) begin
                live[i] <= 1;
                due_at[i] <= drive_deadline;
                mask[i] <= drive_mask;
                value[i] <= drive_value & drive_mask;
                oe[i] <= drive_oe & drive_mask;
            end else if (due[i]) live[i] <= 0;
        end
    end endgenerate
endmodule

`default_nettype wire
