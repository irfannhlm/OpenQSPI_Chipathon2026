// Top-level testbench for the QSPI flash controller
// Outside communication through UART, configure QSPI through CSR
// Author: Team Crispi - SSCS Chipathon 2026


module top #(
    parameter int NUM_CS = 2,
    parameter int CLOCK_FREQ = 50_000_000
) (
    // Clock and reset
    input logic clk_i,
    input logic rst_ni,

    // UART interface
    input  logic uart_rx_i,
    output logic uart_tx_o,

    // QSPI interface
    output logic qspi_cs_o,
    output logic qspi_clk_o,
    inout logic [3:0] qspi_io
);

  // UART TO APB INSTANCE


  // APB UART INSTANCE

endmodule
