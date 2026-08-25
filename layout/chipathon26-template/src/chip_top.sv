// SPDX-License-Identifier: Apache-2.0
//
// chip_top for SSCS Chipathon 2026 - Team A09 (variant BV)
//
// GENERATED FILE - do not edit by hand.
//   source: project_defs/BV/A09_BV_interface.yaml
//   script: scripts/gen_chip_top.py
//   spec:   7398a4da36e4d6ad9f9b76c06813b073c9c0ed2f
//
// Block origin ['350', '1475'] um, size ['550', '1110'] um, 13 user pins -> 91 core-side connections.

`default_nettype none

module chip_top (
    // Physical bond pads
    inout wire N01,
    inout wire N02,
    inout wire N03,
    inout wire N04,
    inout wire N05,
    inout wire N06,
    inout wire N07,
    inout wire N08,
    inout wire N09,
    inout wire N10,
    inout wire N11,
    inout wire N12,
    inout wire N13,
    inout wire N14,
    inout wire N15,
    inout wire N16,
    inout wire N17,
    inout wire N18,
    inout wire N19,
    inout wire N20,
    inout wire N21,
    inout wire N22,
    inout wire E01,
    inout wire E02,
    inout wire E03,
    inout wire E04,
    inout wire E05,
    inout wire E06,
    inout wire E07,
    inout wire E08,
    inout wire E09,
    inout wire E10,
    inout wire E11,
    inout wire E12,
    inout wire E13,
    inout wire E14,
    inout wire E15,
    inout wire E16,
    inout wire E17,
    inout wire E18,
    inout wire E19,
    inout wire E20,
    inout wire E21,
    inout wire E22,
    inout wire S01,
    inout wire S02,
    inout wire S03,
    inout wire S04,
    inout wire S05,
    inout wire S06,
    inout wire S07,
    inout wire S08,
    inout wire S09,
    inout wire S10,
    inout wire S11,
    inout wire S12,
    inout wire S13,
    inout wire S14,
    inout wire S15,
    inout wire S16,
    inout wire S17,
    inout wire S18,
    inout wire S19,
    inout wire S20,
    inout wire S21,
    inout wire S22,
    inout wire W01,
    inout wire W02,
    inout wire W03,
    inout wire W04,
    inout wire W05,
    inout wire W06,
    inout wire W07,
    inout wire W08,
    inout wire W09,
    inout wire W10,
    inout wire W11,
    inout wire W12,
    inout wire W13,
    inout wire W14,
    inout wire W15,
    inout wire W16,
    inout wire W17,
    inout wire W18,
    inout wire W19,
    inout wire W20,
    inout wire W21,
    inout wire W22
);

    // ---- padring core-side nets ----
    wire N01_A;
    wire N01_CS;
    wire N01_IE;
    wire N01_OE;
    wire N01_PD;
    wire N01_PDRV0;
    wire N01_PDRV1;
    wire N01_PU;
    wire N01_SL;
    wire N01_Y;
    wire N02_A;
    wire N02_CS;
    wire N02_IE;
    wire N02_OE;
    wire N02_PD;
    wire N02_PDRV0;
    wire N02_PDRV1;
    wire N02_PU;
    wire N02_SL;
    wire N02_Y;
    wire W14_PD;
    wire W14_PU;
    wire W14_Y;
    wire W15_PD;
    wire W15_PU;
    wire W15_Y;
    wire W16_PD;
    wire W16_PU;
    wire W16_Y;
    wire W17_A;
    wire W17_CS;
    wire W17_IE;
    wire W17_OE;
    wire W17_PD;
    wire W17_PDRV0;
    wire W17_PDRV1;
    wire W17_PU;
    wire W17_SL;
    wire W17_Y;
    wire W18_A;
    wire W18_CS;
    wire W18_IE;
    wire W18_OE;
    wire W18_PD;
    wire W18_PDRV0;
    wire W18_PDRV1;
    wire W18_PU;
    wire W18_SL;
    wire W18_Y;
    wire W19_A;
    wire W19_CS;
    wire W19_IE;
    wire W19_OE;
    wire W19_PD;
    wire W19_PDRV0;
    wire W19_PDRV1;
    wire W19_PU;
    wire W19_SL;
    wire W19_Y;
    wire W20_A;
    wire W20_CS;
    wire W20_IE;
    wire W20_OE;
    wire W20_PD;
    wire W20_PDRV0;
    wire W20_PDRV1;
    wire W20_PU;
    wire W20_SL;
    wire W20_Y;
    wire W21_A;
    wire W21_CS;
    wire W21_IE;
    wire W21_OE;
    wire W21_PD;
    wire W21_PDRV0;
    wire W21_PDRV1;
    wire W21_PU;
    wire W21_SL;
    wire W21_Y;
    wire W22_A;
    wire W22_CS;
    wire W22_IE;
    wire W22_OE;
    wire W22_PD;
    wire W22_PDRV0;
    wire W22_PDRV1;
    wire W22_PU;
    wire W22_SL;
    wire W22_Y;

    // ---- padring (A09_BV_padring) ----
    A09_BV_padring u_padring (
        .N01(N01),
        .N02(N02),
        .N03(N03),
        .N04(N04),
        .N05(N05),
        .N06(N06),
        .N07(N07),
        .N08(N08),
        .N09(N09),
        .N10(N10),
        .N11(N11),
        .N12(N12),
        .N13(N13),
        .N14(N14),
        .N15(N15),
        .N16(N16),
        .N17(N17),
        .N18(N18),
        .N19(N19),
        .N20(N20),
        .N21(N21),
        .N22(N22),
        .E01(E01),
        .E02(E02),
        .E03(E03),
        .E04(E04),
        .E05(E05),
        .E06(E06),
        .E07(E07),
        .E08(E08),
        .E09(E09),
        .E10(E10),
        .E11(E11),
        .E12(E12),
        .E13(E13),
        .E14(E14),
        .E15(E15),
        .E16(E16),
        .E17(E17),
        .E18(E18),
        .E19(E19),
        .E20(E20),
        .E21(E21),
        .E22(E22),
        .S01(S01),
        .S02(S02),
        .S03(S03),
        .S04(S04),
        .S05(S05),
        .S06(S06),
        .S07(S07),
        .S08(S08),
        .S09(S09),
        .S10(S10),
        .S11(S11),
        .S12(S12),
        .S13(S13),
        .S14(S14),
        .S15(S15),
        .S16(S16),
        .S17(S17),
        .S18(S18),
        .S19(S19),
        .S20(S20),
        .S21(S21),
        .S22(S22),
        .W01(W01),
        .W02(W02),
        .W03(W03),
        .W04(W04),
        .W05(W05),
        .W06(W06),
        .W07(W07),
        .W08(W08),
        .W09(W09),
        .W10(W10),
        .W11(W11),
        .W12(W12),
        .W13(W13),
        .W14(W14),
        .W15(W15),
        .W16(W16),
        .W17(W17),
        .W18(W18),
        .W19(W19),
        .W20(W20),
        .W21(W21),
        .W22(W22),
        .N01_A(N01_A),
        .N01_CS(N01_CS),
        .N01_IE(N01_IE),
        .N01_OE(N01_OE),
        .N01_PD(N01_PD),
        .N01_PDRV0(N01_PDRV0),
        .N01_PDRV1(N01_PDRV1),
        .N01_PU(N01_PU),
        .N01_SL(N01_SL),
        .N01_Y(N01_Y),
        .N02_A(N02_A),
        .N02_CS(N02_CS),
        .N02_IE(N02_IE),
        .N02_OE(N02_OE),
        .N02_PD(N02_PD),
        .N02_PDRV0(N02_PDRV0),
        .N02_PDRV1(N02_PDRV1),
        .N02_PU(N02_PU),
        .N02_SL(N02_SL),
        .N02_Y(N02_Y),
        .W14_PD(W14_PD),
        .W14_PU(W14_PU),
        .W14_Y(W14_Y),
        .W15_PD(W15_PD),
        .W15_PU(W15_PU),
        .W15_Y(W15_Y),
        .W16_PD(W16_PD),
        .W16_PU(W16_PU),
        .W16_Y(W16_Y),
        .W17_A(W17_A),
        .W17_CS(W17_CS),
        .W17_IE(W17_IE),
        .W17_OE(W17_OE),
        .W17_PD(W17_PD),
        .W17_PDRV0(W17_PDRV0),
        .W17_PDRV1(W17_PDRV1),
        .W17_PU(W17_PU),
        .W17_SL(W17_SL),
        .W17_Y(W17_Y),
        .W18_A(W18_A),
        .W18_CS(W18_CS),
        .W18_IE(W18_IE),
        .W18_OE(W18_OE),
        .W18_PD(W18_PD),
        .W18_PDRV0(W18_PDRV0),
        .W18_PDRV1(W18_PDRV1),
        .W18_PU(W18_PU),
        .W18_SL(W18_SL),
        .W18_Y(W18_Y),
        .W19_A(W19_A),
        .W19_CS(W19_CS),
        .W19_IE(W19_IE),
        .W19_OE(W19_OE),
        .W19_PD(W19_PD),
        .W19_PDRV0(W19_PDRV0),
        .W19_PDRV1(W19_PDRV1),
        .W19_PU(W19_PU),
        .W19_SL(W19_SL),
        .W19_Y(W19_Y),
        .W20_A(W20_A),
        .W20_CS(W20_CS),
        .W20_IE(W20_IE),
        .W20_OE(W20_OE),
        .W20_PD(W20_PD),
        .W20_PDRV0(W20_PDRV0),
        .W20_PDRV1(W20_PDRV1),
        .W20_PU(W20_PU),
        .W20_SL(W20_SL),
        .W20_Y(W20_Y),
        .W21_A(W21_A),
        .W21_CS(W21_CS),
        .W21_IE(W21_IE),
        .W21_OE(W21_OE),
        .W21_PD(W21_PD),
        .W21_PDRV0(W21_PDRV0),
        .W21_PDRV1(W21_PDRV1),
        .W21_PU(W21_PU),
        .W21_SL(W21_SL),
        .W21_Y(W21_Y),
        .W22_A(W22_A),
        .W22_CS(W22_CS),
        .W22_IE(W22_IE),
        .W22_OE(W22_OE),
        .W22_PD(W22_PD),
        .W22_PDRV0(W22_PDRV0),
        .W22_PDRV1(W22_PDRV1),
        .W22_PU(W22_PU),
        .W22_SL(W22_SL),
        .W22_Y(W22_Y)
    );

    // ---- user macro (a09_chipathon26_top) ----
    a09_chipathon26_top u_core (
    `ifdef USE_POWER_PINS
        .VDD(W13),
        .VSS(W12),
    `endif
        .clk(W14_Y),
        .clk_PD(W14_PD),
        .clk_PU(W14_PU),
        .qspi_csn_CS({W19_CS, W18_CS}),
        .qspi_csn_IE({W19_IE, W18_IE}),
        .qspi_csn_IN({W19_Y, W18_Y}),
        .qspi_csn_OE({W19_OE, W18_OE}),
        .qspi_csn_OUT({W19_A, W18_A}),
        .qspi_csn_PD({W19_PD, W18_PD}),
        .qspi_csn_PDRV0({W19_PDRV0, W18_PDRV0}),
        .qspi_csn_PDRV1({W19_PDRV1, W18_PDRV1}),
        .qspi_csn_PU({W19_PU, W18_PU}),
        .qspi_csn_SL({W19_SL, W18_SL}),
        .qspi_io_CS({N02_CS, N01_CS, W22_CS, W21_CS}),
        .qspi_io_IE({N02_IE, N01_IE, W22_IE, W21_IE}),
        .qspi_io_IN({N02_Y, N01_Y, W22_Y, W21_Y}),
        .qspi_io_OE({N02_OE, N01_OE, W22_OE, W21_OE}),
        .qspi_io_OUT({N02_A, N01_A, W22_A, W21_A}),
        .qspi_io_PD({N02_PD, N01_PD, W22_PD, W21_PD}),
        .qspi_io_PDRV0({N02_PDRV0, N01_PDRV0, W22_PDRV0, W21_PDRV0}),
        .qspi_io_PDRV1({N02_PDRV1, N01_PDRV1, W22_PDRV1, W21_PDRV1}),
        .qspi_io_PU({N02_PU, N01_PU, W22_PU, W21_PU}),
        .qspi_io_SL({N02_SL, N01_SL, W22_SL, W21_SL}),
        .qspi_sck_CS(W20_CS),
        .qspi_sck_IE(W20_IE),
        .qspi_sck_IN(W20_Y),
        .qspi_sck_OE(W20_OE),
        .qspi_sck_OUT(W20_A),
        .qspi_sck_PD(W20_PD),
        .qspi_sck_PDRV0(W20_PDRV0),
        .qspi_sck_PDRV1(W20_PDRV1),
        .qspi_sck_PU(W20_PU),
        .qspi_sck_SL(W20_SL),
        .rst_n(W15_Y),
        .rst_n_PD(W15_PD),
        .rst_n_PU(W15_PU),
        .uart_rx(W16_Y),
        .uart_rx_PD(W16_PD),
        .uart_rx_PU(W16_PU),
        .uart_tx_CS(W17_CS),
        .uart_tx_IE(W17_IE),
        .uart_tx_IN(W17_Y),
        .uart_tx_OE(W17_OE),
        .uart_tx_OUT(W17_A),
        .uart_tx_PD(W17_PD),
        .uart_tx_PDRV0(W17_PDRV0),
        .uart_tx_PDRV1(W17_PDRV1),
        .uart_tx_PU(W17_PU),
        .uart_tx_SL(W17_SL)
    );

endmodule

`default_nettype wire