// SPDX-License-Identifier: Apache-2.0
// BLK-HOST: SPI frame validation, image control and payload commands.

`default_nettype none

module host_loader (
    input  wire        clk, rst_n, selected,
    input  wire        host_cs_n, host_sck, host_mosi,
    output wire        host_miso,
    output reg         host_ready,
    output reg         prog_write_valid,
    output reg  [6:0]  prog_write_index,
    output reg  [23:0] prog_write_word,
    output wire        load_active,
    output reg         image_valid,
    output wire        running,
    output reg  [7:0]  word_count,
    output reg         start,
    output wire        flush, safe,
    output reg  [1:0]  enable_ctx,
    output reg  [6:0]  entry0, entry1,
    output reg  [7:0]  owner0, owner1, open_drain,
    input  wire        core_done, core_faulted, core_fault_safe, core_fault_ctx,
    input  wire [7:0]  core_fault_pc,
    input  wire [2:0]  core_fault_cause,
    input  wire [1:0]  ingress_pop, egress_push,
    input  wire [15:0] egress_word,
    output wire [1:0]  ingress_ready, egress_ready,
    output wire [31:0] ingress_words
);
    localparam [7:0] BEGIN_IMAGE=1, DATA=2, COMMIT=3, START=4, STOP=5,
                     WRITE=6, READ=7, READN=8, WRITEN=9;
    localparam [7:0] OK=0, COMPLETE=1, BAD=2, STATE=3, FULL=4, EMPTY=5;
    localparam [1:0] HALTED=0, RUNNING=1, DONE=2, FAULTED=3;

    function [15:0] crc_bit;
        input [15:0] crc;
        input bit_in;
        begin
            crc_bit = {crc[14:0], 1'b0} ^ ((crc[15] ^ bit_in) ? 16'h1021 : 16'h0000);
        end
    endfunction

    function [15:0] crc_byte;
        input [15:0] crc;
        input [7:0] byte_in;
        integer b;
        begin
            crc_byte = crc;
            for (b = 7; b >= 0; b = b - 1)
                crc_byte = crc_bit(crc_byte, byte_in[b]);
        end
    endfunction

    reg cs_prev, sck_prev;
    reg rx_live, tx_live, launched, have_config, have_data, stop_pending;
    wire enabled = rst_n && selected;
    wire begin_frame = enabled && cs_prev && !host_cs_n;
    wire close_frame = enabled && !cs_prev && host_cs_n;
    wire rise = !host_cs_n && host_sck && !sck_prev;
    wire fall = !host_cs_n && !host_sck && sck_prev;
    wire [1:0] run_state = (core_faulted || core_fault_safe) && launched ? FAULTED :
                           launched ? (core_done ? DONE : RUNNING) : HALTED;
    assign running = run_state == RUNNING;
    assign load_active = have_config && !image_valid && !launched;
    assign flush = !enabled || stop_pending || core_fault_safe;
    assign safe = flush;

    reg [8:0] rx_index, rx_length;
    reg [2:0] rx_bit;
    reg [6:0] rx_shift;
    reg rx_bad_length, rx_overrun;
    reg [7:0] opcode;
    reg [15:0] rx_crc, received_crc, word_low;
    reg [1:0] word_phase;
    reg [6:0] word_index;
    reg [7:0] body [0:8];
    reg [2:0] payload_words;

    wire [8:0] body_end = rx_length + 9'd3;
    wire [8:0] frame_end = rx_length + 9'd5;
    wire [8:0] image_bytes = {1'b0, word_count} + {word_count, 1'b0};
    wire [7:0] rx_byte = {rx_shift, host_mosi};
    wire rx_body = rx_index >= 3 && rx_index < body_end;
    wire rx_close = rx_live && close_frame;
    wire frame_ok = !rx_bad_length && !rx_overrun && rx_bit == 0 &&
                    rx_index == frame_end && received_crc == rx_crc;
    wire good_config = body[0] >= 1 && body[0] <= 128 && body[1] >= 1 && body[1] <= 3 &&
        (body[4] & body[5]) == 0 && (body[6] & ~(body[4] | body[5])) == 0 &&
        (body[1][0] ? body[2] < body[0] : (body[2] == 0 && body[4] == 0)) &&
        (body[1][1] ? body[3] < body[0] : (body[3] == 0 && body[5] == 0));
    wire payload_ctx = body[0][0];
    wire payload_allowed = image_valid && body[0] <= 1 && enable_ctx[payload_ctx];

    reg build_reply;
    reg [2:0] gather, deferred_pop;
    reg reply_ctx;
    reg [7:0] reply_status;
    reg [3:0] reply_length, crc_index;
    reg [63:0] reply_body;
    reg [15:0] reply_crc;
    reg [6:0] tx_seen, tx_pos;
    wire [3:0] tx_data_end = reply_length + 4'd3;
    wire [6:0] tx_bits = {reply_length + 4'd5, 3'b0};
    wire [3:0] tx_byte_index = tx_pos[6:3];
    wire [7:0] tx_byte = tx_byte_index == tx_data_end ? reply_crc[7:0] :
                         tx_byte_index == tx_data_end + 4'd1 ? reply_crc[15:8] :
                         reply_data_byte(tx_byte_index, reply_status, reply_length, reply_body);
    assign host_miso = tx_live && !host_cs_n && tx_pos < tx_bits && tx_byte[3'd7 - tx_pos[2:0]];
    wire tx_close_ok = close_frame && tx_live && tx_seen == tx_bits;

    function [7:0] reply_data_byte;
        input [3:0] index;
        input [7:0] status;
        input [3:0] length;
        input [63:0] data;
        reg [2:0] body_index;
        begin
            body_index = index[2:0] - 3'd3;
            case (index)
                0: reply_data_byte = status;
                1: reply_data_byte = {4'b0, length};
                2: reply_data_byte = 0;
                default: reply_data_byte = data[{body_index, 3'b0} +: 8];
            endcase
        end
    endfunction

    wire fifo_ctx = (build_reply || tx_live || host_ready) ? reply_ctx : payload_ctx;
    wire [2:0] staged;
    wire [3:0] fifo_count;
    wire [15:0] fifo_peek;
    wire _unused_write_ready, stage_ready;
    wire [2:0] stage_word_index = staged;
    wire [3:0] stage_lo = {stage_word_index, 1'b0} + 4'd1;
    wire [3:0] stage_hi = stage_lo + 4'd1;
    wire [15:0] fifo_word = opcode == WRITEN && staged < 4 ? {body[stage_hi], body[stage_lo]} : {body[2], body[1]};
    wire [2:0] requested_words = rx_length[3:1];
    wire [2:0] read_count = fifo_count < {1'b0, body[1][2:0]} ? fifo_count[2:0] : body[1][2:0];
    wire [2:0] read_words = opcode == READ ? 3'd1 : read_count;
    wire valid_writen_size = rx_length >= 3 && rx_length <= 9 && rx_length[0];
    wire want_stage = opcode == WRITEN && payload_allowed && valid_writen_size && staged < payload_words;
    wire fifo_stage = enabled && rx_live && !host_cs_n && want_stage && stage_ready;
    wire fifo_commit = rx_close && frame_ok && opcode == WRITEN && payload_allowed && valid_writen_size;
    wire fifo_write = rx_close && response == OK && opcode == WRITE;
    wire fifo_abort = rx_close && opcode == WRITEN && !fifo_commit;
    wire abandon = rx_close && !launched && (response == BAD || opcode == BEGIN_IMAGE);
    wire fifo_clear = !selected || stop_pending || abandon;
    wire [2:0] fifo_release = tx_close_ok ? deferred_pop :
                              (rx_close && response == OK && opcode == READ) ? 3'd1 : 3'd0;
    wire [1:0] reply_peek = gather != 0 ? reply_length[2:1] - gather[1:0] : 2'd0;
    wire [3:0] ingress_free;
    // After the CRC bytes, staging can lag a core pop by at most one word.
    wire final_word = want_stage && ingress_free > {1'b0, staged};
    wire [2:0] accepted_words = staged + {2'b0, final_word};

    host_payload payload (
        .clk(clk), .rst_n(rst_n), .clear(fifo_clear), .ingress_pop(ingress_pop), .egress_push(egress_push),
        .egress_word(egress_word), .ingress_ready(ingress_ready), .egress_ready(egress_ready),
        .ingress_words(ingress_words), .host_ctx(fifo_ctx), .host_word(fifo_word), .host_write(fifo_write),
        .host_stage(fifo_stage), .host_commit(fifo_commit), .host_abort(fifo_abort),
        .host_commit_word(final_word), .host_stage_index(stage_word_index[1:0]),
        .host_write_ready(_unused_write_ready), .host_stage_ready(stage_ready), .host_ingress_free(ingress_free),
        .host_staged_count(staged), .host_peek(reply_peek), .host_release(fifo_release),
        .host_egress_count(fifo_count), .host_egress_word(fifo_peek)
    );

    reg [7:0] response;
    always @* begin
        response = BAD;
        if (frame_ok) begin
            case (opcode)
                BEGIN_IMAGE: response = launched ? STATE : rx_length == 7 && good_config ? OK : BAD;
                DATA: response = launched ? STATE : load_active && !have_data && rx_length == image_bytes ? OK : BAD;
                COMMIT: response = launched ? STATE : rx_length == 0 && have_data && !image_valid ? COMPLETE : BAD;
                START: response = rx_length != 0 ? BAD : launched || !image_valid ? STATE : OK;
                STOP: response = rx_length == 0 ? OK : BAD;
                READ: response = rx_length != 1 ? BAD : !payload_allowed ? STATE : fifo_count == 0 ? EMPTY : OK;
                READN: response = rx_length != 2 || body[1] < 1 || body[1] > 4 ? BAD :
                                  !payload_allowed ? STATE : fifo_count == 0 ? EMPTY : OK;
                WRITE: response = rx_length != 3 ? BAD : !payload_allowed ? STATE :
                                  ingress_free != 0 ? OK : FULL;
                WRITEN: response = !valid_writen_size ? BAD : !payload_allowed ? STATE :
                                   accepted_words == requested_words ? OK : FULL;
                default: response = BAD;
            endcase
        end
    end

    // Count every sampled bit, including extra clocks after a complete frame.
    always @(posedge clk) begin
        if (!enabled) begin
            cs_prev <= 0; sck_prev <= 0; rx_live <= 0; tx_live <= 0;
            rx_index <= 0; rx_bit <= 0; rx_shift <= 0; rx_length <= 0;
            rx_bad_length <= 0; rx_overrun <= 0; opcode <= 0;
            rx_crc <= 16'hffff; received_crc <= 0; word_low <= 0;
            word_phase <= 0; word_index <= 0; payload_words <= 0;
            tx_seen <= 0; tx_pos <= 0;
            prog_write_valid <= 0; prog_write_index <= 0; prog_write_word <= 0;
        end else begin
            cs_prev <= host_cs_n;
            sck_prev <= host_sck;
            prog_write_valid <= 0;
            if (begin_frame) begin
                rx_live <= !host_ready && !build_reply && !stop_pending;
                tx_live <= host_ready;
                tx_seen <= 0; tx_pos <= 0;
                rx_index <= 0; rx_bit <= 0; rx_shift <= 0; rx_length <= 0;
                rx_bad_length <= 0; rx_overrun <= 0; opcode <= 0;
                rx_crc <= 16'hffff; received_crc <= 0;
                word_phase <= 0; word_index <= 0; payload_words <= 0;
            end else if (close_frame) begin
                rx_live <= 0;
                tx_live <= 0;
            end else if (tx_live) begin
                if (rise && tx_seen <= tx_bits) tx_seen <= tx_seen + 7'd1;
                if (fall && tx_pos < tx_seen) tx_pos <= tx_pos + 7'd1;
            end else if (rx_live && rise) begin
                if (rx_index >= frame_end || rx_bad_length) rx_overrun <= 1;
                rx_shift <= rx_byte[6:0];
                rx_bit <= rx_bit + 3'd1;
                if (rx_index < body_end) rx_crc <= crc_bit(rx_crc, host_mosi);
                if (rx_bit == 7 && rx_index < 389) begin
                    rx_index <= rx_index + 9'd1;
                    case (rx_index)
                        0: opcode <= rx_byte;
                        1: rx_length[7:0] <= rx_byte;
                        2: begin
                            rx_length[8] <= rx_byte[0];
                            rx_bad_length <= rx_byte > 1 || (rx_byte == 1 && rx_length[7:0] > 128);
                        end
                        default: if (rx_body && !rx_bad_length) begin
                            if (rx_index < 12 && opcode != DATA)
                                body[rx_index[3:0] - 4'd3] <= rx_byte;
                            if (opcode == WRITEN && rx_index >= 5 && rx_index[0] && payload_words < 4)
                                payload_words <= payload_words + 3'd1;
                            if (opcode == DATA && load_active && !have_data && rx_length == image_bytes) begin
                                case (word_phase)
                                    0: begin word_low[7:0] <= rx_byte; word_phase <= 1; end
                                    1: begin word_low[15:8] <= rx_byte; word_phase <= 2; end
                                    default: begin
                                        prog_write_valid <= 1;
                                        prog_write_index <= word_index;
                                        prog_write_word <= {rx_byte, word_low};
                                        word_index <= word_index + 7'd1;
                                        word_phase <= 0;
                                    end
                                endcase
                            end
                        end else if (rx_index == body_end) received_crc[7:0] <= rx_byte;
                        else if (rx_index == body_end + 9'd1) received_crc[15:8] <= rx_byte;
                    endcase
                end
            end
        end
    end

    integer j;
    always @(posedge clk) begin
        if (!enabled) begin
            launched <= 0; have_config <= 0; have_data <= 0; image_valid <= 0;
            word_count <= 0; enable_ctx <= 0; entry0 <= 0; entry1 <= 0;
            owner0 <= 0; owner1 <= 0; open_drain <= 0; start <= 0; stop_pending <= 0;
            build_reply <= 0; gather <= 0; deferred_pop <= 0; reply_ctx <= 0;
            reply_status <= 0; reply_length <= 0; reply_body <= 0; reply_crc <= 16'hffff;
            crc_index <= 0; host_ready <= 0;
        end else begin
            start <= 0;
            stop_pending <= 0;
            if (tx_close_ok) begin
                host_ready <= 0;
                deferred_pop <= 0;
            end
            if (stop_pending) begin
                launched <= 0; have_config <= 0; have_data <= 0; image_valid <= 0;
                if (core_fault_safe)
                    reply_body[31:0] <= {5'b0, core_fault_cause, core_fault_pc, 7'b0, core_fault_ctx, 6'b0, FAULTED};
                build_reply <= 1;
            end
            if (build_reply) begin
                if (gather != 0) begin
                    for (j = 0; j < 4; j = j + 1)
                        if (reply_peek == j[1:0]) reply_body[j*16 +: 16] <= fifo_peek;
                    gather <= gather - 3'd1;
                end else if (crc_index < tx_data_end) begin
                    reply_crc <= crc_byte(reply_crc, reply_data_byte(crc_index, reply_status, reply_length, reply_body));
                    crc_index <= crc_index + 4'd1;
                end else begin
                    build_reply <= 0;
                    host_ready <= 1;
                end
            end
            if (rx_close) begin
                reply_status <= response;
                reply_length <= 0; reply_body <= 0; reply_crc <= 16'hffff; crc_index <= 0;
                gather <= 0; deferred_pop <= 0;
                reply_ctx <= payload_ctx;
                build_reply <= 1;
                if (abandon) begin
                    have_config <= 0; have_data <= 0; image_valid <= 0;
                end
                if (response == COMPLETE) image_valid <= 1;
                if (response == OK) begin
                    case (opcode)
                        BEGIN_IMAGE: begin
                            have_config <= 1;
                            word_count <= body[0]; enable_ctx <= body[1][1:0];
                            entry0 <= body[2][6:0]; entry1 <= body[3][6:0];
                            owner0 <= body[4]; owner1 <= body[5]; open_drain <= body[6];
                        end
                        DATA: have_data <= 1;
                        START: begin launched <= 1; start <= 1; end
                        STOP: begin
                            stop_pending <= 1;
                            build_reply <= 0;
                            reply_length <= 4;
                            reply_body[31:0] <= run_state == FAULTED ?
                                {5'b0, core_fault_cause, core_fault_pc, 7'b0, core_fault_ctx, 6'b0, FAULTED} :
                                {30'b0, run_state};
                        end
                        READ: begin
                            reply_length <= 2;
                            reply_body[15:0] <= fifo_peek;
                        end
                        READN: begin
                            reply_length <= {read_words, 1'b0};
                            gather <= read_words;
                            deferred_pop <= read_words;
                        end
                        default: begin end
                    endcase
                end
                if (opcode == WRITEN && (response == OK || response == FULL)) begin
                    reply_length <= 1;
                    reply_body[7:0] <= {5'b0, accepted_words};
                end
            end
        end
    end
endmodule

`default_nettype wire
