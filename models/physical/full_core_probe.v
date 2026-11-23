// EVAL-018: exploratory BLK-CORE with program storage, timer and timed I/O.
module full_core_probe #(parameter OPT = 0) (
    input clk, rst_n, start, stop, image_valid, load_word,
    input [6:0] load_addr, entry0, entry1,
    input [23:0] load_data,
    input [7:0] image_count, owner0, owner1, open_drain, raw_pins,
    input [1:0] enable_ctx, ingress_ready, egress_ready,
    input [31:0] ingress_words,
    output [1:0] ingress_pop, egress_push,
    output [15:0] egress_word,
    output [7:0] pad_value, pad_oe,
    output done, faulted,
    output reg fault_ctx,
    output reg [7:0] fault_pc,
    output reg [2:0] fault_cause
);
    localparam HALT=0, SET=1, ADD=2, CAP=5, WAIT_TO=6, CALL=7, RET=8, LOOP=9, JNZ=10, JUMP=11,
               FENCE=14, SAVE_NOW=15, ADDOFF=16, WAIT_SAVE=17, PAD=18, PAD2=19, SHIFT_PIN=20,
               SHIFT_PAIR=21, DRIVEV=22, HOST_GET=23, HOST_PUT=24, EDGE_SAVE=25, EDGE_DELTA=26,
               SHR=27, ADDOFF_R=28, XOR=29, ULT=30, MOV=31;
    localparam P_NONE=0, P_DRIVE=1, P_CAP=2, P_GET=3, P_PUT=4, P_FENCE=5;

    function in_future_half;
        input [23:0] target, now;
        begin
            in_future_half = (target != now) &&
                ((target[23] ^ now[23]) == (target[22:0] < now[22:0]));
        end
    endfunction

    function [23:0] sum3;
        input [23:0] a, b, c;
        begin
            sum3 = (a ^ b ^ c) + (((a & b) | (a & c) | (b & c)) << 1);
        end
    endfunction

    reg [23:0] cycle;
    reg [7:0] pin_sync0, pin_sync1;
    reg started, fault_pending, fault_latched, rr_next, redirect;
    reg fetch_live, fetch_ctx, fetch_fault;
    reg retry_live, retry_ctx, timing_live;
    reg [23:0] timed_relative, timed_deadline, timed_expiry;
    reg [1:0] active, stamp_valid, fence_open;
    reg [7:0] pc [0:1];
    reg [1:0] depth [0:1];
    reg [7:0] ret0 [0:1], ret1 [0:1];
    reg [23:0] saved_stamp [0:1];
    reg [2:0] wait_kind [0:1], wait_rd [0:1];
    reg [4:0] wait_op [0:1];
    reg [1:0] wait_mode [0:1];
    reg [23:0] wait_at [0:1];
    reg [7:0] wait_mask [0:1], wait_value [0:1], wait_oe [0:1];
    reg [15:0] wait_word [0:1];

    wire drive_credit, drive_empty, drive_accept, drive_reject;
    wire [1:0] cap_ready;
    wire cap_occupied, cap_bit, cap_expired;
    wire [23:0] cap_stamp;
    wire flush = stop || fault_pending || start;
    wire go = rst_n && started && image_valid && !flush && !fault_latched;
    wire [1:0] runnable;
    wire [1:0] get_ready, put_ready;
    wire [1:0] fence_hit;
    wire [1:0] saved_future;
    wire [1:0] saved_last;
    genvar i;
    generate
        for (i = 0; i < 2; i = i + 1) begin : eligibility
            wire [23:0] age = wait_at[i] - cycle;
            assign saved_future[i] = OPT ? in_future_half(wait_at[i], cycle) : (|age && !age[23]);
            assign saved_last[i] = wait_at[i] == cycle + 24'd1;
            assign fence_hit[i] = cycle == wait_at[i];
            assign get_ready[i] = wait_kind[i] == P_GET && ingress_ready[i];
            assign put_ready[i] = wait_kind[i] == P_PUT && egress_ready[i];
            assign runnable[i] = active[i] &&
                (wait_kind[i] == P_NONE ||
                 (wait_kind[i] == P_DRIVE && (drive_credit || !saved_future[i])) ||
                 (wait_kind[i] == P_CAP && cap_ready[i]) ||
                 get_ready[i] || put_ready[i] ||
                 (wait_kind[i] == P_FENCE && (fence_open[i] || fence_hit[i])));
        end
    endgenerate

    wire select_ctx = runnable[1] && (!runnable[0] || rr_next);
    wire same_cycle = OPT < 3 || OPT == 10 || OPT == 11;
    wire ctx = fetch_live ? fetch_ctx : ((!same_cycle && !bypass_drive) ? retry_ctx : select_ctx);
    wire free_issue = go && !fetch_live && !(!same_cycle && retry_live) && !redirect;
    wire boundary = free_issue && |runnable;
    wire fetch = boundary && wait_kind[select_ctx] == P_NONE;
    wire select_retry = boundary && wait_kind[select_ctx] != P_NONE;
    wire expired_on_select = (OPT == 7 || OPT == 8) && select_retry && wait_kind[select_ctx] == P_DRIVE &&
                             !saved_future[select_ctx];
    wire bypass_drive = select_retry && wait_kind[select_ctx] == P_DRIVE &&
                        (OPT == 9 || (OPT == 8 && saved_last[select_ctx]));
    wire retry = same_cycle ? select_retry : ((go && retry_live) || bypass_drive);
    wire prepare_timing = OPT == 4 && go && fetch_live && !timing_live;
    wire execute = go && fetch_live && (OPT != 4 || timing_live);
    wire [7:0] cur_pc = pc[ctx];
    wire [7:0] fetch_pc = pc[select_ctx];
    wire [23:0] insn;
    wire [23:0] fetched_word;
    reg [31:0] early_op;
    reg early_malformed;
    wire fetch_ok = fetch && fetch_pc < image_count;
    generate if (OPT == 6) begin : fast_fetch
        reg [23:0] mem [0:127];
        reg [23:0] stored_word;
        assign fetched_word = mem[fetch_pc[6:0]];
        assign insn = stored_word;
        always @(posedge clk) begin
            if (load_word && rst_n && !started && !start) mem[load_addr] <= load_data;
            if (fetch_ok) stored_word <= fetched_word;
        end
    end else begin : legacy_fetch
        assign fetched_word = 24'b0;
        probe_store #(.AW(7)) program_store (
        .clk(clk), .wr(load_word && rst_n && !started && !start), .rd(fetch && fetch_pc < image_count),
        .waddr(load_addr), .raddr(fetch_pc[6:0]), .wdata(load_data), .word(insn)
        );
    end endgenerate

    wire [4:0] op = insn[4:0];
    wire [2:0] ra = (!OPT && retry) ? wait_rd[ctx] : op == WAIT_TO ? insn[20:18] : insn[7:5];
    wire [2:0] rb = retry ? wait_rd[ctx] : insn[10:8];
    wire [15:0] ax, bx;
    wire [22:0] offset;
    reg retire, take_halt, branch, push, pop, write_a, write_off, write_delta, write_stamp;
    reg [7:0] branch_pc;
    reg [2:0] addr_a;
    reg [15:0] word_a;
    reg [22:0] off_data;
    reg [23:0] stamp_data;
    reg [2:0] next_wait;
    reg [2:0] cause;
    wire [23:0] interval = cap_stamp - saved_stamp[ctx];
    wire [31:0] op_select = OPT == 6 ? early_op : (32'b1 << op);
    wire [15:0] input_word = ctx ? ingress_words[31:16] : ingress_words[15:0];
    wire [15:0] fresh_alu = ({16{op_select[SET]}} & insn[23:8]) |
                            ({16{op_select[ADD]}} & (ax + {insn[22], insn[22:8]})) |
                            ({16{op_select[SHR]}} & (ax >> insn[11:8])) |
                            ({16{op_select[XOR]}} & (ax ^ bx)) |
                            ({16{op_select[MOV]}} & bx) |
                            ({16{op_select[ULT]}} & {15'b0, ax < insn[23:8]}) |
                            ({16{op_select[LOOP]}} & (ax - 16'd1));
    wire static_ok = execute && !fetch_fault && !malformed;
    wire alu_write = static_ok && (op_select[SET] || op_select[ADD] || op_select[SHR] || op_select[XOR] ||
                                    op_select[MOV] || op_select[ULT] || op_select[LOOP]);
    wire [1:0] fresh_grant = {2{static_ok}} & {fetch_ctx, !fetch_ctx};
    wire [1:0] fresh_get_by_ctx = {2{op_select[HOST_GET]}} & fresh_grant & ingress_ready;
    wire [1:0] fresh_put_by_ctx = {2{op_select[HOST_PUT]}} & fresh_grant & egress_ready;
    wire fresh_get = OPT == 11 ? |fresh_get_by_ctx : (static_ok && op_select[HOST_GET] && ingress_ready[ctx]);
    wire fresh_put = static_ok && op_select[HOST_PUT] && egress_ready[ctx];
    wire fresh_shift = drive_accept && execute && (op_select[SHIFT_PIN] || op_select[SHIFT_PAIR]);
    wire fast_we = alu_write || fresh_get || fresh_shift || (retry && retire && write_a);
    wire [15:0] fast_data = fresh_alu & {16{alu_write}} | input_word & {16{fresh_get}} |
                            shifted_word & {16{fresh_shift}} | word_a & {16{retry}};
    regfile_probe #(.VARIANT(1)) rf (
        .clk(clk), .rst_n(rst_n), .clear(flush), .ctx_a(ctx), .we_a(OPT >= 5 ? fast_we : (retire && write_a)),
        .addr_a(addr_a), .data_a(OPT >= 5 ? fast_data : word_a), .off_we(retire && write_off), .off_data(off_data),
        .delta_we(retire && write_delta), .delta_rd(addr_a[1:0] - 2'd1), .delta_hi(interval[22:16]),
        .wb_go(1'b0), .we_b(1'b0), .addr_b(3'b0), .data_b(16'b0),
        .ctx_r(ctx), .raddr_x(ra), .raddr_y(rb), .rx(ax), .ry(bx), .offset(offset), .wb_pending()
    );

    wire drives = op == PAD || op == PAD2 || op == SHIFT_PIN || op == SHIFT_PAIR || op == DRIVEV;
    wire samples = op == CAP || op == WAIT_SAVE || op == WAIT_TO || op == EDGE_SAVE || op == EDGE_DELTA;
    wire [8:0] immediate = op == DRIVEV ? {1'b0, insn[23:16]} :
                           (op == PAD2 || op == SHIFT_PAIR) ? insn[23:15] :
                           op == SHIFT_PIN ? insn[19:11] : op == CAP ? insn[21:13] :
                           (op == WAIT_SAVE || op == WAIT_TO) ? insn[17:9] :
                           op == FENCE ? insn[13:5] : insn[18:10];
    wire [23:0] relative_calc = {1'b0, offset} + {15'b0, immediate};
    wire [23:0] time_base = saved_stamp[OPT ? fetch_ctx : ctx];
    wire time_valid = stamp_valid[OPT ? fetch_ctx : ctx];
    wire [23:0] deadline_calc = OPT >= 2 ? sum3(time_base, {1'b0, offset}, {15'b0, immediate}) : time_base + relative_calc;
    wire [23:0] expiry_calc = OPT >= 2 ? sum3(time_base, relative_calc, {2'b0, ax, 6'b0}) : deadline_calc + {2'b0, ax, 6'b0};
    wire [23:0] relative = OPT == 4 ? timed_relative : relative_calc;
    wire [23:0] deadline = OPT == 4 ? timed_deadline : deadline_calc;
    wire [23:0] deadline_delta = deadline - cycle;
    wire deadline_future = OPT ? in_future_half(deadline, cycle) : (!deadline_delta[23] && |deadline_delta);
    wire [23:0] expiry = OPT == 4 ? timed_expiry : expiry_calc;
    wire [23:0] expiry_delta = expiry - cycle;
    wire expiry_future = OPT ? in_future_half(expiry, cycle) : (!expiry_delta[23] && |expiry_delta);
    wire [23:0] bumped_offset = {1'b0, offset} +
        (op == ADDOFF_R ? {8'b0, ax} : {{9{insn[19]}}, insn[19:5]});

    wire [7:0] gpio_a = 8'b1 << ((op == SHIFT_PIN || op == SHIFT_PAIR) ? insn[10:8] : insn[7:5]);
    wire [7:0] gpio_b = (op == PAD2 || op == SHIFT_PAIR ? 8'b1 : 8'b0) <<
                        (op == SHIFT_PAIR ? insn[13:11] : insn[12:10]);
    wire lsb = op == SHIFT_PIN && insn[20];
    wire shifted_bit = lsb ? ax[0] : ax[15];
    wire [15:0] shifted_word = lsb ? {1'b0, ax[15:1]} : {ax[14:0], 1'b0};
    wire [7:0] new_mask = op == DRIVEV ? ax[7:0] : gpio_a | gpio_b;
    wire [7:0] new_value = op == DRIVEV ? ax[15:8] :
        ((op == SHIFT_PIN || op == SHIFT_PAIR ? shifted_bit : insn[8]) ? gpio_a : 8'b0) |
        ((op == SHIFT_PAIR ? insn[14] : insn[13]) ? gpio_b : 8'b0);
    wire [7:0] new_oe = op == DRIVEV ? insn[15:8] :
        ((op == SHIFT_PIN || op == SHIFT_PAIR || insn[9]) ? gpio_a : 8'b0) |
        ((op == SHIFT_PAIR || insn[14]) ? gpio_b : 8'b0);

    function invalid_word;
        input [23:0] w;
        begin
            case (w[4:0])
                HALT, RET, SAVE_NOW: invalid_word = |w[23:5];
                ADD: invalid_word = w[23];
                CALL, JUMP, SHR: invalid_word = |w[23:12];
                LOOP, JNZ: invalid_word = |w[23:15];
                FENCE: invalid_word = |w[23:14];
                ADDOFF: invalid_word = |w[23:20];
                CAP: invalid_word = |w[23:22] || w[12:11] == 3;
                WAIT_SAVE: invalid_word = |w[23:18];
                WAIT_TO: invalid_word = |w[23:21];
                PAD: invalid_word = |w[23:19];
                PAD2: invalid_word = w[7:5] == w[12:10];
                SHIFT_PAIR: invalid_word = w[10:8] == w[13:11];
                SHIFT_PIN: invalid_word = |w[23:21];
                HOST_GET, HOST_PUT, ADDOFF_R: invalid_word = |w[23:8];
                EDGE_SAVE: invalid_word = |w[23:10] || w[9:8] == 3;
                EDGE_DELTA: invalid_word = |w[23:13] || w[9:8] == 3 || w[12:10] < 1 || w[12:10] > 4;
                XOR, MOV: invalid_word = |w[23:11];
                SET, ULT, DRIVEV: invalid_word = 0;
                default: invalid_word = 1;
            endcase
        end
    endfunction
    wire malformed = OPT == 6 ? early_malformed : invalid_word(insn);

    wire [2:0] decode_fault = fetch_fault ? 3'd1 : malformed ? 3'd2 :
        ((op == CALL && depth[ctx] == 2) || (op == RET && depth[ctx] == 0)) ? 3'd3 :
        (((drives || op == CAP || op == WAIT_TO || op == FENCE || op == EDGE_DELTA) && !time_valid) ||
         ((drives || op == CAP || op == WAIT_TO || op == WAIT_SAVE || op == FENCE) && relative[23]) ||
         (op == WAIT_SAVE && !time_valid && (|relative)) ||
         (op == CAP && !deadline_future) || (op == WAIT_TO && |ax && !expiry_future) ||
         ((op == ADDOFF || op == ADDOFF_R) && bumped_offset[23])) ? 3'd4 : 3'd0;

    wire drive_valid = (execute && !decode_fault && drives) || (retry && wait_kind[ctx] == P_DRIVE);
    wire route_ctx = !same_cycle && !bypass_drive ? retry_ctx : select_ctx;
    wire [2:0] route = {retry && route_ctx, retry && !route_ctx, execute};
    wire [23:0] drive_at = OPT ? (({24{route[0]}} & deadline) | ({24{route[1]}} & wait_at[0]) |
                                 ({24{route[2]}} & wait_at[1])) : (retry ? wait_at[ctx] : deadline);
    wire [7:0] drive_mask = OPT ? (({8{route[0]}} & new_mask) | ({8{route[1]}} & wait_mask[0]) |
                                  ({8{route[2]}} & wait_mask[1])) : (retry ? wait_mask[ctx] : new_mask);
    full_core_drive #(.SPLIT(OPT != 0)) drive (
        .clk(clk), .rst_n(rst_n), .flush(flush), .cycle(cycle),
        .deadline(drive_at), .mask(drive_mask),
        .values(retry ? wait_value[ctx] : new_value), .enables(retry ? wait_oe[ctx] : new_oe),
        .owner((OPT ? fetch_ctx : ctx) ? owner1 : owner0), .open_drain(open_drain), .valid(drive_valid),
        .route(route), .future({saved_future, deadline_future}), .fresh_at(deadline),
        .saved_at0(wait_at[0]), .saved_at1(wait_at[1]), .fresh_mask(new_mask),
        .saved_mask0(wait_mask[0]), .saved_mask1(wait_mask[1]), .owner0(owner0), .owner1(owner1),
        .credit(drive_credit), .empty(drive_empty), .accept(drive_accept), .reject(drive_reject),
        .pad_value(pad_value), .pad_oe(pad_oe)
    );
    wire cap_arm = execute && !decode_fault && samples && !cap_occupied;
    full_core_capture capture (
        .clk(clk), .rst_n(rst_n), .flush(flush), .cycle(cycle), .pins(pin_sync1), .ctx(ctx),
        .arm(cap_arm), .consume(retry && retire && wait_kind[ctx] == P_CAP), .target(deadline),
        .pin(insn[7:5]), .mode(op == CAP ? 2'd0 : op == WAIT_SAVE || op == WAIT_TO ? 2'd1 : 2'd2),
        .polarity(insn[9:8]), .level(insn[8]), .guarded((op == WAIT_SAVE && stamp_valid[ctx]) || op == WAIT_TO),
        .timeout(op == WAIT_TO ? ax : 16'b0), .ready(cap_ready), .occupied(cap_occupied),
        .sample(cap_bit), .expired(cap_expired), .stamp(cap_stamp)
    );

    wire get = OPT >= 5 ? fresh_get || (retry && wait_kind[ctx] == P_GET) :
                          retire && ((execute && op == HOST_GET) || (retry && wait_kind[ctx] == P_GET));
    wire put_word = OPT >= 5 ? fresh_put || (retry && wait_kind[ctx] == P_PUT) :
                               retire && ((execute && op == HOST_PUT) || (retry && wait_kind[ctx] == P_PUT));
    // Local payload eligibility already implies runnable for an active context.
    wire [1:0] retry_grant = {2{free_issue}} & active & {select_ctx, !select_ctx};
    assign ingress_pop = OPT == 11 ? (fresh_get_by_ctx | (retry_grant & get_ready)) : {get && ctx, get && !ctx};
    assign egress_push = OPT == 11 ? (fresh_put_by_ctx | (retry_grant & put_ready)) : {put_word && ctx, put_word && !ctx};
    assign egress_word = retry ? wait_word[ctx] : ax;
    assign done = go && active == 0 && drive_empty;
    assign faulted = fault_latched;

    always @* begin
        retire = 0;
        take_halt = 0;
        branch = 0;
        push = 0;
        pop = 0;
        branch_pc = {1'b0, insn[11:5]};
        write_a = 0;
        write_off = 0;
        write_delta = 0;
        write_stamp = 0;
        addr_a = insn[7:5];
        word_a = 0;
        off_data = 0;
        stamp_data = cap_stamp;
        next_wait = P_NONE;
        cause = 0;
        if (retry) begin
            addr_a = wait_rd[ctx];
            case (wait_kind[ctx])
                P_DRIVE: begin
                    retire = drive_accept;
                    cause = drive_reject ? 3'd5 : 3'd0;
                    write_a = wait_op[ctx] == SHIFT_PIN || wait_op[ctx] == SHIFT_PAIR;
                    word_a = wait_word[ctx];
                end
                P_CAP: begin
                    retire = 1;
                    if (wait_op[ctx] == CAP) begin
                        write_a = 1;
                        case (wait_mode[ctx])
                            1: word_a = {bx[14:0], cap_bit};
                            2: word_a = {1'b0, bx[15:1]} | {8'b0, cap_bit, 7'b0};
                            default: word_a = {15'b0, cap_bit};
                        endcase
                    end else if (cap_expired) begin
                        write_a = 1;
                    end else if (wait_op[ctx] == EDGE_DELTA && (interval == 0 || interval[23])) begin
                        retire = 0;
                        cause = 3'd4;
                    end else begin
                        write_stamp = 1;
                        write_off = 1;
                        write_delta = wait_op[ctx] == EDGE_DELTA;
                        write_a = write_delta;
                        word_a = interval[15:0];
                    end
                end
                P_GET: begin retire = 1; write_a = 1; word_a = ctx ? ingress_words[31:16] : ingress_words[15:0]; end
                P_PUT, P_FENCE: retire = 1;
                default: begin end
            endcase
        end else if (execute) begin
            cause = decode_fault;
            if (!cause) begin
                retire = 1;
                if (drives) begin
                    retire = drive_accept;
                    cause = drive_reject ? 3'd5 : 3'd0;
                    if (!drive_accept && !drive_reject) next_wait = P_DRIVE;
                    write_a = op == SHIFT_PIN || op == SHIFT_PAIR;
                    word_a = shifted_word;
                end else if (samples) begin
                    retire = 0;
                    if (cap_occupied) cause = 3'd6;
                    else next_wait = P_CAP;
                end else begin
                    case (op)
                        HALT: take_halt = 1;
                        SET: begin write_a = 1; word_a = insn[23:8]; end
                        ADD: begin write_a = 1; word_a = ax + {insn[22], insn[22:8]}; end
                        SHR: begin write_a = 1; word_a = ax >> insn[11:8]; end
                        XOR: begin write_a = 1; word_a = ax ^ bx; end
                        MOV: begin write_a = 1; word_a = bx; end
                        ULT: begin write_a = 1; word_a = {15'b0, ax < insn[23:8]}; end
                        ADDOFF, ADDOFF_R: begin write_off = 1; off_data = bumped_offset[22:0]; end
                        SAVE_NOW: begin write_stamp = 1; stamp_data = cycle; write_off = 1; end
                        JUMP: branch = 1;
                        CALL: begin branch = 1; push = 1; end
                        RET: begin branch = 1; pop = 1; branch_pc = depth[ctx] == 2 ? ret1[ctx] : ret0[ctx]; end
                        LOOP: begin
                            write_a = 1;
                            word_a = ax - 16'd1;
                            branch = word_a != 0;
                            branch_pc = {1'b0, insn[14:8]};
                        end
                        JNZ: begin branch = ax != 0; branch_pc = {1'b0, insn[14:8]}; end
                        FENCE: if (deadline_future) begin retire = 0; next_wait = P_FENCE; end
                        HOST_GET: begin
                            retire = ingress_ready[ctx];
                            if (!retire) next_wait = P_GET;
                            write_a = 1;
                            word_a = ctx ? ingress_words[31:16] : ingress_words[15:0];
                        end
                        HOST_PUT: if (!egress_ready[ctx]) begin retire = 0; next_wait = P_PUT; end
                        default: begin end
                    endcase
                end
            end
        end
    end

    integer c;
    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            pin_sync0 <= 0;
            pin_sync1 <= 0;
        end else begin
            cycle <= cycle + 1'b1;
            pin_sync0 <= raw_pins;
            pin_sync1 <= pin_sync0;
        end

        if (!rst_n || flush) begin
            started <= rst_n && start && image_valid && !stop && !fault_pending;
            active <= (rst_n && start && image_valid && !stop && !fault_pending) ? enable_ctx : 2'b0;
            fetch_live <= 0;
            fetch_ctx <= 0;
            fetch_fault <= 0;
            retry_live <= 0;
            retry_ctx <= 0;
            timing_live <= 0;
            redirect <= 0;
            rr_next <= 0;
            stamp_valid <= 0;
            fence_open <= 0;
            fault_pending <= 0;
            fault_latched <= rst_n && fault_pending;
            if (!rst_n || !fault_pending) begin
                fault_ctx <= 0;
                fault_pc <= 0;
                fault_cause <= 0;
            end
            pc[0] <= {1'b0, entry0};
            pc[1] <= {1'b0, entry1};
            for (c = 0; c < 2; c = c + 1) begin
                depth[c] <= 0;
                wait_kind[c] <= P_NONE;
            end
        end else begin
            fetch_live <= fetch || prepare_timing;
            timing_live <= prepare_timing;
            retry_live <= select_retry && !expired_on_select && !bypass_drive;
            if (select_retry) retry_ctx <= select_ctx;
            if (prepare_timing) begin
                timed_relative <= relative_calc;
                timed_deadline <= deadline_calc;
                timed_expiry <= expiry_calc;
            end
            redirect <= retire && branch;
            if (fetch) begin
                fetch_ctx <= select_ctx;
                fetch_fault <= fetch_pc >= image_count;
                if (fetch_ok) begin
                    early_op <= 32'b1 << fetched_word[4:0];
                    early_malformed <= invalid_word(fetched_word);
                end
            end
            if (boundary) rr_next <= !select_ctx;
            for (c = 0; c < 2; c = c + 1)
                if (wait_kind[c] == P_FENCE && fence_hit[c]) fence_open[c] <= 1;

            if (expired_on_select) begin
                fault_pending <= 1;
                fault_ctx <= select_ctx;
                fault_pc <= fetch_pc;
                fault_cause <= 3'd5;
            end else if (cause != 0) begin
                fault_pending <= 1;
                fault_ctx <= ctx;
                fault_pc <= cur_pc;
                fault_cause <= cause;
            end else if (retire) begin
                pc[ctx] <= branch ? branch_pc : cur_pc + 1'b1;
                wait_kind[ctx] <= P_NONE;
                if (take_halt) active[ctx] <= 0;
                if (push) begin
                    depth[ctx] <= depth[ctx] + 1'b1;
                    if (depth[ctx] == 0) ret0[ctx] <= cur_pc + 1'b1;
                    else ret1[ctx] <= cur_pc + 1'b1;
                end else if (pop) begin
                    depth[ctx] <= depth[ctx] - 1'b1;
                end
                if (write_stamp) begin
                    saved_stamp[ctx] <= stamp_data;
                    stamp_valid[ctx] <= 1;
                end
            end else if (execute && next_wait != P_NONE) begin
                wait_kind[ctx] <= next_wait;
                wait_op[ctx] <= op;
                wait_rd[ctx] <= op == CAP ? insn[10:8] : op == WAIT_TO ? insn[20:18] :
                                op == EDGE_DELTA ? insn[12:10] : insn[7:5];
                wait_mode[ctx] <= insn[12:11];
                wait_word[ctx] <= drives ? shifted_word : ax;
                wait_at[ctx] <= deadline;
                wait_mask[ctx] <= new_mask;
                wait_value[ctx] <= new_value;
                wait_oe[ctx] <= new_oe;
                fence_open[ctx] <= 0;
            end
        end
    end
endmodule
