`default_nettype none

module pad_adapter_tb;
    reg clk, rst_n, ena;
    reg [7:0] ui_in, uio_in;
    wire [7:0] uo_out, uio_out, uio_oe, pin_sample;
    wire selected, host_cs_n, host_sck, host_mosi;
    reg host_miso, host_ready, safe;
    reg [7:0] open_drain, update_mask, update_value, update_oe;

    pad_adapter u (
        .clk(clk), .rst_n(rst_n), .ena(ena), .ui_in(ui_in), .uio_in(uio_in),
        .uo_out(uo_out), .uio_out(uio_out), .uio_oe(uio_oe),
        .pin_sample(pin_sample), .selected(selected), .host_cs_n(host_cs_n), .host_sck(host_sck), .host_mosi(host_mosi),
        .host_miso(host_miso), .host_ready(host_ready), .safe(safe), .open_drain(open_drain),
        .update_mask(update_mask), .update_value(update_value), .update_oe(update_oe)
    );
endmodule

`default_nettype wire
