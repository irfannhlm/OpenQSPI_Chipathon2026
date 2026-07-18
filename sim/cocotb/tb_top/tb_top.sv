// Wrapper for QSPI master testbench
// Include multiple memory models from official vendors
// Author: Team Crispi - SSCS Chipathon 2026

`timescale 1ns / 1ps
module tb_top #(
    parameter int CLOCK_FREQ = 50_000_000,
    parameter int BAUD_RATE  = 921_600
) (
    // Clock and reset
    input logic clk_i,
    input logic rst_ni,

    // UART interface
    input  logic uart_rx_i,
    output logic uart_tx_o
);

  // QSPI interface
  logic qspi_csn;
  logic qspi_sck;
  wire [3:0] qspi_io;
  top #(
      .CS_NUM(1),
      .CLOCK_FREQ(CLOCK_FREQ),
      .BAUD_RATE(BAUD_RATE)
  ) u_top (
      // Clock and reset
      .clk_i (clk_i),
      .rst_ni(rst_ni),

      // UART interface
      .uart_rx_i(uart_rx_i),
      .uart_tx_o(uart_tx_o),

      // QSPI interface
      .qspi_csn_o(qspi_csn),
      .qspi_sck_o(qspi_sck),
      .qspi_io(qspi_io)
  );

  pullup (qspi_io[0]);
  pullup (qspi_io[1]);
  pullup (qspi_io[2]);
  pullup (qspi_io[3]);

  // MEMORY VERILOG MODELS
  // W25Q65NE (Winbond)
  W25QxxNExxIx u_flash1 (
      .CSn   (qspi_csn),
      .CLK   (qspi_sck),
      .DIO   (qspi_io[0]),
      .DO    (qspi_io[1]),
      .WPn   (qspi_io[2]),
      .HOLDn (qspi_io[3]),
      .RESETn(rst_ni)
  );
  //   // MX25L51245G (Macronix)
  //   MX25L51245G u_flash2 (
  //       .SCLK(qspi_sck),
  //       .CS(qspi_csn[1]),
  //       .SI(qspi_io[0]),
  //       .SO(qspi_io[1]),
  //       .WP(qspi_io[2]),
  //       .RESET(1'b1),  // tied high for simulation
  //       .SIO3(qspi_io[3])
  //   );

endmodule
