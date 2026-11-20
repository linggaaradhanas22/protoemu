// EVAL-014: random push/pop against a reference queue. Override DEPTH and
// BYPASS with iverilog -P. Reports boundary edges where both sides tried.
`timescale 1ns / 1ps
module fifo_probe_tb;
    parameter DEPTH = 8, BYPASS = 0, STEPS = 20000;
    reg clk = 0, rst_n = 0, clear = 0, push = 0, pop = 0;
    reg [15:0] wdata = 0;
    wire [15:0] rdata;
    wire can_push, can_pop, do_push, do_pop;
    reg [15:0] model [0:63];
    integer head, tail, n, errors, seed, pushes, pops, both_full, both_empty, level;

    fifo_probe_queue #(.DEPTH(DEPTH), .BYPASS(BYPASS)) dut (
        clk, rst_n, clear, push, pop, wdata, rdata, can_push, can_pop, do_push, do_pop);

    always #5 clk = ~clk;

    initial begin
        head = 0; tail = 0; errors = 0; seed = 14; pushes = 0; pops = 0;
        both_full = 0; both_empty = 0;
        @(negedge clk) rst_n = 1;
        for (n = 0; n < STEPS; n = n + 1) begin
            @(negedge clk);
            // Bias the load so the queue spends time both full and empty.
            level = (n / 500) % 2;
            push = ({$random(seed)} % 100) < (level ? 70 : 30);
            pop = ({$random(seed)} % 100) < (level ? 30 : 70);
            wdata = $random(seed);
            #1;
            if (push && pop && tail - head == DEPTH) both_full = both_full + 1;
            if (push && pop && tail == head) both_empty = both_empty + 1;
            // Reference acceptance from the count before the edge.
            if (do_push !== (push && (tail - head < DEPTH || (BYPASS && pop && tail != head)))) begin
                errors = errors + 1;
                if (errors < 5) $display("step %0d push accept %b", n, do_push);
            end
            if (do_pop !== (pop && (tail != head || (BYPASS && push)))) begin
                errors = errors + 1;
                if (errors < 5) $display("step %0d pop accept %b", n, do_pop);
            end
            if (do_push) begin
                model[tail % 64] = wdata;
                tail = tail + 1;
                pushes = pushes + 1;
            end
            if (do_pop) begin
                if (rdata !== model[head % 64]) begin
                    errors = errors + 1;
                    if (errors < 5) $display("step %0d pop %h expected %h", n, rdata, model[head % 64]);
                end
                head = head + 1;
                pops = pops + 1;
            end
            @(posedge clk);
        end
        $display("fifo_probe_tb DEPTH=%0d BYPASS=%0d: %0d pushes, %0d pops, %0d full+both, %0d empty+both, %0d errors",
                 DEPTH, BYPASS, pushes, pops, both_full, both_empty, errors);
        $finish;
    end
endmodule
