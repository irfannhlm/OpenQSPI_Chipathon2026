// SPDX-FileCopyrightText: 2026 Chipathon 2026 workshop
// SPDX-License-Identifier: Apache-2.0
//
// Minimal chip_core for the Chipathon 2026 workshop padring slot.
// The emphasis of this slot is the padring itself (60 analog + 20
// bidir + 4/4 power + clk/rst_n); the core is intentionally trivial:
// a free-running counter whose state drives the 20 bidir pads. The
// 60 analog pads are routed straight through to analog[] and stay
// unconnected at the core level (the intent is that a downstream
// design wires them to custom analog IP later).

`default_nettype none

`include "pad_map.svh"

module chip_core #(
    parameter NUM_INPUT_PADS,
    parameter NUM_BIDIR_PADS,
    parameter NUM_ANALOG_PADS
    )(
    `ifdef USE_POWER_PINS
    inout  wire VDD,
    inout  wire VSS,
    `endif

    input  wire clk,       // clock
    input  wire rst_n,     // reset (active low)

    input  wire [NUM_INPUT_PADS-1:0] input_in,   // Input value
    output wire [NUM_INPUT_PADS-1:0] input_pu,   // Pull-up
    output wire [NUM_INPUT_PADS-1:0] input_pd,   // Pull-down

    input  wire [NUM_BIDIR_PADS-1:0] bidir_in,   // Input value
    output wire [NUM_BIDIR_PADS-1:0] bidir_out,  // Output value
    output wire [NUM_BIDIR_PADS-1:0] bidir_oe,   // Output enable
    output wire [NUM_BIDIR_PADS-1:0] bidir_cs,   // Input type (0=CMOS, 1=Schmitt)
    output wire [NUM_BIDIR_PADS-1:0] bidir_sl,   // Slew rate (0=fast, 1=slow)
    output wire [NUM_BIDIR_PADS-1:0] bidir_ie,   // Input enable
    output wire [NUM_BIDIR_PADS-1:0] bidir_pu,   // Pull-up
    output wire [NUM_BIDIR_PADS-1:0] bidir_pd,   // Pull-down

    inout  wire [NUM_ANALOG_PADS-1:0] analog    // Analog
);

    wire uart_rx_i, uart_tx_o;
    wire [1:0] qspi_csn_o;
    wire qspi_sck_o;
    wire [3:0] qspi_i, qspi_o, qspi_oe;
    a09_chipathon26_top #() a09_inst (
    `ifdef USE_POWER_PINS
        .VDD(VDD),
        .VSS(VSS),
    `endif

        // Clock and reset
        .clk_i(clk),
        .rst_ni(rst_n),

        // UART interface
        .uart_rx_i(uart_rx_i),
        .uart_tx_o(uart_tx_o),

        // QSPI interface
        .qspi_csn_o(qspi_csn_o),
        .qspi_sck_o(qspi_sck_o),
        .qspi_i(qspi_i),
        .qspi_o(qspi_o),
        .qspi_oe(qspi_oe)  // output enable for qspi_o
    );


    // =========================================================
    // PAD MAPPING (Use EAST PADs for UART and QSPI)
    // =========================================================
    generate
        for (genvar i = 0; i < NUM_BIDIR_PADS; i++) begin : gen_pad_defaults
            if (i == `PAD_UART_RX) begin
                // Pad PAD_UART_RX: UART RX (Input)
                assign bidir_out[i] = 1'b0;
                assign bidir_oe[i]  = 1'b0;
                assign bidir_ie[i]  = 1'b1;
                assign uart_rx_i = bidir_in[i];
                assign bidir_pu[i]  = 1'b0;
                assign bidir_pd[i]  = 1'b0;
            end else if (i == `PAD_UART_TX) begin
                // Pad PAD_UART_TX: UART TX (Output)
                assign bidir_out[i] = uart_tx_o;
                assign bidir_oe[i]  = 1'b1;
                assign bidir_ie[i]  = 1'b0;
                assign bidir_pu[i]  = 1'b0;
                assign bidir_pd[i]  = 1'b0;
            end else if (i == `PAD_QSPI_SCK) begin
                // Pad PAD_QSPI_SCK: QSPI SCK (Output)
                assign bidir_out[i] = qspi_sck_o;
                assign bidir_oe[i]  = 1'b1;
                assign bidir_ie[i]  = 1'b0;
                assign bidir_pu[i]  = 1'b0;
                assign bidir_pd[i]  = 1'b0;
            end else if (i == `PAD_QSPI_CSN0 || i == `PAD_QSPI_CSN1) begin
                // Pads PAD_QSPI_CSN0 and PAD_QSPI_CSN1: QSPI CSN[1:0] (Outputs)
                assign bidir_out[i] = qspi_csn_o[i - `PAD_QSPI_CSN0];
                assign bidir_oe[i]  = 1'b1;
                assign bidir_ie[i]  = 1'b0;
                assign bidir_pu[i]  = 1'b0;
                assign bidir_pd[i]  = 1'b0;
            end else if (i >= `PAD_QSPI_IO0 && i <= `PAD_QSPI_IO3) begin
                // Pads PAD_QSPI_IO3:PAD_QSPI_IO0: QSPI IO[3:0] (Bidirectional)
                assign bidir_out[i] = qspi_o[i - `PAD_QSPI_IO0];
                assign bidir_oe[i]  = qspi_oe[i - `PAD_QSPI_IO0];
                assign bidir_ie[i]  = ~qspi_oe[i - `PAD_QSPI_IO0];
                assign qspi_i[i - `PAD_QSPI_IO0] = bidir_in[i];
                assign bidir_pu[i]  = 1'b1; // enable pullup (simulation only)
                assign bidir_pd[i]  = 1'b0;
            end else begin
                // Unused pads -> Grounded and Disabled
                assign bidir_out[i] = 1'b0;
                assign bidir_oe[i]  = 1'b0;
                assign bidir_ie[i]  = 1'b0;
                assign bidir_pu[i]  = 1'b0;
                assign bidir_pd[i]  = 1'b0;
            end
        end
    endgenerate

    // ---------------------------------------------------------
    // Static Pad Electrical Configurations
    // ---------------------------------------------------------
    assign bidir_cs = '0; // 0 = CMOS input thresholds
    assign bidir_sl = '0; // 0 = Fast slew rate (critical for 50MHz QSPI!)
    assign input_pu = '0; // Disable pull-ups on pure inputs
    assign input_pd = '0;

    // Keep synthesis from optimising unused inputs away.
    logic _unused;
    assign _unused = &{1'b0, bidir_in, input_in};

endmodule

`default_nettype wire
