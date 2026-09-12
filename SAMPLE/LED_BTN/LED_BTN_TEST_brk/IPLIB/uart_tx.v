
// ========================================================
// xBASIC UART TX IP
// ========================================================
//
// Simple 8-bit UART transmitter
//
// Clock : parameter
// Baud  : parameter
//
// Format:
//   8 data bits
//   No parity
//   1 stop bit
//
// TX idle state = HIGH
//
// ========================================================

module uart_tx #(
    parameter integer CLK_FREQ  = 12000000,
    parameter integer BAUD_RATE = 115200
)(
    input  wire       clk,
    input  wire       rst,

    input  wire       start,
    input  wire [7:0] data,

    output reg        tx,
    output reg        busy
);

    localparam integer CLKS_PER_BIT =
        CLK_FREQ / BAUD_RATE;

    reg [31:0] clk_count;
    reg [3:0]  bit_index;
    reg [9:0]  tx_shift;

    always @(posedge clk) begin

        if (rst) begin

            tx        <= 1'b1;
            busy      <= 1'b0;
            clk_count <= 0;
            bit_index <= 0;
            tx_shift  <= 10'b1111111111;

        end else begin

            if (!busy) begin

                tx <= 1'b1;

                if (start) begin

                    tx_shift <= {
                        1'b1,
                        data,
                        1'b0
                    };

                    busy      <= 1'b1;
                    clk_count <= 0;
                    bit_index <= 0;

                    tx <= 1'b0;
                end

            end else begin

                if (clk_count >= CLKS_PER_BIT - 1) begin

                    clk_count <= 0;

                    if (bit_index == 9) begin

                        busy <= 1'b0;
                        tx   <= 1'b1;

                    end else begin

                        bit_index <= bit_index + 1'b1;

                        tx <= tx_shift[
                            bit_index + 1'b1
                        ];

                    end

                end else begin

                    clk_count <= clk_count + 1'b1;

                end
            end
        end
    end

endmodule
