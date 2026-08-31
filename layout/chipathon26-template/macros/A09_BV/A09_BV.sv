// Top-level wrapper for Team A09 Chipathon 2026 QSPI flash controller
// Aligned to the given BH block type and pinout
// Author: Team Crispi - SSCS Chipathon 2026


module A09_BV #(
    parameter int CLOCK_FREQ = 40_000_000,  // 40 MHz
    parameter int BAUD_RATE  = 2_000_000,   // 2 Mbps
    parameter int FIFO_DEPTH = 8,           // Depth of the FIFO
    parameter int CS_NUM     = 2            // Number of chip selects for QSPI
) (
`ifdef USE_POWER_PINS
    inout wire VDD,
    inout wire VSS,
`endif

    // Clock and reset
    input  logic clk,
    output logic clk_PU,
    output logic clk_PD,

    input  logic rst_n,
    output logic rst_n_PU,
    output logic rst_n_PD,


    // UART interface
    input  logic uart_rx,
    output logic uart_rx_PU,
    output logic uart_rx_PD,

    input logic uart_tx_IN,
    output logic uart_tx_OUT,
    output logic uart_tx_CS,  // input type
    output logic uart_tx_SL,  // output slew rate
    output logic uart_tx_PU,  // pull-up
    output logic uart_tx_PD,  // pull-down
    output logic uart_tx_OE,  // output enable
    output logic uart_tx_IE,  // input enable
    output logic uart_tx_PDRV0,  // drive strength 0
    output logic uart_tx_PDRV1,  // drive strength 1


    // QSPI interface
    input logic [CS_NUM-1:0] qspi_csn_IN,
    output logic [CS_NUM-1:0] qspi_csn_OUT,
    output logic [CS_NUM-1:0] qspi_csn_CS,  // input type
    output logic [CS_NUM-1:0] qspi_csn_SL,  // output slew rate
    output logic [CS_NUM-1:0] qspi_csn_PU,  // pull-up
    output logic [CS_NUM-1:0] qspi_csn_PD,  // pull-down
    output logic [CS_NUM-1:0] qspi_csn_OE,  // output enable
    output logic [CS_NUM-1:0] qspi_csn_IE,  // input enable
    output logic [CS_NUM-1:0] qspi_csn_PDRV0,  // drive strength 0
    output logic [CS_NUM-1:0] qspi_csn_PDRV1,  // drive strength 1

    input logic qspi_sck_IN,
    output logic qspi_sck_OUT,
    output logic qspi_sck_CS,  // input type
    output logic qspi_sck_SL,  // output slew rate
    output logic qspi_sck_PU,  // pull-up
    output logic qspi_sck_PD,  // pull-down
    output logic qspi_sck_OE,  // output enable
    output logic qspi_sck_IE,  // input enable
    output logic qspi_sck_PDRV0,  // drive strength 0
    output logic qspi_sck_PDRV1,  // drive strength 1

    input wire [3:0] qspi_io_IN,
    output logic [3:0] qspi_io_OUT,
    output logic [3:0] qspi_io_CS,  // input type
    output logic [3:0] qspi_io_SL,  // output slew rate
    output logic [3:0] qspi_io_PU,  // pull-up
    output logic [3:0] qspi_io_PD,  // pull-down
    output logic [3:0] qspi_io_OE,  // output enable
    output logic [3:0] qspi_io_IE,  // input enable
    output logic [3:0] qspi_io_PDRV0,  // drive strength 0
    output logic [3:0] qspi_io_PDRV1  // drive strength 1

);

  // Pipeline reset signal
  logic rst_n_q;
  always_ff @(posedge clk) begin : rst_reg
    rst_n_q <= rst_n;
  end

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
      .clk_i (clk),
      .rst_ni(rst_n_q),

      // UART interface
      .uart_rx_i(uart_rx),
      .uart_tx_o(uart_tx_OUT),

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
  logic [3:0] qspi_oe;
  apb_qspi #(
      .FIFO_DEPTH(FIFO_DEPTH),
      .CS_NUM(CS_NUM)
  ) inst_apb_qspi (
      // clock and reset
      .clk_i (clk),
      .rst_ni(rst_n_q),

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
      .qspi_csn_o(qspi_csn_OUT),
      .qspi_sck_o(qspi_sck_OUT),
      .qspi_i(qspi_io_IN),
      .qspi_o(qspi_io_OUT),
      .qspi_oe(qspi_oe)
  );

  // IO CELLS CONTROL SIGNALS
  assign clk_PU = 1'b0;  // no pull-up for clk
  assign clk_PD = 1'b0;  // no pull-down for clk

  assign rst_n_PU = 1'b0;  // no pull-up for rst_n
  assign rst_n_PD = 1'b0;  // no pull-down for rst_n

  assign uart_rx_PU = 1'b0;  // no pull-up for uart_rx
  assign uart_rx_PD = 1'b0;  // no pull-down for uart_rx

  assign uart_tx_CS = 1'b0;  // CMOS input type for uart_tx
  assign uart_tx_SL = 1'b0;  // fast slew rate for uart_tx
  assign uart_tx_PU = 1'b0;  // no pull-up for uart_tx
  assign uart_tx_PD = 1'b0;  // no pull-down for uart_tx
  assign uart_tx_OE = 1'b1;  // always enable output for uart_tx
  assign uart_tx_IE = 1'b0;  // disable input for uart_tx
  assign uart_tx_PDRV0 = 1'b1;  // 8mA output drive strength for uart_tx
  assign uart_tx_PDRV1 = 1'b0;  // 8mA output drive strength for uart_tx

  assign qspi_csn_CS = {CS_NUM{1'b0}};  // CMOS input type for qspi_csn
  assign qspi_csn_SL = {CS_NUM{1'b0}};  // fast slew rate for qspi_csn
  assign qspi_csn_PU = {CS_NUM{1'b1}};  // pull-up for qspi_csn
  assign qspi_csn_PD = {CS_NUM{1'b0}};  // no pull-down for qspi_csn
  assign qspi_csn_OE = {CS_NUM{1'b1}};  // always enable output for qspi_csn
  assign qspi_csn_IE = {CS_NUM{1'b0}};  // disable input for qspi_csn
  assign qspi_csn_PDRV0 = {CS_NUM{1'b0}};  // 12mA output drive strength for qspi_csn
  assign qspi_csn_PDRV1 = {CS_NUM{1'b1}};  // 12mA output drive strength for qspi_csn

  assign qspi_sck_CS = 1'b0;  // CMOS input type for qspi_sck
  assign qspi_sck_SL = 1'b0;  // fast slew rate for qspi_sck
  assign qspi_sck_PU = 1'b0;  // no pull-up for qspi_sck
  assign qspi_sck_PD = 1'b0;  // no pull-down for qspi_sck
  assign qspi_sck_OE = 1'b1;  // always enable output for qspi_sck
  assign qspi_sck_IE = 1'b0;  // disable input for qspi_sck
  assign qspi_sck_PDRV0 = 1'b0;  // 12mA output drive strength for qspi_sck
  assign qspi_sck_PDRV1 = 1'b1;  // 12mA output drive strength for qspi_sck

  assign qspi_io_CS = 4'b0000;  // CMOS input type for qspi_io
  assign qspi_io_SL = 4'b0000;  // fast slew rate for qspi_io
  assign qspi_io_PU = 4'b1111;  // pull-up for qspi_io
  assign qspi_io_PD = 4'b0000;  // no pull-down for qspi_io
  assign qspi_io_OE = qspi_oe;  // output enable for qspi_io is driven by the controller
  assign qspi_io_IE = ~qspi_oe;  // input enable is the inverse of output enable for qspi_io
  assign qspi_io_PDRV0 = 4'b1111;  // 16mA output drive strength for qspi_io
  assign qspi_io_PDRV1 = 4'b1111;  // 16mA output drive strength for qspi_io

endmodule
