// SPDX-License-Identifier: Apache-2.0
// BLK-PROGRAM: Load shared program words and register instruction fetches.

`default_nettype none

module program_store (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        prog_write_valid,
    input  wire [6:0]  prog_write_index,
    input  wire [23:0] prog_write_word,
    input  wire        load_active,
    input  wire        image_valid,
    input  wire        running,
    input  wire [7:0]  word_count,
    input  wire        fetch_req_valid,
    input  wire [6:0]  fetch_pc,
    output reg         fetch_rsp_valid,
    output reg         fetch_rsp_fault,
    output reg  [23:0] fetch_instruction
);
    reg [23:0] words [0:127];
    wire fetch_enabled = fetch_req_valid && running && image_valid && !load_active;
    wire in_image = {1'b0, fetch_pc} < word_count;

    // The loader must rewrite the whole declared image before making it executable.
    always @(posedge clk) begin
        if (rst_n && prog_write_valid && load_active && !running && !image_valid)
            words[prog_write_index] <= prog_write_word;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            fetch_rsp_valid <= 1'b0;
            fetch_rsp_fault <= 1'b0;
            fetch_instruction <= 24'b0;
        end else begin
            fetch_rsp_valid <= fetch_enabled;
            fetch_rsp_fault <= fetch_enabled && !in_image;
            if (fetch_enabled && in_image)
                fetch_instruction <= words[fetch_pc];
        end
    end
endmodule

`default_nettype wire
