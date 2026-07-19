// Wrapper for APB QSPI testbench (pyuvm)
// apb_qspi DUT + S25FL128S flash model on a shared QSPI bus
// Author: Team Crispi - SSCS Chipathon 2026

`timescale 1ns / 1ps
module tb_apb_qspi (
    // Clock and reset
    input logic clk_i,
    input logic rst_ni,

    // Flash reset, kept separate from DUT reset so re-resetting the DUT
    // between tests does not re-trigger the flash model's power-up delay
    input logic flash_rstn_i,

    // APB interface
    input logic psel_i,
    input logic penable_i,
    input logic pwrite_i,
    input logic [31:0] paddr_i,
    input logic [31:0] pwdata_i,
    output logic [31:0] prdata_o,
    output logic pready_o
);

  // DUT
  logic qspi_csn;
  logic qspi_sck;
  logic [3:0] qspi_i, qspi_o, qspi_oe;

  apb_qspi #(
      .FIFO_DEPTH(64)  // spec: 64x32-bit data FIFO
  ) u_dut (
      .clk_i (clk_i),
      .rst_ni(rst_ni),

      .psel_i   (psel_i),
      .penable_i(penable_i),
      .pwrite_i (pwrite_i),
      .paddr_i  (paddr_i),
      .pwdata_i (pwdata_i),
      .prdata_o (prdata_o),
      .pready_o (pready_o),

      .qspi_csn_o(qspi_csn),
      .qspi_sck_o(qspi_sck),
      .qspi_i    (qspi_i),
      .qspi_o    (qspi_o),
      .qspi_oe   (qspi_oe)
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

  // MEMORY VERILOG MODEL
  // S25FL128S (Infineon), matches the competition spec's reference flash.
  // TimingModel must be a full part number: the model parses its 15th/16th
  // characters for latency config and sector/page size ("...000" -> 256B
  // page, 64KB sectors). The default "DefaultTimingModel" string leaves
  // PageSize/SecSize uninitialized (X), which silently corrupts every page
  // program (WByte assembly loop never runs -> memory programmed to X).
  s25fl128s #(
      .TimingModel("S25FL128SAGMFI000_R_30pF")
  ) u_flash (
      // Data Inputs/Outputs
      .SI     (qspi_io[0]),
      .SO     (qspi_io[1]),
      // Controls
      .SCK    (qspi_sck),
      .CSNeg  (qspi_csn),
      .RSTNeg (flash_rstn_i),
      .WPNeg  (qspi_io[2]),
      .HOLDNeg(qspi_io[3])
  );

  // Waveforms: use cocotb's built-in dump support -
  //   make WAVES=1          -> sim_build/tb_apb_qspi.fst
  //   python run.py --waves -> sim_build/tb_apb_qspi.fst
endmodule
