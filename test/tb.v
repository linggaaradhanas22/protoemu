`default_nettype none
`timescale 1ns / 1ps

/* This testbench just instantiates the module and makes some convenient wires
   that can be driven / tested by the cocotb test.py.
*/
module tb ();

  // Dump the signals to a FST file. You can view it with gtkwave or surfer.
  initial begin
    $dumpfile("tb.fst");
    $dumpvars(0, tb);
    #1;
  end

  // Wire up the inputs and outputs:
  reg clk;
  reg rst_n;
  reg ena;
  reg [7:0] ui_in;
  reg [7:0] uio_in;
  wire [7:0] uo_out;
  wire [7:0] uio_out;
  wire [7:0] uio_oe;

  // Replace tt_um_example with your module name:
  tt_um_example user_project (
      .ui_in  (ui_in),    // Dedicated inputs
      .uo_out (uo_out),   // Dedicated outputs
      .uio_in (uio_in),   // IOs: Input path
      .uio_out(uio_out),  // IOs: Output path
      .uio_oe (uio_oe),   // IOs: Enable path (active high: 0=input, 1=output)
      .ena    (ena),      // enable - goes high when design is selected
      .clk    (clk),      // clock
      .rst_n  (rst_n)     // not reset
  );

`ifndef GL_TEST
  issue_core_tb core_tb ();
  timed_drive_tb drive_tb ();
  timed_capture_tb capture_tb ();
  pad_adapter_tb pad_tb ();

  reg timer_clk, timer_rst_n;
  wire [23:0] cycle;
  wire [3:0] short_cycle;
  cycle_timer timer (.clk(timer_clk), .rst_n(timer_rst_n), .cycle(cycle));
  cycle_timer #(.WIDTH(4)) short_timer (
      .clk(timer_clk), .rst_n(timer_rst_n), .cycle(short_cycle)
  );

  reg prog_clk, prog_rst_n;
  reg prog_write_valid, load_active, image_valid, running, fetch_req_valid;
  reg [6:0] prog_write_index, fetch_pc;
  reg [7:0] word_count;
  reg [23:0] prog_write_word;
  wire fetch_rsp_valid, fetch_rsp_fault;
  wire [23:0] fetch_instruction;

  program_store store (
      .clk(prog_clk), .rst_n(prog_rst_n),
      .prog_write_valid(prog_write_valid), .prog_write_index(prog_write_index),
      .prog_write_word(prog_write_word), .load_active(load_active),
      .image_valid(image_valid), .running(running), .word_count(word_count),
      .fetch_req_valid(fetch_req_valid), .fetch_pc(fetch_pc),
      .fetch_rsp_valid(fetch_rsp_valid), .fetch_rsp_fault(fetch_rsp_fault),
      .fetch_instruction(fetch_instruction)
  );
`endif

endmodule
