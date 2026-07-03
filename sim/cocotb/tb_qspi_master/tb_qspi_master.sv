// Wrapper for QSPI master testbench
// Include multiple memory models from official vendors
// Author: Team Crispi - SSCS Chipathon 2026

`timescale 1ns / 1ps
module tb_qspi_master #(
    parameter int CS_NUM = 3  // number of chip selects
) (
    // Clock and reset
    input logic clk_i,
    input logic rst_ni,

    // QSPI control signals
    input  logic qspi_abort_i,   // abort current transfer (will avoid MODE or DUMMY phase)
    input  logic qspi_start_i,   // start the transfer
    output logic qspi_done_o,    // transfer done
    output logic qspi_timeout_o, // transfer timeout

    // QSPI config
    input logic [31:0] qspi_timeout_i,  // timeout in clock cycles (0: no timeout)
    input logic [7:0] qspi_prescaler_i,  // QSPI clock = clk_i / (qspi_prescaler_i + 2)
    input logic qspi_addr_len_i,  // 0: 3 bytes, 1: 4 bytes
    input logic [5:0] qspi_dummy_len_i,  // number of dummy cycles (max 63)
    input logic [31:0] qspi_data_len_i,  // number of bytes to read/write
    input logic [1:0] qspi_cmd_mode_i,  // 00: no command, 01: single, 10: dual, 11: quad
    input logic [1:0] qspi_addr_mode_i,  // 00: no address, 01: single, 10: dual, 11: quad
    input logic [1:0] qspi_data_mode_i,  // 00: no data, 01: single, 10: dual, 11: quad
    input logic [CS_NUM-1:0] qspi_csn_sel_i,  // csn selector
    input logic qspi_sck_mode_i,  // 0: (mode 0) CPOL=0, CPHA=0; 1: (mode 3) CPOL=1, CPHA=1
    input logic qspi_data_dir_i,  // 0: read, 1: write
    input logic qspi_crm_i,  // continuous read mode, ignores data length and keeps reading
    input logic qspi_ddr_i,  // double data rate mode
    input logic qspi_endian_i,  // 0: big endian, 1: little endian

    // QSPI rx/tx data
    input logic [7:0] qspi_cmd_i,  // command to send
    input logic [31:0] qspi_addr_i,  // address to send, length is determined by qspi_addr_len_i
    input logic [7:0] qspi_mode_byte_i,  // mode byte to send after address phase
    input logic [31:0] qspi_wdata_i,  // data to send, length is determined by qspi_data_len_i
    output logic [31:0] qspi_rdata_o,  // data received, length is determined by qspi_data_len_i
    output logic [31:0] qspi_byte_cnt_o,  // the current byte count

    // FIFO interface
    input  logic fifo_empty_i,
    input  logic fifo_full_i,
    output logic fifo_push_o,
    output logic fifo_pop_o
);

  // QSPI MASTER INSTANCE
  logic qspi_sck;
  logic [CS_NUM-1:0] qspi_csn;
  logic [3:0] qspi_i, qspi_o, qspi_oe;
  qspi_master #(
      .CS_NUM(CS_NUM)
  ) u_master (
      // Clock and reset
      .clk_i (clk_i),
      .rst_ni(rst_ni),

      // QSPI control signals
      .qspi_abort_i(qspi_abort_i),
      .qspi_start_i(qspi_start_i),
      .qspi_done_o(qspi_done_o),
      .qspi_timeout_o(qspi_timeout_o),

      // QSPI config
      .qspi_timeout_i(qspi_timeout_i),
      .qspi_prescaler_i(qspi_prescaler_i),
      .qspi_addr_len_i(qspi_addr_len_i),
      .qspi_dummy_len_i(qspi_dummy_len_i),
      .qspi_data_len_i(qspi_data_len_i),
      .qspi_cmd_mode_i(qspi_cmd_mode_i),
      .qspi_addr_mode_i(qspi_addr_mode_i),
      .qspi_data_mode_i(qspi_data_mode_i),
      .qspi_csn_sel_i(qspi_csn_sel_i),
      .qspi_sck_mode_i(qspi_sck_mode_i),
      .qspi_data_dir_i(qspi_data_dir_i),
      .qspi_crm_i(qspi_crm_i),
      .qspi_ddr_i(qspi_ddr_i),
      .qspi_endian_i(qspi_endian_i),
      .qspi_cmd_i(qspi_cmd_i),
      .qspi_addr_i(qspi_addr_i),
      .qspi_mode_byte_i(qspi_mode_byte_i),
      .qspi_wdata_i(qspi_wdata_i),
      .qspi_rdata_o(qspi_rdata_o),
      .qspi_byte_cnt_o(qspi_byte_cnt_o),

      // QSPI interface
      .qspi_csn_o(qspi_csn),
      .qspi_sck_o(qspi_sck),
      .qspi_i(qspi_i),
      .qspi_o(qspi_o),
      .qspi_oe(qspi_oe),

      // FIFO interface
      .fifo_empty_i(fifo_empty_i),
      .fifo_full_i (fifo_full_i),
      .fifo_push_o (fifo_push_o),
      .fifo_pop_o  (fifo_pop_o)
  );

  // QSPI IO BUFFERS
  wire [3:0] qspi_io;
  assign qspi_io[0] = qspi_oe[0] ? qspi_o[0] : 1'bz;
  assign qspi_io[1] = qspi_oe[1] ? qspi_o[1] : 1'bz;
  assign qspi_io[2] = qspi_oe[2] ? qspi_o[2] : 1'bz;
  assign qspi_io[3] = qspi_oe[3] ? qspi_o[3] : 1'bz;
  assign qspi_i = qspi_io;

  pullup (qspi_io[0]);
  pullup (qspi_io[1]);
  pullup (qspi_io[2]);
  pullup (qspi_io[3]);

  // MEMORY VERILOG MODELS
  // S25FL128S (Infineon)
  s25fl128s u_flash0 (
      // Data Inputs/Outputs
      .SI     (qspi_io[0]),
      .SO     (qspi_io[1]),
      // Controls
      .SCK    (qspi_sck),
      .CSNeg  (qspi_csn[0]),
      .RSTNeg (rst_ni),
      .WPNeg  (qspi_io[2]),
      .HOLDNeg(qspi_io[3])

  );
  // W25Q65NE (Winbond)
  W25QxxNExxIx u_flash1 (
      .CSn   (qspi_csn[1]),
      .CLK   (qspi_sck),
      .DIO   (qspi_io[0]),
      .DO    (qspi_io[1]),
      .WPn   (qspi_io[2]),
      .HOLDn (qspi_io[3]),
      .RESETn(rst_ni)
  );
  // MX25L51245G (Macronix)
  MX25L51245G u_flash2 (
      .SCLK(qspi_sck),
      .CS  (qspi_csn[2]),
      .SI  (qspi_io[0]),
      .SO  (qspi_io[1]),
      .WP  (qspi_io[2]),
      .SIO3(qspi_io[3])
  );

    // --- Waveform Generation ---
    initial begin
        $dumpfile("qspi_waves.vcd"); // 
        $dumpvars(0, tb_qspi_master);
    end
endmodule
