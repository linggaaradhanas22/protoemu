// SPDX-License-Identifier: Apache-2.0
// BLK-CORE: Shared sequential instruction issue for two protocol contexts.

`default_nettype none

module issue_core (
    input wire clk, rst_n,
    input wire [23:0] cycle,
    input wire start, flush,
    input wire [1:0] enable_ctx,
    input wire [6:0] entry0, entry1,
    output wire running, done,
    output reg faulted,
    output wire fault_safe,
    output reg fault_ctx,
    output reg [7:0] fault_pc,
    output reg [2:0] fault_cause,

    output wire fetch_req_valid,
    output wire [6:0] fetch_pc,
    input wire fetch_rsp_valid, fetch_rsp_fault,
    input wire [23:0] fetch_instruction,

    output wire drive_valid, drive_ctx,
    output wire [23:0] drive_deadline,
    output wire [7:0] drive_mask, drive_value, drive_oe,
    input wire drive_credit, drive_ready, drive_reject, drive_empty,

    output wire capture_arm, capture_consume, capture_ctx,
    output wire [2:0] capture_pin,
    output wire [1:0] capture_mode, capture_polarity,
    output wire capture_level, capture_guarded,
    output wire [23:0] capture_target,
    output wire [15:0] capture_timeout,
    input wire capture_arm_reject,
    input wire [1:0] capture_ready,
    input wire capture_bit, capture_expired,
    input wire [23:0] capture_stamp,

    input wire [1:0] ingress_ready, egress_ready,
    input wire [31:0] ingress_words,
    output wire [1:0] ingress_pop, egress_push,
    output wire [15:0] egress_word
);
    localparam [4:0] HALT=0, SET=1, ADD=2, CAP=5, WAIT_TO=6, CALL=7, RET=8,
        LOOP=9, JNZ=10, JUMP=11, FENCE=14, SAVE_NOW=15, ADDOFF=16, WAIT_SAVE=17,
        PAD=18, PAD2=19, SHIFT_PIN=20, SHIFT_PAIR=21, DRIVEV=22, HOST_GET=23,
        HOST_PUT=24, EDGE_SAVE=25, EDGE_DELTA=26, SHR=27, ADDOFF_R=28, XOR=29, ULT=30, MOV=31;
    localparam [2:0] NONE=0, DRIVE=1, CAPTURE=2, GET=3, PUT=4, GUARD=5;
    localparam [2:0] BAD_FETCH=1, BAD_INSN=2, BAD_STACK=3, BAD_TIME=4,
        BAD_DRIVE=5, BAD_CAPTURE=6;

    reg started, fault_pending, rr_next, redirect;
    reg fetch_live, fetch_ctx, fetch_overflow;
    reg [1:0] active, stamp_valid, guard_open;
    // Bit 7 retains the out-of-range fall-through past word 127.
    reg [7:0] pc [0:1], ret0 [0:1], ret1 [0:1];
    reg [1:0] depth [0:1];
    reg [15:0] regs [0:15];
    reg [23:0] saved_stamp [0:1], wait_target [0:1];
    reg [2:0] wait_kind [0:1], wait_rd [0:1];
    reg [4:0] wait_op [0:1];
    reg [1:0] wait_mode [0:1];
    reg [7:0] wait_mask [0:1], wait_value [0:1], wait_oe [0:1];
    reg [15:0] wait_word [0:1];

    function future;
        input [23:0] target, now;
        begin
            future = target != now && ((target[23] ^ now[23]) == (target[22:0] < now[22:0]));
        end
    endfunction

    function malformed;
        input [23:0] w;
        begin
            case (w[4:0])
                HALT, RET, SAVE_NOW: malformed = |w[23:5];
                ADD: malformed = w[23];
                CALL, JUMP, SHR: malformed = |w[23:12];
                LOOP, JNZ: malformed = |w[23:15];
                FENCE: malformed = |w[23:14];
                ADDOFF: malformed = |w[23:20];
                CAP: malformed = |w[23:22] || w[12:11] == 2'd3;
                WAIT_SAVE: malformed = |w[23:18];
                WAIT_TO, SHIFT_PIN: malformed = |w[23:21];
                PAD: malformed = |w[23:19];
                PAD2: malformed = w[7:5] == w[12:10];
                SHIFT_PAIR: malformed = w[10:8] == w[13:11];
                HOST_GET, HOST_PUT, ADDOFF_R: malformed = |w[23:8];
                EDGE_SAVE: malformed = |w[23:10] || w[9:8] == 2'd3;
                EDGE_DELTA: malformed = |w[23:13] || w[9:8] == 2'd3 || w[12:10] < 3'd1 || w[12:10] > 3'd4;
                XOR, MOV: malformed = |w[23:11];
                SET, ULT, DRIVEV: malformed = 1'b0;
                default: malformed = 1'b1;
            endcase
        end
    endfunction

    wire launch = start && !started && !faulted && !flush;
    wire go = rst_n && started && !flush && !fault_pending && !faulted;
    assign done = go && active == 0 && drive_empty;
    assign running = go && !done;
    assign fault_safe = rst_n && fault_pending;

    wire [1:0] runnable, pending_future, guard_hit;
    genvar k;
    generate for (k = 0; k < 2; k = k + 1) begin : eligibility
        assign pending_future[k] = future(wait_target[k], cycle);
        assign guard_hit[k] = wait_target[k] == cycle;
        assign runnable[k] = active[k] && (wait_kind[k] == NONE ||
            (wait_kind[k] == DRIVE && (drive_credit || !pending_future[k])) ||
            (wait_kind[k] == CAPTURE && capture_ready[k]) ||
            (wait_kind[k] == GET && ingress_ready[k]) || (wait_kind[k] == PUT && egress_ready[k]) ||
            (wait_kind[k] == GUARD && (guard_open[k] || guard_hit[k])));
    end endgenerate

    wire boundary = go && !fetch_live && !redirect && (|runnable);
    wire chosen = runnable[1] && (!runnable[0] || rr_next);
    wire ctx = fetch_live ? fetch_ctx : chosen;
    wire fetch = boundary && wait_kind[chosen] == NONE;
    wire retry = boundary && wait_kind[chosen] != NONE;
    wire execute = go && fetch_live && (fetch_rsp_valid || fetch_overflow);
    assign fetch_req_valid = fetch && !pc[chosen][7];
    assign fetch_pc = pc[chosen][6:0];

    wire [23:0] insn = fetch_instruction;
    wire [4:0] op = insn[4:0];
    wire [2:0] src = op == WAIT_TO ? insn[20:18] : insn[7:5];
    wire [2:0] src_b = retry ? wait_rd[ctx] : insn[10:8];
    wire [15:0] x = regs[{ctx, src}], y = regs[{ctx, src_b}];
    wire [15:0] in_word = ctx ? ingress_words[31:16] : ingress_words[15:0];
    wire [22:0] offset = {regs[{ctx, 3'd6}][6:0], regs[{ctx, 3'd0}]};
    wire [8:0] imm = op == DRIVEV ? {1'b0, insn[23:16]} :
        (op == PAD2 || op == SHIFT_PAIR) ? insn[23:15] : op == SHIFT_PIN ? insn[19:11] :
        op == CAP ? insn[21:13] : (op == WAIT_SAVE || op == WAIT_TO) ? insn[17:9] :
        op == FENCE ? insn[13:5] : insn[18:10];
    wire [23:0] relative = {1'b0, offset} + {15'b0, imm};
    wire [23:0] target = saved_stamp[ctx] + relative;
    wire [23:0] expiry = target + {2'b0, x, 6'b0};
    wire [23:0] interval = capture_stamp - saved_stamp[ctx];
    wire [23:0] bumped = {1'b0, offset} + (op == ADDOFF_R ? {8'b0, x} : {{9{insn[19]}}, insn[19:5]});
    wire target_future = future(target, cycle);

    wire shift = op == SHIFT_PIN || op == SHIFT_PAIR;
    wire shift_lsb = op == SHIFT_PIN && insn[20];
    wire [15:0] shifted = shift_lsb ? {1'b0, x[15:1]} : {x[14:0], 1'b0};
    wire [7:0] pin_a = 8'b1 << (shift ? insn[10:8] : insn[7:5]);
    wire [7:0] pin_b = (op == PAD2 || op == SHIFT_PAIR ? 8'b1 : 8'b0) <<
        (op == SHIFT_PAIR ? insn[13:11] : insn[12:10]);
    wire [7:0] new_mask = op == DRIVEV ? x[7:0] : pin_a | pin_b;
    wire [7:0] new_value = op == DRIVEV ? x[15:8] :
        ((shift ? (shift_lsb ? x[0] : x[15]) : insn[8]) ? pin_a : 8'b0) |
        ((op == SHIFT_PAIR ? insn[14] : insn[13]) ? pin_b : 8'b0);
    wire [7:0] new_oe = op == DRIVEV ? insn[15:8] :
        ((shift || insn[9]) ? pin_a : 8'b0) | ((op == SHIFT_PAIR || insn[14]) ? pin_b : 8'b0);

    wire drives = op == PAD || op == PAD2 || shift || op == DRIVEV;
    wire captures = op == CAP || op == WAIT_SAVE || op == WAIT_TO || op == EDGE_SAVE || op == EDGE_DELTA;
    wire [2:0] decode_fault = (fetch_overflow || fetch_rsp_fault) ? BAD_FETCH :
        malformed(insn) ? BAD_INSN :
        ((op == CALL && depth[ctx] == 2) || (op == RET && depth[ctx] == 0)) ? BAD_STACK :
        (((drives || op == CAP || op == WAIT_TO || op == FENCE || op == EDGE_DELTA) && !stamp_valid[ctx]) ||
         ((drives || op == CAP || op == WAIT_TO || op == WAIT_SAVE || op == FENCE) && relative[23]) ||
         (op == WAIT_SAVE && !stamp_valid[ctx] && relative != 0) ||
         ((drives || op == CAP) && !target_future) ||
         (op == WAIT_TO && x != 0 && !future(expiry, cycle)) ||
         ((op == ADDOFF || op == ADDOFF_R) && bumped[23])) ? BAD_TIME :
        (op == DRIVEV && new_mask == 0) ? BAD_DRIVE : 3'd0;

    assign drive_valid = (execute && decode_fault == 0 && drives) ||
                         (retry && wait_kind[ctx] == DRIVE && pending_future[ctx]);
    assign drive_ctx = ctx;
    assign drive_deadline = retry ? wait_target[ctx] : target;
    assign drive_mask = retry ? wait_mask[ctx] : new_mask;
    assign drive_value = retry ? wait_value[ctx] : new_value;
    assign drive_oe = retry ? wait_oe[ctx] : new_oe;

    assign capture_arm = execute && decode_fault == 0 && captures;
    assign capture_consume = retry && wait_kind[ctx] == CAPTURE && retire;
    assign capture_ctx = ctx;
    assign capture_pin = insn[7:5];
    assign capture_mode = op == CAP ? 2'd0 : (op == WAIT_SAVE || op == WAIT_TO) ? 2'd1 : 2'd2;
    assign capture_polarity = insn[9:8];
    assign capture_level = insn[8];
    assign capture_guarded = (op == WAIT_SAVE || op == WAIT_TO) && stamp_valid[ctx];
    assign capture_target = target;
    assign capture_timeout = op == WAIT_TO ? x : 16'd0;

    wire get_word = retire && (retry ? wait_kind[ctx] == GET : op == HOST_GET);
    wire put_word = retire && (retry ? wait_kind[ctx] == PUT : op == HOST_PUT);
    assign ingress_pop = {get_word && ctx, get_word && !ctx};
    assign egress_push = {put_word && ctx, put_word && !ctx};
    assign egress_word = retry ? wait_word[ctx] : x;

    reg retire, halt, branch, stack_push, stack_pop, wr_reg, wr_offset, wr_stamp, wr_delta;
    reg [7:0] branch_pc;
    reg [2:0] rd, stall_kind, cause;
    reg [15:0] word_out;
    reg [22:0] offset_out;
    reg [23:0] stamp_out;

    always @* begin
        retire=0; halt=0; branch=0; stack_push=0; stack_pop=0;
        wr_reg=0; wr_offset=0; wr_stamp=0; wr_delta=0;
        branch_pc={1'b0, insn[11:5]};
        rd=insn[7:5]; stall_kind=NONE; cause=0;
        word_out=0; offset_out=0; stamp_out=capture_stamp;
        if (retry) begin
            rd = wait_rd[ctx];
            case (wait_kind[ctx])
                DRIVE: begin
                    if (!pending_future[ctx] || drive_reject) cause = BAD_DRIVE;
                    else retire = drive_ready;
                    wr_reg = wait_op[ctx] == SHIFT_PIN || wait_op[ctx] == SHIFT_PAIR;
                    word_out = wait_word[ctx];
                end
                CAPTURE: begin
                    retire = 1;
                    if (wait_op[ctx] == CAP) begin
                        wr_reg = 1;
                        case (wait_mode[ctx])
                            2'd1: word_out = {y[14:0], capture_bit};
                            2'd2: word_out = {1'b0, y[15:1]} | {8'b0, capture_bit, 7'b0};
                            default: word_out = {15'b0, capture_bit};
                        endcase
                    end else if (wait_op[ctx] == WAIT_TO && capture_expired) begin
                        wr_reg = 1;
                    end else if (wait_op[ctx] == EDGE_DELTA && (interval == 0 || interval[23])) begin
                        retire = 0;
                        cause = BAD_TIME;
                    end else begin
                        wr_stamp = 1;
                        wr_offset = 1;
                        wr_delta = wait_op[ctx] == EDGE_DELTA;
                        wr_reg = wr_delta;
                        word_out = interval[15:0];
                    end
                end
                GET: begin retire=1; wr_reg=1; word_out=in_word; end
                PUT, GUARD: retire = 1;
                default: begin end
            endcase
        end else if (execute) begin
            cause = decode_fault;
            if (cause == 0) begin
                retire = 1;
                if (drives) begin
                    retire = drive_ready && !drive_reject;
                    if (drive_reject) cause = BAD_DRIVE;
                    else if (!drive_ready) stall_kind = DRIVE;
                    wr_reg = shift;
                    word_out = shifted;
                end else if (captures) begin
                    retire = 0;
                    if (capture_arm_reject) cause = BAD_CAPTURE;
                    else stall_kind = CAPTURE;
                end else case (op)
                    HALT: halt = 1;
                    SET: begin wr_reg=1; word_out=insn[23:8]; end
                    ADD: begin wr_reg=1; word_out=x + {insn[22], insn[22:8]}; end
                    SHR: begin wr_reg=1; word_out=x >> insn[11:8]; end
                    XOR: begin wr_reg=1; word_out=x ^ y; end
                    MOV: begin wr_reg=1; word_out=y; end
                    ULT: begin wr_reg=1; word_out={15'b0, x < insn[23:8]}; end
                    ADDOFF, ADDOFF_R: begin wr_offset=1; offset_out=bumped[22:0]; end
                    SAVE_NOW: begin wr_stamp=1; stamp_out=cycle; wr_offset=1; end
                    JUMP: branch = 1;
                    CALL: begin branch=1; stack_push=1; end
                    RET: begin branch=1; stack_pop=1; branch_pc=depth[ctx] == 2 ? ret1[ctx] : ret0[ctx]; end
                    LOOP: begin
                        wr_reg=1; word_out=x - 16'd1; branch=word_out != 0;
                        branch_pc={1'b0, insn[14:8]};
                    end
                    JNZ: begin branch=x != 0; branch_pc={1'b0, insn[14:8]}; end
                    FENCE: if (target_future) begin retire=0; stall_kind=GUARD; end
                    HOST_GET: begin
                        retire=ingress_ready[ctx]; wr_reg=1; word_out=in_word;
                        if (!retire) stall_kind=GET;
                    end
                    HOST_PUT: if (!egress_ready[ctx]) begin retire=0; stall_kind=PUT; end
                    default: begin end
                endcase
            end
        end
    end

    wire clear = !rst_n || flush || fault_pending || launch;
    genvar r;
    generate for (r = 0; r < 16; r = r + 1) begin : reg_slot
        localparam [0:0] BANK = r[3];
        localparam [2:0] NUM = r[2:0];
        always @(posedge clk) begin
            if (clear) regs[r] <= 0;
            else if (retire && ctx == BANK) begin
                if (wr_reg && rd == NUM) regs[r] <= word_out;
                if (wr_offset && NUM == 0) regs[r] <= offset_out[15:0];
                if (wr_offset && NUM == 6) regs[r] <= {9'b0, offset_out[22:16]};
                // The high interval word can only reach R2 through R5.
                if (r % 8 >= 2 && r % 8 <= 5 && wr_delta && rd + 3'd1 == NUM)
                    regs[r] <= {9'b0, interval[22:16]};
            end
        end
    end endgenerate

    integer i;
    always @(posedge clk) begin
        if (clear) begin
            started <= rst_n && launch;
            active <= rst_n && launch ? enable_ctx : 2'd0;
            fault_pending <= 0;
            faulted <= rst_n && fault_pending;
            if (!rst_n || !fault_pending) begin
                fault_ctx <= 0; fault_pc <= 0; fault_cause <= 0;
            end
            fetch_live <= 0; fetch_ctx <= 0; fetch_overflow <= 0;
            redirect <= 0; rr_next <= 0; stamp_valid <= 0; guard_open <= 0;
            pc[0] <= rst_n && launch ? {1'b0, entry0} : 8'd0;
            pc[1] <= rst_n && launch ? {1'b0, entry1} : 8'd0;
            for (i = 0; i < 2; i = i + 1) begin
                depth[i] <= 0; ret0[i] <= 0; ret1[i] <= 0;
                saved_stamp[i] <= 0; wait_kind[i] <= NONE; wait_rd[i] <= 0;
                wait_op[i] <= 0; wait_mode[i] <= 0; wait_target[i] <= 0;
                wait_mask[i] <= 0; wait_value[i] <= 0; wait_oe[i] <= 0; wait_word[i] <= 0;
            end
        end else begin
            redirect <= retire && branch;
            if (boundary) rr_next <= !chosen;
            if (execute) fetch_live <= 0;
            if (fetch) begin
                fetch_live <= 1;
                fetch_ctx <= chosen;
                fetch_overflow <= pc[chosen][7];
            end
            for (i = 0; i < 2; i = i + 1)
                if (wait_kind[i] == GUARD && guard_hit[i]) guard_open[i] <= 1;
            if (cause != 0) begin
                fault_pending <= 1;
                fault_ctx <= ctx;
                fault_pc <= pc[ctx];
                fault_cause <= cause;
            end else if (retire) begin
                pc[ctx] <= branch ? branch_pc : pc[ctx] + 8'd1;
                wait_kind[ctx] <= NONE;
                guard_open[ctx] <= 0;
                if (halt) active[ctx] <= 0;
                if (stack_push) begin
                    depth[ctx] <= depth[ctx] + 2'd1;
                    if (depth[ctx] == 0) ret0[ctx] <= pc[ctx] + 8'd1;
                    else ret1[ctx] <= pc[ctx] + 8'd1;
                end else if (stack_pop) depth[ctx] <= depth[ctx] - 2'd1;
                if (wr_stamp) begin
                    saved_stamp[ctx] <= stamp_out;
                    stamp_valid[ctx] <= 1;
                end
            end else if (execute && stall_kind != NONE) begin
                wait_kind[ctx] <= stall_kind;
                wait_op[ctx] <= op;
                wait_rd[ctx] <= op == CAP ? insn[10:8] : op == WAIT_TO ? insn[20:18] :
                                op == EDGE_DELTA ? insn[12:10] : insn[7:5];
                wait_mode[ctx] <= insn[12:11];
                wait_target[ctx] <= target;
                wait_mask[ctx] <= new_mask;
                wait_value[ctx] <= new_value;
                wait_oe[ctx] <= new_oe;
                wait_word[ctx] <= drives ? shifted : x;
                guard_open[ctx] <= 0;
            end
        end
    end
endmodule

`default_nettype wire
