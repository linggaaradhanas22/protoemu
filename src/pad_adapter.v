// SPDX-License-Identifier: Apache-2.0
// BLK-PADS: Synchronize external inputs and register host and protocol outputs.

`default_nettype none

module pad_adapter (
    input  wire        clk, rst_n, ena,
    input  wire [7:0]  ui_in, uio_in,
    output wire [7:0]  uo_out,
    output reg  [7:0]  uio_out, uio_oe,

    output wire [7:0]  pin_sample,
    output wire        selected, host_cs_n, host_sck, host_mosi,
    input  wire        host_miso, host_ready,

    input  wire        safe,
    input  wire [7:0]  open_drain, update_mask, update_value, update_oe
);
    (* async_reg = "true" *) reg [11:0] input_meta, input_sync;
    reg miso_q, ready_q;

    assign {selected, host_mosi, host_sck, host_cs_n, pin_sample} = input_sync;
    assign uo_out = {3'b0, ready_q, miso_q, 3'b0};

    always @(posedge clk) begin
        if (!rst_n) begin
            input_meta <= {4'b0001, 8'b0}; // CS idles high during reset.
            input_sync <= {4'b0001, 8'b0};
        end else begin
            input_meta <= {ena, ui_in[2:0], uio_in};
            input_sync <= input_meta;
        end
    end

    // Protocol safety does not suppress host replies after STOP or a core fault.
    always @(posedge clk) begin
        if (!rst_n || !selected) begin
            miso_q <= 0;
            ready_q <= 0;
        end else begin
            miso_q <= host_miso;
            ready_q <= host_ready;
        end
        if (!rst_n || !selected || safe) begin
            uio_out <= 0;
            uio_oe <= 0;
        end else begin
            uio_out <= (uio_out & ~update_mask) | (update_value & update_mask & ~open_drain);
            uio_oe <= (uio_oe & ~update_mask) | (update_oe & update_mask & ~(open_drain & update_value));
        end
    end

    wire _unused = &{1'b0, ui_in[7:3]};
endmodule

`default_nettype wire
