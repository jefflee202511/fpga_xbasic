// ========================================================
// xBASIC Generated Verilog : led_btn
// ========================================================

// Generated from xBASIC source.
// Control flow is implemented as a hardware FSM.
// PRINT streams over UART; the FSM waits for it to finish.

module led_btn (
    input wire clk,
    output wire UART_TX,
    output reg LED_02,
    input wire BTN_01
);

// ========================================================
// Button input: synchroniser + debounce + rising edge
// ========================================================

wire BTN_01_raw = BTN_01;
reg [1:0] BTN_01_sync;
reg BTN_01_pressed;
reg [16:0] BTN_01_settle;
reg BTN_01_pressed_prev;
wire BTN_01_pressed_rise = BTN_01_pressed && !BTN_01_pressed_prev;

always @(posedge clk) begin
    BTN_01_sync <= {BTN_01_sync[0], BTN_01_raw};
    if (BTN_01_sync[1] == BTN_01_pressed) begin
        BTN_01_settle <= 17'd120000;
    end else if (BTN_01_settle == 17'd0) begin
        BTN_01_pressed <= BTN_01_sync[1];
        BTN_01_settle <= 17'd120000;
    end else begin
        BTN_01_settle <= BTN_01_settle - 17'd1;
    end
end

initial begin
    BTN_01_pressed_prev = 1'b0;
    BTN_01_pressed = 1'b0;
    BTN_01_sync = 2'b00;
    BTN_01_settle = 17'd120000;
end

// ========================================================
// Initial LED State
// ========================================================

initial begin
    LED_02 = 1'b0;
end

// ========================================================
// DELAY counter (12000000 Hz clock, 23-bit)
// ========================================================

reg delay_active;
reg [22:0] delay_counter;

initial begin
    delay_active = 1'b0;
    delay_counter = 23'd0;
end

// ========================================================
// UART TX IP
// ========================================================

reg        uart_start;
reg [7:0]  uart_data;
wire       uart_busy;

uart_tx #(
    .CLK_FREQ(12000000),
    .BAUD_RATE(115200)
) uart_tx_inst (
    .clk(clk),
    .rst(1'b0),
    .start(uart_start),
    .data(uart_data),
    .tx(UART_TX),
    .busy(uart_busy)
);

// ========================================================
// xBASIC PRINT ROM
// ========================================================

reg [7:0] print_rom_0 [0:11];
reg [7:0] print_rom_1 [0:9];

initial begin
    print_rom_0[0] = 8'h74;
    print_rom_0[1] = 8'h65;
    print_rom_0[2] = 8'h73;
    print_rom_0[3] = 8'h74;
    print_rom_0[4] = 8'h20;
    print_rom_0[5] = 8'h62;
    print_rom_0[6] = 8'h74;
    print_rom_0[7] = 8'h6E;
    print_rom_0[8] = 8'h20;
    print_rom_0[9] = 8'h6F;
    print_rom_0[10] = 8'h6E;
    print_rom_0[11] = 8'h00;
    print_rom_1[0] = 8'h42;
    print_rom_1[1] = 8'h54;
    print_rom_1[2] = 8'h4E;
    print_rom_1[3] = 8'h31;
    print_rom_1[4] = 8'h20;
    print_rom_1[5] = 8'h6F;
    print_rom_1[6] = 8'h66;
    print_rom_1[7] = 8'h66;
    print_rom_1[8] = 8'h20;
    print_rom_1[9] = 8'h00;
end

reg [7:0] print_id;
reg [15:0] print_index;
reg print_active;
reg print_wait_busy;
reg print_wait_busy_high;
reg print_finished;
reg [7:0] print_byte;
reg [7:0] print_request;
reg [7:0] print_char_request;
reg print_char_mode;
reg print_request_valid;
// Minimum idle between messages: 1248 clocks (~12 bit times). Lets a mis-synced receiver resync.
localparam [10:0] PRINT_GAP_CYCLES = 11'd1248;
reg [10:0] print_gap;
reg print_value_request_valid;
reg signed [31:0] print_value_request;
reg signed [31:0] print_value;
reg [3:0] print_num_length;
reg print_num_negative;
reg [31:0] print_num_abs;
reg [7:0] print_num_rom [0:10];

// Binary -> BCD (double dabble), 32 clocks.
reg [39:0] bcd_digits;   // 10 decimal digits, 4 bits each
reg [31:0] bcd_shift;    // |value|, shifted out MSB first
reg [5:0]  bcd_count;
reg        bcd_busy;

wire [3:0] bcd_adj0 = (bcd_digits[3:0] >= 4'd5) ? (bcd_digits[3:0] + 4'd3) : bcd_digits[3:0];
wire [3:0] bcd_adj1 = (bcd_digits[7:4] >= 4'd5) ? (bcd_digits[7:4] + 4'd3) : bcd_digits[7:4];
wire [3:0] bcd_adj2 = (bcd_digits[11:8] >= 4'd5) ? (bcd_digits[11:8] + 4'd3) : bcd_digits[11:8];
wire [3:0] bcd_adj3 = (bcd_digits[15:12] >= 4'd5) ? (bcd_digits[15:12] + 4'd3) : bcd_digits[15:12];
wire [3:0] bcd_adj4 = (bcd_digits[19:16] >= 4'd5) ? (bcd_digits[19:16] + 4'd3) : bcd_digits[19:16];
wire [3:0] bcd_adj5 = (bcd_digits[23:20] >= 4'd5) ? (bcd_digits[23:20] + 4'd3) : bcd_digits[23:20];
wire [3:0] bcd_adj6 = (bcd_digits[27:24] >= 4'd5) ? (bcd_digits[27:24] + 4'd3) : bcd_digits[27:24];
wire [3:0] bcd_adj7 = (bcd_digits[31:28] >= 4'd5) ? (bcd_digits[31:28] + 4'd3) : bcd_digits[31:28];
wire [3:0] bcd_adj8 = (bcd_digits[35:32] >= 4'd5) ? (bcd_digits[35:32] + 4'd3) : bcd_digits[35:32];
wire [3:0] bcd_adj9 = (bcd_digits[39:36] >= 4'd5) ? (bcd_digits[39:36] + 4'd3) : bcd_digits[39:36];
wire [39:0] bcd_adj = {bcd_adj9, bcd_adj8, bcd_adj7, bcd_adj6, bcd_adj5, bcd_adj4, bcd_adj3, bcd_adj2, bcd_adj1, bcd_adj0};
wire [39:0] bcd_next = {bcd_adj[38:0], bcd_shift[31]};

wire [3:0] bcd_length =
    (bcd_digits[39:36] != 4'd0) ? 4'd10 :
    (bcd_digits[35:32] != 4'd0) ? 4'd9 :
    (bcd_digits[31:28] != 4'd0) ? 4'd8 :
    (bcd_digits[27:24] != 4'd0) ? 4'd7 :
    (bcd_digits[23:20] != 4'd0) ? 4'd6 :
    (bcd_digits[19:16] != 4'd0) ? 4'd5 :
    (bcd_digits[15:12] != 4'd0) ? 4'd4 :
    (bcd_digits[11:8] != 4'd0) ? 4'd3 :
    (bcd_digits[7:4] != 4'd0) ? 4'd2 :
    4'd1;

wire [31:0] print_value_abs = print_value_request[31] ? (~print_value_request + 32'd1) : print_value_request;

always @(*) begin
    print_byte = 8'h00;

    if (print_id == 8'd254) begin
        if (print_index == 16'd0)
            print_byte = print_char_request;
        else
            print_byte = 8'h00;
    end else if (print_id == 8'd255) begin
        if (print_num_negative && print_index == 16'd0)
            print_byte = 8'd45;   // '-' sign
        else if (print_index < print_num_length)
            print_byte = print_num_rom[11 - print_num_length + print_index];
        else
            print_byte = 8'h00;
    end else begin
        case (print_id)
        8'd0: print_byte = print_rom_0[print_index];
        8'd1: print_byte = print_rom_1[print_index];
        default: print_byte = 8'h00;
        endcase
    end
end

// ========================================================
// xBASIC Hardware FSM
// ========================================================

localparam integer FSM_STATE_WIDTH = 4;

localparam [3:0] STATE_0 = 4'd0;
localparam [3:0] STATE_1 = 4'd1;
localparam [3:0] STATE_2 = 4'd2;
localparam [3:0] STATE_3 = 4'd3;
localparam [3:0] STATE_4 = 4'd4;
localparam [3:0] STATE_5 = 4'd5;
localparam [3:0] STATE_6 = 4'd6;
localparam [3:0] STATE_7 = 4'd7;
localparam [3:0] STATE_8 = 4'd8;
localparam [3:0] STATE_9 = 4'd9;
localparam [3:0] STATE_10 = 4'd10;

localparam [3:0] STATE_DONE = 4'd11;
reg [3:0] fsm_state;

initial begin
    fsm_state = STATE_0;
    delay_active = 1'b0;
    delay_counter = 23'd0;
    uart_start = 1'b0;
    uart_data = 8'h00;
    print_id = 8'h00;
    print_index = 16'd0;
    print_active = 1'b0;
    print_wait_busy = 1'b0;
    print_wait_busy_high = 1'b0;
    print_finished = 1'b0;
    print_request = 8'h00;
    print_char_request = 8'h00;
    print_char_mode = 1'b0;
    print_request_valid = 1'b0;
    print_gap = 0;
    print_value_request_valid = 1'b0;
    print_value_request = 32'd0;
    print_value = 32'd0;
    print_num_length = 4'd1;
    print_num_negative = 1'b0;
    print_num_abs = 32'd0;
    bcd_digits = 40'd0;
    bcd_shift = 32'd0;
    bcd_count = 6'd0;
    bcd_busy = 1'b0;
end

always @(posedge clk) begin
    // Update button previous states
    BTN_01_pressed_prev <= BTN_01_pressed;

    // UART start is a one-clock pulse
    uart_start <= 1'b0;

    if (BTN_01_pressed_rise) begin
        print_request <= 8'd0;
        print_request_valid <= 1'b1;
    end

    // ---------------------------------------------
    // PRINT UART FSM
    // ---------------------------------------------
    if (print_active) begin

        if (!print_wait_busy) begin

            if (print_char_mode || print_byte != 8'h00) begin
                uart_data <= print_byte;
                uart_start <= 1'b1;
                print_wait_busy <= 1'b1;
                print_wait_busy_high <= 1'b0;

            end else begin
                print_active <= 1'b0;
                print_finished <= 1'b1;
                // Force the TX line idle for a while so a
                // mis-synced receiver can re-lock.
                print_gap <= PRINT_GAP_CYCLES;
            end

        end else begin
            // Wait for UART BUSY rising edge, then BUSY falling edge.
            if (!print_wait_busy_high) begin
                if (uart_busy) begin
                    print_wait_busy_high <= 1'b1;
                end
            end else if (!uart_busy) begin
                print_wait_busy <= 1'b0;
                print_wait_busy_high <= 1'b0;
                if (print_char_mode) begin
                    print_char_mode <= 1'b0;
                    print_active <= 1'b0;
                    print_finished <= 1'b1;
                end else begin
                    print_index <= print_index + 1'b1;
                end
            end
        end

    end

    // Numeric PRINT : start binary -> BCD conversion.
    if (!print_active && !bcd_busy && print_value_request_valid) begin
        print_value        <= print_value_request;
        print_num_negative <= print_value_request[31];
        print_num_abs      <= print_value_abs;
        bcd_shift          <= print_value_abs;
        bcd_digits         <= 40'd0;
        bcd_count          <= 6'd32;
        bcd_busy           <= 1'b1;
        print_value_request_valid <= 1'b0;
    end else if (bcd_busy) begin
        if (bcd_count != 6'd0) begin
            // One double-dabble step per clock.
            bcd_digits <= bcd_next;
            bcd_shift  <= {bcd_shift[30:0], 1'b0};
            bcd_count  <= bcd_count - 6'd1;
        end else begin
            bcd_busy <= 1'b0;

            // print_num_rom[0] is never selected by the read mux
            // (index 0 is always the '-' column). Drive it anyway
            // so synthesis does not report an undriven wire.
            print_num_rom[0] <= 8'h00;

            // Digits come from the ABSOLUTE value. The '-' sign is
            // emitted by the print_byte mux, never stored here.
            print_num_rom[1] <= 8'd48 + bcd_digits[39:36];
            print_num_rom[2] <= 8'd48 + bcd_digits[35:32];
            print_num_rom[3] <= 8'd48 + bcd_digits[31:28];
            print_num_rom[4] <= 8'd48 + bcd_digits[27:24];
            print_num_rom[5] <= 8'd48 + bcd_digits[23:20];
            print_num_rom[6] <= 8'd48 + bcd_digits[19:16];
            print_num_rom[7] <= 8'd48 + bcd_digits[15:12];
            print_num_rom[8] <= 8'd48 + bcd_digits[11:8];
            print_num_rom[9] <= 8'd48 + bcd_digits[7:4];
            print_num_rom[10] <= 8'd48 + bcd_digits[3:0];

            // total length = digits (+ 1 column for '-')
            print_num_length <= print_num_negative ? (bcd_length + 4'd1) : bcd_length;

            print_id             <= 8'd255;
            print_index          <= 16'd0;
            print_active         <= 1'b1;
            print_finished       <= 1'b0;
            print_wait_busy      <= 1'b0;
            print_wait_busy_high <= 1'b0;
        end
    end

    // Inter-message idle countdown.
    if (print_gap != 0) begin
        print_gap <= print_gap - 1'b1;
    end

    if (!print_active && !bcd_busy && print_gap == 0 && print_request_valid) begin
        print_id <= print_request;
        if (print_request != 8'd254) print_char_mode <= 1'b0;
        print_index <= 16'd0;
        print_active <= 1'b1;
        print_finished <= 1'b0;
        print_wait_busy <= 1'b0;
        print_wait_busy_high <= 1'b0;
        print_request_valid <= 1'b0;
    end

    // ---------------------------------------------
    // BASIC FSM
    // ---------------------------------------------

    case (fsm_state)

        STATE_0: begin
            // WHILE 1
            fsm_state <= STATE_1;
        end

        STATE_1: begin
            // IF BTN1
            if (BTN_01_pressed) begin
                fsm_state <= STATE_2;
            end else begin
                fsm_state <= STATE_6;
            end
        end

        STATE_2: begin
            // PRINT "test btn on"
            // Button PRINT request is handled by the independent UART engine
            fsm_state <= STATE_3;
        end

        STATE_3: begin
            // LED_02 = ON
            LED_02 <= 1'b1;
            fsm_state <= STATE_4;
        end

        STATE_4: begin
            // DELAY 200  (2400000 clocks)
            if (!delay_active) begin
                delay_counter <= 23'd2399999;
                delay_active  <= 1'b1;
                fsm_state <= STATE_4;
            end else if (delay_counter == 23'd0) begin
                delay_active <= 1'b0;
                fsm_state <= STATE_5;
            end else begin
                delay_counter <= delay_counter - 23'd1;
                fsm_state <= STATE_4;
            end
        end

        STATE_5: begin
            // ELSE
            fsm_state <= STATE_10;
        end

        STATE_6: begin
            // PRINT "BTN1 off "
            if (print_finished) begin
                // One loop PRINT completed: acknowledge and continue to WEND
                print_finished <= 1'b0;
                fsm_state <= STATE_7;
            end else if (!print_active && !bcd_busy && !print_request_valid) begin
                print_request <= 8'd1;
                print_request_valid <= 1'b1;
                // Stay here until the UART engine completes this message
                fsm_state <= STATE_6;
            end else begin
                fsm_state <= STATE_6;
            end
        end

        STATE_7: begin
            // LED_02 = OFF
            LED_02 <= 1'b0;
            fsm_state <= STATE_8;
        end

        STATE_8: begin
            // DELAY 500  (6000000 clocks)
            if (!delay_active) begin
                delay_counter <= 23'd5999999;
                delay_active  <= 1'b1;
                fsm_state <= STATE_8;
            end else if (delay_counter == 23'd0) begin
                delay_active <= 1'b0;
                fsm_state <= STATE_9;
            end else begin
                delay_counter <= delay_counter - 23'd1;
                fsm_state <= STATE_8;
            end
        end

        STATE_9: begin
            // ENDIF
            fsm_state <= STATE_10;
        end

        STATE_10: begin
            // WEND -> WHILE
            fsm_state <= STATE_0;
        end

        STATE_DONE: begin
            // Program completed: hold here (do not restart).
            fsm_state <= STATE_DONE;
        end
        default: begin
            fsm_state <= STATE_0;
        end

    endcase

end


endmodule