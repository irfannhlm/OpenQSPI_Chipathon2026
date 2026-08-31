// Chip Top Testbench wrapper for QSPI test with official flash models

`include "pad_map.svh"

module bv_chip_tb (
`ifdef USE_POWER_PINS
    inout wire VDD,
    inout wire VSS,
`endif

    input wire clk_i,
    input wire rst_ni,

    input  wire uart_rx_i,
    output wire uart_tx_o
);

  // MAIN CHIP INSTANCE
  wire qspi_sck;
  wire qspi_csn0, qspi_csn1;
  wire qspi_io0, qspi_io1, qspi_io2, qspi_io3;
  A09_BV_chip #(
  ) i_chip_top (
    .N01(qspi_io2), .N02(qspi_io3), .N03(), .N04(), .N05(), .N06(), .N07(), .N08(), .N09(), .N10(), .N11(),
    .N12(), .N13(), .N14(), .N15(), .N16(), .N17(), .N18(), .N19(), .N20(), .N21(), .N22(),
    .E01(), .E02(), .E03(), .E04(), .E05(), .E06(), .E07(), .E08(), .E09(), .E10(), .E11(),
    .E12(), .E13(), .E14(), .E15(), .E16(), .E17(), .E18(), .E19(), .E20(), .E21(), .E22(),
    .S01(), .S02(), .S03(), .S04(), .S05(), .S06(), .S07(), .S08(), .S09(), .S10(), .S11(),
    .S12(), .S13(), .S14(), .S15(), .S16(), .S17(), .S18(), .S19(), .S20(), .S21(), .S22(),
    .W01(), .W02(), .W03(), .W04(), .W05(), .W06(), .W07(), .W08(), .W09(), .W10(), .W11(),
    .W12(VSS), .W13(VDD), .W14(clk_i), .W15(rst_ni), 
    .W16(uart_rx_i), .W17(uart_tx_o), .W18(qspi_csn0), .W19(qspi_csn1), .W20(qspi_sck), .W21(qspi_io0), .W22(qspi_io1)
  );

  MX25L51245G u_flash1 (
      .SCLK(qspi_sck),
      .CS(qspi_csn0),
      .SI(qspi_io0),
      .SO(qspi_io1),
      .WP(qspi_io2),
      .RESET(rst_ni),
      .SIO3(qspi_io3)
  );
  //   23LC1024 (Microchip)
  M23LC1024 u_flash2 (
      .SI_SIO0(qspi_io0),
      .SO_SIO1(qspi_io1),
      .SCK(qspi_sck),
      .CS_N(qspi_csn1),
      .SIO2(qspi_io2),
      .HOLD_N_SIO3(qspi_io3),
      .RESET(rst_ni)
  );

`ifdef SDF_ANNOTATE
  initial begin
    #1 $sdf_annotate(`SDF_FILE0, i_chip_top);
  end
`endif
endmodule
