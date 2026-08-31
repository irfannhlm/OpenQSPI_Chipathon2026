// SPDX-License-Identifier: Apache-2.0
//
// A09_BV_chip - integration netlist: the pre-hardened A09_BV macro inside the
// Chipathon-supplied pad ring A09_BV_padring (layout/project_defs/BV/).
//
// - SOURCE side of LVS (netgen) against the Magic-extracted layout of
//   bv_chip/out/A09_BV_chip.gds
// - DUT for cocotb/bv_chip_tb.sv
// Plain Verilog-2001, no defines - VDD/VSS on the macro are always connected to
// the ring rails W13/W12.
//
//   Top ports  = the 88 perimeter balls of A09_BV_padring (N01..W22).
//                W12 = VSS ball, W13 = VDD ball.
//   u_padring  = A09_BV_padring   (bv_chip/A09_BV_padring.prep.v, from prep.py)
//   u_core     = A09_BV           (macros/A09_BV/final/pnl/A09_BV.pnl.v, gate-level)
//
// Pin map (layout/project_defs/BV/A09_BV_pad_map.yaml):
//   clk->W14(in_s)  rst_n->W15(in_c)  uart_rx->W16(in_c)  uart_tx->W17(bi_t)
//   qspi_csn[0]->W18  qspi_csn[1]->W19  qspi_sck->W20
//   qspi_io[0]->W21   qspi_io[1]->W22  qspi_io[2]->N01  qspi_io[3]->N02
//   bidir terminal rename: core *_OUT <-> pad .A , core *_IN <-> pad .Y

module A09_BV_chip (
    N01, N02, N03, N04, N05, N06, N07, N08, N09, N10, N11,
    N12, N13, N14, N15, N16, N17, N18, N19, N20, N21, N22,
    E01, E02, E03, E04, E05, E06, E07, E08, E09, E10, E11,
    E12, E13, E14, E15, E16, E17, E18, E19, E20, E21, E22,
    S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11,
    S12, S13, S14, S15, S16, S17, S18, S19, S20, S21, S22,
    W01, W02, W03, W04, W05, W06, W07, W08, W09, W10, W11,
    W12, W13, W14, W15, W16, W17, W18, W19, W20, W21, W22
);
  inout N01, N02, N03, N04, N05, N06, N07, N08, N09, N10, N11,
        N12, N13, N14, N15, N16, N17, N18, N19, N20, N21, N22;
  inout E01, E02, E03, E04, E05, E06, E07, E08, E09, E10, E11,
        E12, E13, E14, E15, E16, E17, E18, E19, E20, E21, E22;
  inout S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11,
        S12, S13, S14, S15, S16, S17, S18, S19, S20, S21, S22;
  inout W01, W02, W03, W04, W05, W06, W07, W08, W09, W10, W11,
        W12, W13, W14, W15, W16, W17, W18, W19, W20, W21, W22;

  // pad-ring core-side stub nets
  wire W14_PU, W14_PD, W14_Y;   // clk   (in_s)
  wire W15_PU, W15_PD, W15_Y;   // rst_n (in_c)
  wire W16_PU, W16_PD, W16_Y;   // uart_rx (in_c)
  wire W17_CS, W17_SL, W17_IE, W17_OE, W17_PU, W17_PD, W17_A, W17_PDRV0, W17_PDRV1, W17_Y; // uart_tx
  wire W18_CS, W18_SL, W18_IE, W18_OE, W18_PU, W18_PD, W18_A, W18_PDRV0, W18_PDRV1, W18_Y; // qspi_csn[0]
  wire W19_CS, W19_SL, W19_IE, W19_OE, W19_PU, W19_PD, W19_A, W19_PDRV0, W19_PDRV1, W19_Y; // qspi_csn[1]
  wire W20_CS, W20_SL, W20_IE, W20_OE, W20_PU, W20_PD, W20_A, W20_PDRV0, W20_PDRV1, W20_Y; // qspi_sck
  wire W21_CS, W21_SL, W21_IE, W21_OE, W21_PU, W21_PD, W21_A, W21_PDRV0, W21_PDRV1, W21_Y; // qspi_io[0]
  wire W22_CS, W22_SL, W22_IE, W22_OE, W22_PU, W22_PD, W22_A, W22_PDRV0, W22_PDRV1, W22_Y; // qspi_io[1]
  wire N01_CS, N01_SL, N01_IE, N01_OE, N01_PU, N01_PD, N01_A, N01_PDRV0, N01_PDRV1, N01_Y; // qspi_io[2]
  wire N02_CS, N02_SL, N02_IE, N02_OE, N02_PU, N02_PD, N02_A, N02_PDRV0, N02_PDRV1, N02_Y; // qspi_io[3]

  A09_BV_padring u_padring (
      .N01(N01), .N02(N02), .N03(N03), .N04(N04), .N05(N05), .N06(N06), .N07(N07),
      .N08(N08), .N09(N09), .N10(N10), .N11(N11), .N12(N12), .N13(N13), .N14(N14),
      .N15(N15), .N16(N16), .N17(N17), .N18(N18), .N19(N19), .N20(N20), .N21(N21), .N22(N22),
      .E01(E01), .E02(E02), .E03(E03), .E04(E04), .E05(E05), .E06(E06), .E07(E07),
      .E08(E08), .E09(E09), .E10(E10), .E11(E11), .E12(E12), .E13(E13), .E14(E14),
      .E15(E15), .E16(E16), .E17(E17), .E18(E18), .E19(E19), .E20(E20), .E21(E21), .E22(E22),
      .S01(S01), .S02(S02), .S03(S03), .S04(S04), .S05(S05), .S06(S06), .S07(S07),
      .S08(S08), .S09(S09), .S10(S10), .S11(S11), .S12(S12), .S13(S13), .S14(S14),
      .S15(S15), .S16(S16), .S17(S17), .S18(S18), .S19(S19), .S20(S20), .S21(S21), .S22(S22),
      .W01(W01), .W02(W02), .W03(W03), .W04(W04), .W05(W05), .W06(W06), .W07(W07),
      .W08(W08), .W09(W09), .W10(W10), .W11(W11), .W12(W12), .W13(W13), .W14(W14),
      .W15(W15), .W16(W16), .W17(W17), .W18(W18), .W19(W19), .W20(W20), .W21(W21), .W22(W22),

      .W14_PU(W14_PU), .W14_PD(W14_PD), .W14_Y(W14_Y),
      .W15_PU(W15_PU), .W15_PD(W15_PD), .W15_Y(W15_Y),
      .W16_PU(W16_PU), .W16_PD(W16_PD), .W16_Y(W16_Y),

      .W17_CS(W17_CS), .W17_SL(W17_SL), .W17_IE(W17_IE), .W17_OE(W17_OE), .W17_PU(W17_PU),
      .W17_PD(W17_PD), .W17_A(W17_A), .W17_PDRV0(W17_PDRV0), .W17_PDRV1(W17_PDRV1), .W17_Y(W17_Y),
      .W18_CS(W18_CS), .W18_SL(W18_SL), .W18_IE(W18_IE), .W18_OE(W18_OE), .W18_PU(W18_PU),
      .W18_PD(W18_PD), .W18_A(W18_A), .W18_PDRV0(W18_PDRV0), .W18_PDRV1(W18_PDRV1), .W18_Y(W18_Y),
      .W19_CS(W19_CS), .W19_SL(W19_SL), .W19_IE(W19_IE), .W19_OE(W19_OE), .W19_PU(W19_PU),
      .W19_PD(W19_PD), .W19_A(W19_A), .W19_PDRV0(W19_PDRV0), .W19_PDRV1(W19_PDRV1), .W19_Y(W19_Y),
      .W20_CS(W20_CS), .W20_SL(W20_SL), .W20_IE(W20_IE), .W20_OE(W20_OE), .W20_PU(W20_PU),
      .W20_PD(W20_PD), .W20_A(W20_A), .W20_PDRV0(W20_PDRV0), .W20_PDRV1(W20_PDRV1), .W20_Y(W20_Y),
      .W21_CS(W21_CS), .W21_SL(W21_SL), .W21_IE(W21_IE), .W21_OE(W21_OE), .W21_PU(W21_PU),
      .W21_PD(W21_PD), .W21_A(W21_A), .W21_PDRV0(W21_PDRV0), .W21_PDRV1(W21_PDRV1), .W21_Y(W21_Y),
      .W22_CS(W22_CS), .W22_SL(W22_SL), .W22_IE(W22_IE), .W22_OE(W22_OE), .W22_PU(W22_PU),
      .W22_PD(W22_PD), .W22_A(W22_A), .W22_PDRV0(W22_PDRV0), .W22_PDRV1(W22_PDRV1), .W22_Y(W22_Y),
      .N01_CS(N01_CS), .N01_SL(N01_SL), .N01_IE(N01_IE), .N01_OE(N01_OE), .N01_PU(N01_PU),
      .N01_PD(N01_PD), .N01_A(N01_A), .N01_PDRV0(N01_PDRV0), .N01_PDRV1(N01_PDRV1), .N01_Y(N01_Y),
      .N02_CS(N02_CS), .N02_SL(N02_SL), .N02_IE(N02_IE), .N02_OE(N02_OE), .N02_PU(N02_PU),
      .N02_PD(N02_PD), .N02_A(N02_A), .N02_PDRV0(N02_PDRV0), .N02_PDRV1(N02_PDRV1), .N02_Y(N02_Y)
  );

  A09_BV u_core (
      .VDD(W13),
      .VSS(W12),

      .clk       (W14_Y),
      .clk_PU    (W14_PU),
      .clk_PD    (W14_PD),

      .rst_n     (W15_Y),
      .rst_n_PU  (W15_PU),
      .rst_n_PD  (W15_PD),

      .uart_rx   (W16_Y),
      .uart_rx_PU(W16_PU),
      .uart_rx_PD(W16_PD),

      .uart_tx_IN   (W17_Y),
      .uart_tx_OUT  (W17_A),
      .uart_tx_CS   (W17_CS),
      .uart_tx_SL   (W17_SL),
      .uart_tx_PU   (W17_PU),
      .uart_tx_PD   (W17_PD),
      .uart_tx_OE   (W17_OE),
      .uart_tx_IE   (W17_IE),
      .uart_tx_PDRV0(W17_PDRV0),
      .uart_tx_PDRV1(W17_PDRV1),

      .qspi_csn_IN   ({W19_Y,     W18_Y}),
      .qspi_csn_OUT  ({W19_A,     W18_A}),
      .qspi_csn_CS   ({W19_CS,    W18_CS}),
      .qspi_csn_SL   ({W19_SL,    W18_SL}),
      .qspi_csn_PU   ({W19_PU,    W18_PU}),
      .qspi_csn_PD   ({W19_PD,    W18_PD}),
      .qspi_csn_OE   ({W19_OE,    W18_OE}),
      .qspi_csn_IE   ({W19_IE,    W18_IE}),
      .qspi_csn_PDRV0({W19_PDRV0, W18_PDRV0}),
      .qspi_csn_PDRV1({W19_PDRV1, W18_PDRV1}),

      .qspi_sck_IN   (W20_Y),
      .qspi_sck_OUT  (W20_A),
      .qspi_sck_CS   (W20_CS),
      .qspi_sck_SL   (W20_SL),
      .qspi_sck_PU   (W20_PU),
      .qspi_sck_PD   (W20_PD),
      .qspi_sck_OE   (W20_OE),
      .qspi_sck_IE   (W20_IE),
      .qspi_sck_PDRV0(W20_PDRV0),
      .qspi_sck_PDRV1(W20_PDRV1),

      .qspi_io_IN   ({N02_Y,     N01_Y,     W22_Y,     W21_Y}),
      .qspi_io_OUT  ({N02_A,     N01_A,     W22_A,     W21_A}),
      .qspi_io_CS   ({N02_CS,    N01_CS,    W22_CS,    W21_CS}),
      .qspi_io_SL   ({N02_SL,    N01_SL,    W22_SL,    W21_SL}),
      .qspi_io_PU   ({N02_PU,    N01_PU,    W22_PU,    W21_PU}),
      .qspi_io_PD   ({N02_PD,    N01_PD,    W22_PD,    W21_PD}),
      .qspi_io_OE   ({N02_OE,    N01_OE,    W22_OE,    W21_OE}),
      .qspi_io_IE   ({N02_IE,    N01_IE,    W22_IE,    W21_IE}),
      .qspi_io_PDRV0({N02_PDRV0, N01_PDRV0, W22_PDRV0, W21_PDRV0}),
      .qspi_io_PDRV1({N02_PDRV1, N01_PDRV1, W22_PDRV1, W21_PDRV1})
  );

endmodule
