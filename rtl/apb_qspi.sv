// APB Wrapper for QSPI Master
// Author: Team Crispi - SSCS Chipathon 2026

module apb_qspi #(
    parameter int FIFO_DEPTH = 16
) (
    // clock and reset
    input logic clk_i,
    input logic rst_ni,

    // APB interface
    input logic psel_i,
    input logic penable_i,
    input logic pwrite_i,
    input logic [31:0] paddr_i,
    input logic [31:0] pwdata_i,
    output logic [31:0] prdata_o,
    output logic pready_o,

    // QSPI interface
    output logic qspi_csn_o,
    output logic qspi_sck_o,
    input logic [3:0] qspi_i,
    output logic [3:0] qspi_o,
    output logic [3:0] qspi_oe  // output enable for qspi_o
);



endmodule
