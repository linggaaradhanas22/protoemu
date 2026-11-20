// EVAL-015: random multi-word host transfers against reference queues while
// the core pushes (egress) or pops (ingress) one word at random.
`timescale 1ns / 1ps
module fifo_multi_probe_tb;
    parameter DEPTH = 8, FRAMES = 3000;
    localparam AW = $clog2(DEPTH);
    reg clk = 0, rst_n = 0;
    // Ingress: host writes many, core pops one.
    reg in_write = 0, in_pop = 0;
    reg [AW-1:0] in_slot = 0;
    reg [AW:0] in_commit = 0;
    reg [15:0] in_wdata = 0;
    wire [15:0] in_rdata;
    wire in_can_pop;
    wire [AW:0] in_count;
    // Egress: core pushes one, host reads many.
    reg eg_push = 0;
    reg [AW-1:0] eg_peek = 0;
    reg [AW:0] eg_free = 0;
    reg [15:0] eg_wdata = 0;
    wire [15:0] eg_rdata;
    wire eg_can_push;
    wire [AW:0] eg_count;
    reg [15:0] in_ref [0:65535];
    reg [15:0] eg_ref [0:65535];
    integer in_head, in_tail, eg_head, eg_tail, f, i, k, errors, seed, in_words, eg_words;
    reg core_on = 1;

    fifo_multi_ingress #(.DEPTH(DEPTH)) ingress (clk, rst_n, 1'b0, in_write, in_slot, in_wdata, in_commit,
                                                 in_pop, in_rdata, in_can_pop, in_count);
    fifo_multi_egress #(.DEPTH(DEPTH)) egress (clk, rst_n, 1'b0, eg_push, eg_wdata, eg_peek, eg_free,
                                               eg_rdata, eg_can_push, eg_count);

    always #5 clk = ~clk;

    // Core side, every cycle: random single pops and pushes, checked against the references.
    always @(negedge clk) if (rst_n) begin
        in_pop = core_on && {$random(seed)} % 3 == 0;
        eg_push = core_on && {$random(seed)} % 3 == 0;
        eg_wdata = $random(seed);
        #1;
        if (in_pop && in_can_pop) begin
            if (in_rdata !== in_ref[in_head]) begin
                errors = errors + 1;
                if (errors < 5) $display("ingress pop %h expected %h", in_rdata, in_ref[in_head]);
            end
            in_head = in_head + 1;
        end
        if (eg_push && eg_can_push) begin
            eg_ref[eg_tail] = eg_wdata;
            eg_tail = eg_tail + 1;
        end
    end

    initial begin
        in_head = 0; in_tail = 0; eg_head = 0; eg_tail = 0; errors = 0; seed = 15;
        in_words = 0; eg_words = 0;
        @(negedge clk) rst_n = 1;
        for (f = 0; f < FRAMES; f = f + 1) begin
            // Host WRITEN: write k tentative words, then commit them on one edge.
            @(negedge clk);
            k = {$random(seed)} % (DEPTH - in_count + 1);
            for (i = 0; i < k; i = i + 1) begin
                #2 in_write = 1; in_slot = i; in_wdata = $random(seed);
                in_ref[in_tail + i] = in_wdata;
                @(negedge clk);
                in_write = 0;
            end
            #2 in_commit = k;
            in_tail = in_tail + k;
            in_words = in_words + k;
            @(negedge clk);
            #2 in_commit = 0;
            // Host READN: peek k words while the reply is sent, then free them on one edge.
            k = {$random(seed)} % (eg_count + 1);
            for (i = 0; i < k; i = i + 1) begin
                #2 eg_peek = i;
                #1;
                if (eg_rdata !== eg_ref[eg_head + i]) begin
                    errors = errors + 1;
                    if (errors < 5) $display("egress peek %0d: %h expected %h", i, eg_rdata, eg_ref[eg_head + i]);
                end
                @(negedge clk);
            end
            #2 eg_free = k;
            eg_head = eg_head + k;
            eg_words = eg_words + k;
            @(negedge clk);
            #2 eg_free = 0;
        end
        // Let the last core operations reach the queues before comparing counts.
        core_on = 0;
        repeat (3) @(negedge clk);
        if (in_count !== in_tail - in_head || eg_count !== eg_tail - eg_head) begin
            errors = errors + 1;
            $display("final counts %0d %0d expected %0d %0d", in_count, eg_count, in_tail - in_head, eg_tail - eg_head);
        end
        $display("fifo_multi_probe_tb DEPTH=%0d: %0d ingress words, %0d egress words, %0d errors",
                 DEPTH, in_words, eg_words, errors);
        $finish;
    end
endmodule
