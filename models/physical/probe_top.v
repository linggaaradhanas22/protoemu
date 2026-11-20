// EVAL-002: integration envelope, not a Tiny Tapeout top or an ISA implementation.
module probe_top #(parameter ARCH = 0) (
    input clk, rst_n,
    input [4:0] pin_in,
    input [7:0] load_byte,
    input [1:0] load_bank,
    input load_strobe, load_clear, load_commit,
    input [4:0] od_enable,
    output reg [4:0] pin_out, pin_oe,
    output reg [15:0] observe
);
    localparam W = ARCH == 0 ? 32 : 24;
    localparam AW = ARCH == 1 ? 7 : 6;
    localparam [1:0] LAST_BYTE = ARCH == 0 ? 2'd3 : 2'd2;
    reg [4:0] sync_a, sync_b;
    reg [15:0] timer;
    reg run;
    reg [1:0] byte_index, target;
    reg [AW-1:0] address;
    reg [W-1:0] word;
    reg write_word;
    wire [4:0] mask0, mask1, data0, data1;
    wire [15:0] observe0, observe1;
    wire [4:0] mask = mask0 | mask1;
    wire [4:0] data = (data0 & mask0 & ~mask1) | (data1 & mask1);

    always @(posedge clk) begin
        sync_a <= pin_in;
        sync_b <= sync_a;
        if (!rst_n) begin
            run <= 0;
            timer <= 0;
            address <= 0;
            byte_index <= 0;
            write_word <= 0;
            pin_out <= 0;
            pin_oe <= 0;
            observe <= 0;
        end else begin
            write_word <= 0;
            if (load_clear) begin
                run <= 0;
                address <= 0;
                byte_index <= 0;
                timer <= 0;
            end else if (!run) begin
                if (write_word) address <= address + 1'b1;
                if (load_strobe) begin
                    word <= {load_byte, word[W-1:8]};
                    if (byte_index == LAST_BYTE) begin
                        write_word <= 1;
                        byte_index <= 0;
                        target <= load_bank;
                    end else byte_index <= byte_index + 1'b1;
                end
                if (load_commit) run <= 1;
            end else begin
                timer <= timer + 1'b1;
                pin_out <= (pin_out & ~mask) | (data & ~od_enable);
                pin_oe <= (pin_oe & ~mask) | (mask & ~(od_enable & data));
                observe <= observe0 ^ observe1;
            end
        end
    end

    genvar k;
    generate if (ARCH == 0) begin: dedicated
        wire [4:0] masks [0:1], values [0:1];
        wire [15:0] observations [0:1];
        for (k = 0; k < 2; k = k + 1) begin: engine
            wire [31:0] code;
            wire [5:0] pc;
            wire fetch, issue, capture, stall;
            wire [15:0] stamp, result;
            wire [4:0] m, d, sampled;
            probe_store #(.W(W), .AW(AW)) store(clk, write_word && target == k, fetch,
                                                address, pc, word, code);
            probe_engine #(.N(1), .AW(AW)) core(clk, rst_n, run, stall, code[23:0], timer, sync_b,
                pc, fetch, issue, capture, , , stamp, m, d, , result);
            probe_direct io(clk, rst_n && run, issue, capture, timer, stamp, sync_b, m, d,
                            masks[k], values[k], sampled, stall);
            assign observations[k] = result ^ {3'b0, code[31:24], sampled};
        end
        assign {mask1, mask0} = {masks[1], masks[0]};
        assign {data1, data0} = {values[1], values[0]};
        assign {observe1, observe0} = {observations[1], observations[0]};
    end else begin: shared
        wire [23:0] code;
        wire [AW-1:0] pc;
        wire fetch, issue, capture, arm, ctx, stall;
        wire [15:0] stamp, result;
        wire [4:0] m, d;
        wire [3:0] descriptor_index;
        probe_store #(.W(W), .AW(AW)) store(clk, write_word && target == 0, fetch,
                                            address, pc, word, code);
        probe_engine #(.N(2), .AW(AW)) core(clk, rst_n, run, stall, code, timer, sync_b,
             pc, fetch, issue, capture, arm, ctx, stamp, m, d, descriptor_index, result);
        if (ARCH == 1) begin: queued
            wire [9:0] sampled;
            wire full;
            probe_queue io(clk, rst_n && run, issue, capture, ctx, stamp, timer, sync_b,
                           m, d, mask0, data0, sampled, full);
            assign stall = full && issue;
            assign {mask1, data1} = 0;
            assign {observe1, observe0} = {6'b0, sampled, result};
        end else begin: lanes
            wire [4:0] lane_mask [0:1], lane_data [0:1];
            wire [15:0] lane_result [0:1];
            wire [1:0] done;
            wire [4:0] sampled;
            probe_direct io(clk, rst_n && run, issue, capture, timer, stamp, sync_b, m, d,
                            mask0, data0, sampled, stall);
            for (k = 0; k < 2; k = k + 1) begin: lane
                reg [3:0] read_addr;
                reg [2:0] reading;
                wire [23:0] desc;
                wire kick = arm && ctx == k;
                always @(posedge clk) begin
                    if (!rst_n) reading <= 0;
                    else if (kick) begin
                        read_addr <= {descriptor_index[1:0], 2'b00};
                        reading <= 4;
                    end else if (reading != 0) begin
                        read_addr <= read_addr + 1'b1;
                        reading <= reading - 1'b1;
                    end
                end
                probe_store #(.W(24), .AW(4)) bank(clk, write_word && target == k + 1,
                    reading != 0, address[3:0], read_addr, word, desc);
                probe_lane io_lane(clk, rst_n && run, kick, desc, result, sync_b,
                    lane_mask[k], lane_data[k], lane_result[k], done[k]);
            end
            assign mask1 = lane_mask[0] | lane_mask[1];
            assign data1 = (lane_data[0] & lane_mask[0] & ~lane_mask[1]) | (lane_data[1] & lane_mask[1]);
            assign observe0 = result ^ {9'b0, done, sampled};
            assign observe1 = lane_result[0] ^ lane_result[1];
        end
    end endgenerate
endmodule
