// Exploratory BLK-DRIVE queue and registered BLK-PADS output stage for EVAL-018.
module full_core_drive (
    input clk, rst_n, flush,
    input [23:0] cycle, deadline,
    input [7:0] mask, values, enables, owner, open_drain,
    input valid,
    output credit, empty, accept, reject,
    output reg [7:0] pad_value, pad_oe
);
    reg [3:0] live;
    reg [23:0] due_at [0:3];
    reg [7:0] slot_mask [0:3], slot_value [0:3], slot_oe [0:3];
    wire [3:0] due, free_slot, conflict;
    wire [7:0] due_mask [0:3], due_value [0:3], due_oe [0:3];
    wire [7:0] merged_mask = due_mask[0] | due_mask[1] | due_mask[2] | due_mask[3];
    wire [7:0] merged_value = due_value[0] | due_value[1] | due_value[2] | due_value[3];
    wire [7:0] merged_oe = due_oe[0] | due_oe[1] | due_oe[2] | due_oe[3];
    wire [23:0] delta = deadline - cycle;

    assign credit = |free_slot;
    assign empty = !(|live);
    assign reject = valid && (delta == 0 || delta[23] || !(|mask) || |(mask & ~owner) || |conflict);
    assign accept = valid && credit && !reject && !flush;

    genvar i;
    generate
        for (i = 0; i < 4; i = i + 1) begin : slot
            wire allocate;
            assign due[i] = live[i] && due_at[i] == cycle;
            assign free_slot[i] = !live[i] || due[i];
            assign conflict[i] = live[i] && due_at[i] == deadline && |(slot_mask[i] & mask);
            assign due_mask[i] = due[i] ? slot_mask[i] : 8'b0;
            assign due_value[i] = slot_value[i] & due_mask[i];
            assign due_oe[i] = slot_oe[i] & due_mask[i];
            if (i == 0) begin : first
                assign allocate = accept && free_slot[i];
            end else begin : next_slot
                assign allocate = accept && free_slot[i] && !(|free_slot[i-1:0]);
            end
            always @(posedge clk) begin
                if (!rst_n || flush) begin
                    live[i] <= 0;
                end else if (allocate) begin
                    live[i] <= 1;
                    due_at[i] <= deadline;
                    slot_mask[i] <= mask;
                    slot_value[i] <= values;
                    slot_oe[i] <= enables;
                end else if (due[i]) begin
                    live[i] <= 0;
                end
            end
        end
    endgenerate

    always @(posedge clk) begin
        if (!rst_n || flush) begin
            pad_value <= 0;
            pad_oe <= 0;
        end else begin
            pad_value <= (pad_value & ~merged_mask) | (merged_value & ~open_drain);
            pad_oe <= (pad_oe & ~merged_mask) | (merged_oe & ~(merged_value & open_drain));
        end
    end
endmodule
