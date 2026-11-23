// SPDX-License-Identifier: Apache-2.0
// BLK-HOST: Per-context ingress staging and egress reply retention.

`default_nettype none

module host_payload (
    input  wire        clk, rst_n, clear,
    input  wire [1:0]  ingress_pop, egress_push,
    input  wire [15:0] egress_word,
    output wire [1:0]  ingress_ready, egress_ready,
    output wire [31:0] ingress_words,

    input  wire        host_ctx,
    input  wire [15:0] host_word,
    input  wire        host_write, host_stage, host_commit, host_abort,
    input  wire        host_commit_word,
    input  wire [1:0]  host_stage_index,
    output wire        host_write_ready, host_stage_ready,
    output wire [3:0]  host_ingress_free,
    output wire [2:0]  host_staged_count,
    input  wire [1:0]  host_peek,
    input  wire [2:0]  host_release,
    output wire [3:0]  host_egress_count,
    output wire [15:0] host_egress_word
);
    wire [1:0] write_ready, stage_ready;
    wire [2:0] staged_count [0:1];
    wire [3:0] eg_count [0:1];
    wire [3:0] in_free [0:1];
    wire [15:0] peek_word [0:1];
    assign host_write_ready = write_ready[host_ctx];
    assign host_stage_ready = stage_ready[host_ctx];
    assign host_staged_count = staged_count[host_ctx];
    assign host_ingress_free = in_free[host_ctx];
    assign host_egress_count = eg_count[host_ctx];
    assign host_egress_word = peek_word[host_ctx];

    genvar i;
    generate for (i = 0; i < 2; i = i + 1) begin : context_fifo
        localparam [0:0] CTX = i == 1;
        reg [15:0] ingress [0:7], egress [0:7];
        reg [2:0] in_head, in_tail, eg_head, eg_tail;
        reg [3:0] in_used, eg_used;
        reg [2:0] staged;
        wire mine = host_ctx == CTX;
        wire aborting = host_abort;
        wire committing = mine && host_commit && !aborting;
        wire can_write = rst_n && !clear && !aborting && !committing;
        wire write_one = mine && host_write && write_ready[i];
        wire stage_one = mine && host_stage && stage_ready[i] && !write_one;
        wire last_word = committing && host_commit_word && staged < 4 && in_used + {1'b0, staged} < 8;
        wire [2:0] add_count = committing ? staged + {2'b0, last_word} : {2'b0, write_one};
        wire in_pop = ingress_pop[i] && ingress_ready[i];
        wire eg_push = egress_push[i] && egress_ready[i];
        wire [3:0] requested = {1'b0, host_release};
        wire [3:0] remove_count = mine && requested <= 4 && requested <= eg_used ? requested : 4'd0;
        wire [2:0] stage_addr = in_tail + {1'b0, host_stage_index};
        wire [2:0] commit_addr = in_tail + staged;
        wire [2:0] peek_addr = eg_head + {1'b0, host_peek};

        // Only committed occupancy controls the core. There is no same-edge bypass.
        assign ingress_ready[i] = in_used != 0;
        assign egress_ready[i] = eg_used != 8;
        assign ingress_words[i*16 +: 16] = ingress_ready[i] ? ingress[in_head] : 16'd0;
        assign write_ready[i] = can_write && staged == 0 && in_used != 8;
        assign stage_ready[i] = can_write && staged == {1'b0, host_stage_index} &&
                                in_used + {1'b0, staged} < 8;
        assign staged_count[i] = staged;
        assign in_free[i] = 4'd8 - in_used;
        assign eg_count[i] = eg_used;
        assign peek_word[i] = {2'b0, host_peek} < eg_used ? egress[peek_addr] : 16'd0;

        always @(posedge clk) begin
            if (!rst_n || clear) begin
                in_head <= 0; in_tail <= 0; in_used <= 0; staged <= 0;
                eg_head <= 0; eg_tail <= 0; eg_used <= 0;
            end else begin
                if (write_one) ingress[in_tail] <= host_word;
                else if (stage_one) ingress[stage_addr] <= host_word;
                else if (last_word) ingress[commit_addr] <= host_word;
                if (aborting || committing) staged <= 0;
                else if (stage_one) staged <= staged + 3'd1;

                in_head <= in_head + {2'b0, in_pop};
                in_tail <= in_tail + add_count;
                in_used <= in_used + {1'b0, add_count} - {3'b0, in_pop};

                if (eg_push) egress[eg_tail] <= egress_word;
                eg_tail <= eg_tail + {2'b0, eg_push};
                eg_head <= eg_head + remove_count[2:0];
                eg_used <= eg_used + {3'b0, eg_push} - remove_count;
            end
        end
    end endgenerate
endmodule

`default_nettype wire
