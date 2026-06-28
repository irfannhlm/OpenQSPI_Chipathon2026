// Fully configurable 32-bit QSPI master module
// Supports single, dual and quad modes for command, address (3 or 4 bytes) and data phases
// Supports DDR with configurable clock prescaler (minimum 2)
// Author: Team Crispi - SSCS Chipathon 2026

module qspi_master #(
) (
    // Clock and reset
    input logic clk_i,
    input logic rst_ni,

    // QSPI interface
    output logic qspi_csn_o,
    output logic qspi_sck_o,

    input  logic [3:0] qspi_i,
    output logic [3:0] qspi_o,
    output logic [3:0] qspi_oe, // output enable for qspi_o

    // QSPI control signals
    input  logic qspi_abort_i,  // abort current transfer (will avoid MODE or DUMMY phase)
    input  logic qspi_start_i,  // start the transfer
    output logic qspi_done_o,   // transfer done

    // QSPI config
    input logic [7:0] qspi_prescaler_i,  // QSPI clock = clk_i / (qspi_prescaler_i + 2)
    input logic [1:0] qspi_addr_len_i,  // 0x: no address, 10: 3 bytes, 11: 4 bytes
    input logic [5:0] qspi_dummy_len_i,  // number of dummy cycles (max 63)
    input logic [31:0] qspi_data_len_i,  // number of bytes to read/write
    input logic [1:0] qspi_addr_mode_i,  // 0x: single, 10: dual, 11: quad
    input logic [1:0] qspi_data_mode_i,  // 0x: single, 10: dual, 11: quad
    input logic qspi_sck_mode_i,  // 0: (mode 0) CPOL=0, CPHA=0; 1: (mode 3) CPOL=1, CPHA=1
    input logic qspi_data_dir_i,  // 0: read, 1: write
    input logic qspi_crm_i,  // continuous read mode, ignores data length and keeps reading
    input logic qspi_ddr_i,  // double data rate mode
    input logic qspi_qpi_i,  // 0: SPI mode, 1: QPI mode (all phases are quad)

    // QSPI rx/tx data
    input logic [7:0] qspi_cmd_i,  // command to send
    input logic [31:0] qspi_addr_i,  // address to send, length is determined by qspi_addr_len_i
    input logic [7:0] qspi_mode_byte_i,  // mode byte to send after address phase
    input logic [31:0] qspi_wdata_i,  // data to send, length is determined by qspi_data_len_i
    output logic [31:0] qspi_rdata_o,  // data received, length is determined by qspi_data_len_i

    // FIFO interface
    input  logic fifo_empty_i,
    input  logic fifo_full_i,
    output logic fifo_push_o,
    output logic fifo_pop_o
);

  // QSPI SCK GEN
  // clock counter
  logic [7:0] clk_cnt;
  logic clk_cnt_en, clk_cnt_rst;
  always_ff @(posedge clk_i, negedge rst_ni) begin : clock_counter
    if (!rst_ni) begin
      clk_cnt <= 9'd0;
    end else if (clk_cnt_rst) begin
      clk_cnt <= 9'd0;
    end else if (clk_cnt_en) begin
      if (clk_cnt == qspi_prescaler_i) begin
        clk_cnt <= 9'd0;
      end else begin
        clk_cnt <= clk_cnt + 1;
      end
    end
  end

  // qspi_sck generation
  logic qspi_sck_int;
  logic qspi_sck_en;
  always_ff @(posedge clk_i, negedge rst_ni) begin : qspi_sck_gen
    if (!rst_ni) begin
      qspi_sck_int <= 1'b0;
    end else if (!qspi_sck_en) begin
      qspi_sck_int <= 1'b0;
    end else if (clk_cnt == qspi_prescaler_i) begin
      qspi_sck_int <= ~qspi_sck_int;
    end
  end
  wire qspi_sck_posedge = ~qspi_sck_int && (clk_cnt == qspi_prescaler_i);
  wire qspi_sck_negedge = qspi_sck_int && (clk_cnt == qspi_prescaler_i);

  // bit counter
  logic [3:0] bit_cnt;
  logic bit_cnt_rst;
  logic bit_cnt_ddr;
  always_ff @(posedge clk_i, negedge rst_ni) begin : bit_counter
    if (!rst_ni) begin
      bit_cnt <= 'd0;
    end else if (bit_cnt_rst) begin
      bit_cnt <= 'd0;
    end else if (qspi_sck_negedge || (bit_cnt_ddr && qspi_sck_posedge)) begin
      bit_cnt <= bit_cnt + 1;
    end
  end
  logic [2:0] bit_cnt_limit;
  logic [1:0] bit_cnt_limit_mode;  // 0x: single, 10: dual, 11: quad
  always_comb begin : adjust_bit_cnt
    case (bit_cnt_limit_mode)
      2'd0: bit_cnt_limit = 3'd7;  // 8 bits per byte
      2'd1: bit_cnt_limit = 3'd7;  // 8 bits per byte
      2'd2: bit_cnt_limit = 3'd3;  // 4 bits per byte
      2'd3: bit_cnt_limit = 3'd1;  // 2 bits per byte
      default: bit_cnt_limit = 3'd7;
    endcase
  end

  // byte counter
  logic [31:0] byte_cnt;
  logic byte_cnt_rst;
  wire byte_cnt_negedge = (bit_cnt == bit_cnt_limit && qspi_sck_negedge);
  always_ff @(posedge clk_i, negedge rst_ni) begin : byte_counter
    if (!rst_ni) begin
      byte_cnt <= 'd0;
    end else if (byte_cnt_rst) begin
      byte_cnt <= 'd0;
    end else if (byte_cnt_negedge) begin
      byte_cnt <= byte_cnt + 1;
    end
  end


  // TX ENGINE
  // main tx shifter
  logic [7:0] tx_shifter;
  logic [7:0] tx_shifter_in;  // input to shifter
  logic [3:0] tx_shifter_out;  // output to qspi_o
  logic [1:0] tx_shifter_mode;  // 0x: single, 10: dual, 11: quad
  logic tx_shifter_en, tx_shifter_load, tx_shifter_ddr;
  wire tx_shift = tx_shifter_en && (qspi_sck_negedge || (qspi_sck_posedge && tx_shifter_ddr));
  always_ff @(posedge clk_i, negedge rst_ni) begin : output_shifter
    if (!rst_ni) begin
      tx_shifter <= 8'd0;
    end else if (tx_shifter_load) begin
      tx_shifter <= tx_shifter_in;
    end else if (tx_shift) begin
      case (tx_shifter_mode)
        'd0: tx_shifter <= {tx_shifter[6:0], 1'b0};  // single mode, shift 1 bit
        'd1: tx_shifter <= {tx_shifter[6:0], 1'b0};  // single mode, shift 1 bit
        'd2: tx_shifter <= {tx_shifter[5:0], 2'b00};  // dual mode, shift 2 bits
        'd3: tx_shifter <= {tx_shifter[3:0], 4'b0000};  // quad mode, shift 4 bits
        default: tx_shifter <= {tx_shifter[6:0], 1'b0};
      endcase
    end
  end
  always_comb begin : tx_shifter_out_mux
    case (tx_shifter_mode)
      'd0: tx_shifter_out = {1'b0, 1'b0, 1'b0, tx_shifter[7]};
      'd1: tx_shifter_out = {1'b0, 1'b0, 1'b0, tx_shifter[7]};
      'd2: tx_shifter_out = {1'b0, 1'b0, tx_shifter[7], tx_shifter[6]};
      'd3: tx_shifter_out = {tx_shifter[7], tx_shifter[6], tx_shifter[5], tx_shifter[4]};
      default: tx_shifter_out = {4{1'b0}};
    endcase
  end

  // tx shifter input mux
  logic [1:0] tx_shifter_in_sel;  // 0: command, 1: address, 2: mode byte, 3: data
  logic [7:0] qspi_addr_byte;
  logic [7:0] qspi_wdata_byte;
  always_comb begin : tx_shifter_in_mux
    case (tx_shifter_in_sel)
      2'd0: tx_shifter_in = qspi_cmd_i;
      2'd1: tx_shifter_in = qspi_addr_byte;
      2'd2: tx_shifter_in = qspi_mode_byte_i;
      2'd3: tx_shifter_in = qspi_wdata_byte;
      default: tx_shifter_in = 8'd0;
    endcase
  end
  always_comb begin : qspi_addr_mux
    if (qspi_addr_len_i[1]) begin
      // 4 bytes address
      case (byte_cnt[1:0])
        2'd0: qspi_addr_byte = qspi_addr_i[31:24];
        2'd1: qspi_addr_byte = qspi_addr_i[23:16];
        2'd2: qspi_addr_byte = qspi_addr_i[15:8];
        2'd3: qspi_addr_byte = qspi_addr_i[7:0];
        default: qspi_addr_byte = 8'd0;
      endcase
    end else begin
      // 3 bytes address
      case (byte_cnt[1:0])
        2'd0: qspi_addr_byte = qspi_addr_i[23:16];
        2'd1: qspi_addr_byte = qspi_addr_i[15:8];
        2'd2: qspi_addr_byte = qspi_addr_i[7:0];
        default: qspi_addr_byte = 8'd0;
      endcase
    end
    qspi_addr_byte = qspi_addr_i[31:24];
  end
  always_comb begin : qspi_wdata_mux
    case (byte_cnt[1:0])
      2'd0: qspi_wdata_byte = qspi_data_i[31:24];
      2'd1: qspi_wdata_byte = qspi_data_i[23:16];
      2'd2: qspi_wdata_byte = qspi_data_i[15:8];
      2'd3: qspi_wdata_byte = qspi_data_i[7:0];
      default: qspi_wdata_byte = 8'd0;
    endcase
  end


  // RX ENGINE


  // CONTROL FSM


endmodule
