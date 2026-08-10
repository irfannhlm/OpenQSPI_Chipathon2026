// Simple fixed baud rate UART transmitter and receiver
// Strictly half duplex with 8N1 protocol (8 data bits, no parity, 1 stop bit)
// Author: Team Crispi - SSCS Chipathon 2026

module uart_simple #(
    parameter int CLOCK_FREQ = 50_000_000,
    parameter int BAUD_RATE  = 921_600
) (
    // Clock and reset
    input logic clk_i,
    input logic rst_ni,

    // Control signals
    input  logic uart_en_i,
    input  logic tx_start_i,
    output logic tx_done_o,
    output logic rx_valid_o,
    output logic rx_error_o,
    output logic uart_busy_o,

    input  logic [7:0] tx_data_i,
    output logic [7:0] rx_data_o,

    // UART interface
    input  logic uart_rx_i,
    output logic uart_tx_o
);
  localparam int BaudDiv = CLOCK_FREQ / BAUD_RATE;
  localparam int CntWidth = $clog2(BaudDiv);

  localparam logic [CntWidth-1:0] MaxCount = CntWidth'(BaudDiv - 1);
  localparam logic [CntWidth-1:0] MidCount = CntWidth'((BaudDiv >> 1) - 1);

  // Two stage synchronizer for UART RX input
  logic [1:0] uart_rx_sync;
  always_ff @(posedge clk_i) begin
    if (!rst_ni) begin
      uart_rx_sync <= 2'b11;
    end else begin
      uart_rx_sync <= {uart_rx_sync[0], uart_rx_i};
    end
  end
  wire uart_rx_filtered = uart_rx_sync[1];
  wire uart_rx_negedge = uart_rx_sync[1] && !uart_rx_sync[0];

  // Clock counter
  logic [CntWidth-1:0] clk_cnt;
  logic clk_cnt_rst;
  always_ff @(posedge clk_i) begin : clock_counter
    if (!rst_ni) begin
      clk_cnt <= '0;
    end else if (clk_cnt_rst) begin
      clk_cnt <= '0;
    end else begin
      if (clk_cnt == MaxCount) begin
        clk_cnt <= '0;
      end else begin
        clk_cnt <= clk_cnt + 1;
      end
    end
  end

  // Bit counter
  logic [2:0] bit_cnt;
  logic bit_cnt_rst;
  always_ff @(posedge clk_i) begin : bit_counter
    if (!rst_ni) begin
      bit_cnt <= '0;
    end else if (bit_cnt_rst) begin
      bit_cnt <= '0;
    end else if (clk_cnt == MaxCount) begin
      bit_cnt <= bit_cnt + 1;
    end
  end

  // RX shifter
  logic [7:0] rx_shift_reg;
  logic rx_shifter_en;
  always_ff @(posedge clk_i) begin : rx_shifter
    if (!rst_ni) begin
      rx_shift_reg <= '0;
    end else if (clk_cnt == MaxCount && rx_shifter_en) begin
      rx_shift_reg <= {uart_rx_filtered, rx_shift_reg[7:1]};  // shift in LSB first
    end
  end
  assign rx_data_o = rx_shift_reg;

  // TX shifter
  logic [8:0] tx_shift_reg;
  logic tx_shifter_en, tx_shifter_load;
  always_ff @(posedge clk_i) begin : tx_shifter
    if (!rst_ni) begin
      tx_shift_reg <= 9'b111111111;  // idle state is high
    end else if (tx_shifter_load) begin
      tx_shift_reg <= {tx_data_i, 1'b0};  // load data with start bit
    end else if (clk_cnt == MaxCount && tx_shifter_en) begin
      tx_shift_reg <= {1'b1, tx_shift_reg[8:1]};  // shift out LSB first
    end
  end
  assign uart_tx_o = tx_shift_reg[0];

  // UART mode flag
  logic uart_mode;  // 0: RX, 1: TX
  always_ff @(posedge clk_i) begin
    if (!rst_ni) begin
      uart_mode <= 1'b0;
    end else if (tx_start_i && !uart_busy_o) begin
      uart_mode <= 1'b1;
    end else if (tx_done_o || rx_valid_o) begin
      uart_mode <= 1'b0;
    end
  end

  // Main FSM
  typedef enum logic [1:0] {
    IDLE,
    START,
    DATA,
    STOP
  } uart_state_t;
  uart_state_t uart_cstate, uart_nstate;

  always_ff @(posedge clk_i) begin : fsm_reg
    if (!rst_ni) begin
      uart_cstate <= IDLE;
    end else begin
      uart_cstate <= uart_nstate;
    end
  end

  always_comb begin
    clk_cnt_rst = 1'b0;

    rx_error_o  = 1'b0;
    rx_valid_o  = 1'b0;
    tx_done_o   = 1'b0;

    uart_busy_o = 1'b0;

    uart_nstate = uart_cstate;

    case (uart_cstate)
      IDLE: begin
        clk_cnt_rst = 1'b1;

        if ((uart_rx_negedge || tx_start_i) && uart_en_i) begin
          uart_nstate = START;
        end
      end

      START: begin
        uart_busy_o = 1'b1;

        if (clk_cnt == MidCount && !uart_mode) begin
          if (uart_rx_filtered == 1'b0) begin
            clk_cnt_rst = 1'b1;
            uart_nstate = DATA;
          end else begin
            rx_error_o  = 1'b1;  // signals error on invalid start bit
            uart_nstate = IDLE;
          end
        end else if (clk_cnt == MaxCount && uart_mode) begin
          clk_cnt_rst = 1'b1;
          uart_nstate = DATA;
        end
      end

      DATA: begin
        uart_busy_o = 1'b1;

        if (clk_cnt == MaxCount && bit_cnt == 3'd7) begin
          uart_nstate = STOP;
        end
      end

      STOP: begin
        uart_busy_o = 1'b1;

        if (clk_cnt == MaxCount) begin
          if (!uart_mode) begin
            rx_valid_o = 1'b1;
          end else begin
            tx_done_o = 1'b1;
          end
          uart_nstate = IDLE;
        end
      end

      default: begin
        uart_nstate = IDLE;
      end
    endcase
  end

  assign bit_cnt_rst = clk_cnt_rst;
  assign rx_shifter_en = uart_busy_o && !uart_mode && !rx_valid_o;
  assign tx_shifter_en = uart_busy_o && uart_mode;
  assign tx_shifter_load = tx_start_i && !uart_busy_o && uart_en_i;


endmodule
