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
    // UART interface
    logic uart_rx_i;
    logic uart_tx_o;
    uart_to_apb #(
        // UART parameters
        .CLOCK_FREQ(50_000_000),  // 50 MHz
        .BAUD_RATE (921_600)      // 921600 bps
    ) inst_uart_to_apb (
        // Clock and reset
        .clk_i (clk),
        .rst_ni(rst_n),

        // UART interface
        .uart_rx_i(uart_rx_i),
        .uart_tx_o(uart_tx_o),

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
    logic [3:0] qspi_i;
    logic [3:0] qspi_o;
    logic [3:0] qspi_oe;  // output enable for qspi_o
    logic [1:0] qspi_csn_o;
    logic qspi_sck_o;
    apb_qspi #(
        .FIFO_DEPTH(16),
        .CS_NUM(2)
    ) inst_apb_qspi (
        // clock and reset
        .clk_i (clk),
        .rst_ni(rst_n),

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
        .qspi_csn_o(qspi_csn_o),
        .qspi_sck_o(qspi_sck_o),
        .qspi_i(qspi_i),
        .qspi_o(qspi_o),
        .qspi_oe(qspi_oe)  // output enable for qspi_o
    );


    // =========================================================
    // PAD MAPPING (Physical Pin Assignments)
    // =========================================================

    // ---------------------------------------------------------
    // Pad 0: UART RX (Input)
    // ---------------------------------------------------------
    assign uart_rx_i    = bidir_in[0];
    assign bidir_out[0] = 1'b0;        // Drive 0 (ignored)
    assign bidir_oe[0]  = 1'b0;        // Output Enable = 0 (Input Mode)
    assign bidir_ie[0]  = 1'b1;        // Input Enable = 1

    // ---------------------------------------------------------
    // Pad 1: UART TX (Output)
    // ---------------------------------------------------------
    assign bidir_out[1] = uart_tx_o;
    assign bidir_oe[1]  = 1'b1;        // Output Enable = 1 (Output Mode)
    assign bidir_ie[1]  = 1'b0;        // Input Enable = 0

    // ---------------------------------------------------------
    // Pad 2: QSPI SCK (Output)
    // ---------------------------------------------------------
    assign bidir_out[2] = qspi_sck_o;
    assign bidir_oe[2]  = 1'b1;
    assign bidir_ie[2]  = 1'b0;

    // ---------------------------------------------------------
    // Pads 4:3: QSPI CSN[1:0] (Outputs)
    // ---------------------------------------------------------
    assign bidir_out[4:3] = qspi_csn_o[1:0];
    assign bidir_oe[4:3]  = 2'b11;
    assign bidir_ie[4:3]  = 2'b00;

    // ---------------------------------------------------------
    // Pads 8:5: QSPI IO[3:0] (Bidirectional / Tri-State)
    // ---------------------------------------------------------
    assign qspi_i         = bidir_in[8:5];
    assign bidir_out[8:5] = qspi_o[3:0];
    assign bidir_oe[8:5]  = qspi_oe[3:0]; 
    assign bidir_ie[8:5]  = ~qspi_oe[3:0];

    // ---------------------------------------------------------
    // Pads 19:9: Unused Bidir Pads (Tie off safely)
    // ---------------------------------------------------------
    assign bidir_out[NUM_BIDIR_PADS-1:9] = '0;
    assign bidir_oe[NUM_BIDIR_PADS-1:9]  = '0; // Keep outputs disabled
    assign bidir_ie[NUM_BIDIR_PADS-1:9]  = '0; // Keep inputs disabled

    // ---------------------------------------------------------
    // Static Pad Electrical Configurations
    // ---------------------------------------------------------
    assign bidir_cs = '0; // 0 = CMOS input thresholds
    assign bidir_sl = '0; // 0 = Fast slew rate (critical for 50MHz QSPI!)
    assign bidir_pu = '0; // No pull-ups (rely on external PCB pull-ups)
    assign bidir_pd = '0; // No pull-downs
    
    assign input_pu = '0; // Disable pull-ups on pure inputs
    assign input_pd = '0;

    // Keep synthesis from optimising unused inputs away.
    logic _unused;
    assign _unused = &{1'b0, bidir_in, input_in};

endmodule

`default_nettype wire
