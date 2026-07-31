// Top-level wrapper for Team A09 Chipathon 2026 QSPI flash controller
// Author: Team Crispi - SSCS Chipathon 2026


module a09_chipathon26_top #(
    parameter int CLOCK_FREQ = 50_000_000,  // 50 MHz
    parameter int BAUD_RATE  = 921_600,     // 921600 bps
    parameter int CS_NUM     = 2            // Number of chip selects for QSPI
) (
`ifdef USE_POWER_PINS
    inout wire VDD,
    inout wire VSS,
`endif

    // Clock and reset
    input wire clk_i,
    input wire rst_ni,

    // UART interface
    input  wire uart_rx_i,
    output wire uart_tx_o,

    // QSPI interface
    output logic [CS_NUM-1:0] qspi_csn_o,
    output logic qspi_sck_o,
    input logic [3:0] qspi_i,
    output logic [3:0] qspi_o,
    output logic [3:0] qspi_oe  // output enable for qspi_o
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
  apb_qspi #(
      .FIFO_DEPTH(12),
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

endmodule
