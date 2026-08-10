// Chip Top Testbench wrapper for QSPI test with official flash models

`include "pad_map.svh"
`include "slot_defines.svh"

module chip_top_tb (
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
  wire [ `NUM_INPUT_PADS-1:0] input_PAD;
  wire [ `NUM_BIDIR_PADS-1:0] bidir_PAD;
  wire [`NUM_ANALOG_PADS-1:0] analog_PAD;
  chip_top #(
`ifndef GL_SIM
      // Power/ground pads for core and I/O
      .NUM_DVDD_PADS(`NUM_DVDD_PADS),
      .NUM_DVSS_PADS(`NUM_DVSS_PADS),

      // Signal pads
      .NUM_INPUT_PADS (`NUM_INPUT_PADS),
      .NUM_BIDIR_PADS (`NUM_BIDIR_PADS),
      .NUM_ANALOG_PADS(`NUM_ANALOG_PADS)
`endif
  ) i_chip_top (
`ifdef USE_POWER_PINS
      .VDD(VDD),
      .VSS(VSS),
`endif

      .clk_PAD  (clk_i),
      .rst_n_PAD(rst_ni),

      .input_PAD(input_PAD),
      .bidir_PAD(bidir_PAD),

      .analog_PAD(analog_PAD)
  );

  // MEMORY VERILOG MODELS
  MX25L51245G u_flash1 (
      .SCLK(bidir_PAD[`PAD_QSPI_SCK]),
      .CS(bidir_PAD[`PAD_QSPI_CSN0]),
      .SI(bidir_PAD[`PAD_QSPI_IO0]),
      .SO(bidir_PAD[`PAD_QSPI_IO1]),
      .WP(bidir_PAD[`PAD_QSPI_IO2]),
      .RESET(rst_ni),
      .SIO3(bidir_PAD[`PAD_QSPI_IO3])
  );
  //   23LC1024 (Microchip)
  M23LC1024 u_flash2 (
      .SI_SIO0(bidir_PAD[`PAD_QSPI_IO0]),
      .SO_SIO1(bidir_PAD[`PAD_QSPI_IO1]),
      .SCK(bidir_PAD[`PAD_QSPI_SCK]),
      .CS_N(bidir_PAD[`PAD_QSPI_CSN1]),
      .SIO2(bidir_PAD[`PAD_QSPI_IO2]),
      .HOLD_N_SIO3(bidir_PAD[`PAD_QSPI_IO3]),
      .RESET(rst_ni)
  );

  // assign bidir_PAD[`PAD_UART_RX] = uart_rx_i;
  assign input_PAD[`PAD_UART_RX] = uart_rx_i;
  assign uart_tx_o = bidir_PAD[`PAD_UART_TX];

`ifdef SDF_ANNOTATE
  initial begin
    #1 $sdf_annotate(`SDF_FILE0, i_chip_top);
  end
`endif
endmodule
