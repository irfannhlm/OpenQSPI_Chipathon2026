// Top-level testbench for the QSPI flash controller
// Outside communication through UART, configure QSPI through CSR
// Author: Team Crispi - SSCS Chipathon 2026


module top #(
    parameter int CS_NUM     = 2,
    parameter int CLOCK_FREQ = 50_000_000,
    parameter int BAUD_RATE  = 921_600
) (
    // Clock and reset
    input logic clk_i,
    input logic rst_ni,

    // UART interface
    input  logic uart_rx_i,
    output logic uart_tx_o,

    // QSPI interface
    output logic [CS_NUM-1:0] qspi_csn_o,
    output logic qspi_sck_o,
    inout wire [3:0] qspi_io
);


  // UART TO APB INSTANCE
  // APB master interface
  logic [31:0] paddr;
  logic [31:0] pwdata;
  logic pwrite;
  logic penable;

  logic psel;
  logic [31:0] prdata;
  logic pready;
  logic pslverr;

  uart_to_apb #(
      // UART parameters
      .CLOCK_FREQ(CLOCK_FREQ),
      .BAUD_RATE (BAUD_RATE)
  ) inst_uart_to_apb (
      // Clock and reset
      .clk_i (clk_i),
      .rst_ni(rst_ni),

      // UART interface
      .uart_rx_i(uart_rx_i),
      .uart_tx_o(uart_tx_o),

      // APB master interface
      .paddr_o  (paddr),
      .pwdata_o (pwdata),
      .pwrite_o (pwrite),
      .penable_o(penable),

      .psel_o(psel),
      .prdata_i(prdata),
      .pready_i(pready),
      .pslverr_i(pslverr)

  );


  // APB_QSPI INSTANCE
  // QSPI interface
  logic [3:0] qspi_i;
  logic [3:0] qspi_o;
  logic [3:0] qspi_oe;  // output enable for qspi_o

  apb_qspi #(
      .FIFO_DEPTH(16),
      .CS_NUM(CS_NUM)
  ) inst_apb_qspi (
      // clock and reset
      .clk_i (clk_i),
      .rst_ni(rst_ni),

      // APB interface
      .psel_i(psel),
      .penable_i(penable),
      .pwrite_i(pwrite),
      .paddr_i(paddr),
      .pwdata_i(pwdata),
      .prdata_o(prdata),
      .pready_o(pready),
      .pslverr_o(pslverr),

      // QSPI interface
      .qspi_csn_o(qspi_csn_o),
      .qspi_sck_o(qspi_sck_o),
      .qspi_i(qspi_i),
      .qspi_o(qspi_o),
      .qspi_oe(qspi_oe)  // output enable for qspi_o
  );

  //IO BUFFER
  assign qspi_i = qspi_io;
  assign qspi_io[0] = qspi_oe[0] ? qspi_o[0] : 1'bz;
  assign qspi_io[1] = qspi_oe[1] ? qspi_o[1] : 1'bz;
  assign qspi_io[2] = qspi_oe[2] ? qspi_o[2] : 1'bz;
  assign qspi_io[3] = qspi_oe[3] ? qspi_o[3] : 1'bz;

endmodule
