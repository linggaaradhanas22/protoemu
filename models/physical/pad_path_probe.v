// EVAL-008 exploration for BLK-CORE, BLK-DRIVE and BLK-PADS, not production RTL.
module pad_path_probe #(parameter FORMAT = 0) (
    input wire clk, rst_n, issue_in, ctx_in,
    input wire [23:0] insn_in, stamp_in,
    input wire [22:0] offset_in,
    input wire rf_write,
    input wire [3:0] rf_addr,
    input wire [15:0] rf_data,
    input wire [7:0] open_drain_in, owner0_in, owner1_in,
    output reg [7:0] pad_value, pad_oe,
    output reg accepted, rejected, blocked
);
    reg [23:0] insn, stamp, timer;
    reg [22:0] offset;
    reg issue, ctx;
    reg [7:0] open_drain, owner0, owner1;
    reg [15:0] gpr [0:15];
    reg [3:0] live;
    reg [23:0] deadline_bank [0:3];
    reg [7:0] mask_bank [0:3], value_bank [0:3], oe_bank [0:3];

    wire is_pad = insn[4:0] == 5'd18;
    wire is_pair = insn[4:0] == 5'd19;
    wire compact = FORMAT != 1 && (is_pad || is_pair);
    wire vector = FORMAT != 0 && insn[4:0] == 5'd22;
    wire [7:0] pin_a = 8'b1 << insn[7:5];
    wire [7:0] pin_b = (is_pair ? 8'b1 : 8'b0) << insn[12:10];
    wire [15:0] vec = gpr[{ctx, insn[7:5]}];
    wire [7:0] mask = compact ? pin_a | pin_b : (vector ? vec[7:0] : 8'b0);
    wire [7:0] values = compact ? (({8{insn[8]}} & pin_a) | ({8{insn[13]}} & pin_b)) : vec[15:8];
    wire [7:0] oe = compact ? (({8{insn[9]}} & pin_a) | ({8{insn[14]}} & pin_b)) : insn[15:8];
    wire [8:0] immediate = compact ? (is_pair ? insn[23:15] : insn[18:10]) : {1'b0, insn[23:16]};
    wire malformed = !(compact || vector) || (compact && |(pin_a & pin_b)) ||
                     (compact && is_pad && |insn[23:19]);
    wire [23:0] relative = {1'b0, offset} + {15'b0, immediate};
    wire [23:0] deadline = stamp + relative;
    wire [23:0] delta = deadline - timer;
    wire [7:0] write_owner = ctx ? owner1 : owner0;

    wire [3:0] due, collides, free_slot, allocate;
    wire [7:0] due_masks [0:3], due_values [0:3], due_oe [0:3];
    wire legal = !malformed && !relative[23] && !delta[23] && (|delta) &&
                 (|mask) && !(|(mask & ~write_owner)) && !(|collides);
    wire take = issue && legal && (|free_slot);
    wire [7:0] merged_mask = due_masks[0] | due_masks[1] | due_masks[2] | due_masks[3];
    wire [7:0] merged_value = due_values[0] | due_values[1] | due_values[2] | due_values[3];
    wire [7:0] merged_oe = due_oe[0] | due_oe[1] | due_oe[2] | due_oe[3];

    genvar i;
    generate for (i = 0; i < 4; i = i + 1) begin: queue
        assign due[i] = live[i] && deadline_bank[i] == timer;
        assign collides[i] = live[i] && deadline_bank[i] == deadline && (|(mask_bank[i] & mask));
        assign free_slot[i] = !live[i] || due[i];
        if (i == 0) begin: first
            assign allocate[i] = take && free_slot[i];
        end else begin: rest
            assign allocate[i] = take && free_slot[i] && !(|free_slot[i-1:0]);
        end
        assign due_masks[i] = {8{due[i]}} & mask_bank[i];
        assign due_values[i] = due_masks[i] & value_bank[i];
        assign due_oe[i] = due_masks[i] & oe_bank[i];
        always @(posedge clk) begin
            if (!rst_n)
                live[i] <= 0;
            else if (allocate[i]) begin
                live[i] <= 1;
                deadline_bank[i] <= deadline;
                mask_bank[i] <= mask;
                value_bank[i] <= values;
                oe_bank[i] <= oe;
            end else if (due[i])
                live[i] <= 0;
        end
    end endgenerate

    always @(posedge clk) begin
        if (rf_write)
            gpr[rf_addr] <= rf_data;
        if (!rst_n) begin
            issue <= 0;
            timer <= 0;
            pad_value <= 0;
            pad_oe <= 0;
            {accepted, rejected, blocked} <= 0;
        end else begin
            timer <= timer + 1'b1;
            {issue, ctx} <= {issue_in, ctx_in};
            {insn, stamp, offset} <= {insn_in, stamp_in, offset_in};
            {open_drain, owner0, owner1} <= {open_drain_in, owner0_in, owner1_in};
            pad_value <= (pad_value & ~merged_mask) | (merged_value & ~open_drain);
            pad_oe <= (pad_oe & ~merged_mask) | (merged_oe & ~(merged_value & open_drain));
            {accepted, rejected, blocked} <= {take, issue && !legal, issue && legal && !take};
        end
    end
endmodule
