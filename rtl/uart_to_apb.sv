// UART to APB bridge module
// configurable number of slaves and their address maps using parameters
// Author: Team Crispi - SSCS Chipathon 2026

module uart_to_apb #(
    // UART to APB parameters
    parameter int NUM_DATA_BYTES = 4,  // Number of data bytes to receive from UART
    parameter int NUM_ADDR_BYTES = 1,  // Number of address bytes to receive from UART
    parameter logic [7:0] ACK_BYTE = 8'h55,  // Ack byte to send back to UART (for successful write)
    parameter logic [7:0] ERR_BYTE = 8'hFF,  // Error byte to send back to UART (for invalid write)

    // UART parameters
    parameter int CLOCK_FREQ = 50_000_000,
    parameter int BAUD_RATE  = 921_600,

    // APB parameters
    parameter int DATA_WIDTH = 32,
    parameter int ADDR_WIDTH = 32,
    parameter int NUM_SLAVES = 1,
    parameter logic [ADDR_WIDTH-1:0] SLAVE_BASE[NUM_SLAVES] = '{
        32'h0000_0000
    },  // Base addresses for each slave
    parameter logic [ADDR_WIDTH-1:0] SLAVE_SIZE[NUM_SLAVES] = '{
        32'd32
    }  // Size of each slave address space (MUST be power of 2)
) (
    // Clock and reset
    input logic clk_i,
    input logic rst_ni,

    // UART interface
    input  logic uart_rx_i,
    output logic uart_tx_o,

    // APB master interface
    output logic [ADDR_WIDTH-1:0] paddr_o,
    output logic [DATA_WIDTH-1:0] pwdata_o,
    output logic pwrite_o,
    output logic penable_o,

    output logic [NUM_SLAVES-1:0] psel_o,
    input  logic [DATA_WIDTH-1:0] prdata_i [NUM_SLAVES],
    input  logic [NUM_SLAVES-1:0] pready_i,
    input  logic [NUM_SLAVES-1:0] pslverr_i

);

  // UART BLOCK INSTANCE
  logic tx_start, tx_done, rx_valid, rx_error, uart_busy;
  logic [7:0] tx_data, rx_data;
  uart_simple #(
      .CLOCK_FREQ(CLOCK_FREQ),
      .BAUD_RATE (BAUD_RATE)
  ) uart_inst (
      .clk_i(clk_i),
      .rst_ni(rst_ni),
      .tx_start_i(tx_start),
      .tx_done_o(tx_done),
      .rx_valid_o(rx_valid),
      .rx_error_o(rx_error),
      .uart_busy_o(uart_busy),
      .tx_data_i(tx_data),
      .rx_data_o(rx_data),
      .uart_rx_i(uart_rx_i),
      .uart_tx_o(uart_tx_o)
  );

  // ADDRESS DECODER
  logic [NUM_SLAVES-1:0] psel;
  logic [ADDR_WIDTH-1:0] paddr;
  generate
    for (genvar i = 0; i < NUM_SLAVES; i++) begin : gen_addr_decode
      localparam logic [ADDR_WIDTH-1:0] MASK = ~(SLAVE_SIZE[i] - 1);  // convert size to mask
      assign psel[i] = ((paddr & MASK) == SLAVE_BASE[i]);
    end
  endgenerate
  assign psel_o  = psel;
  assign paddr_o = paddr;

  // READ MUX
  logic [DATA_WIDTH-1:0] active_prdata;
  logic active_pready;
  always_comb begin
    active_prdata = 'd0;
    active_pready = 1'b1;
    for (int i = 0; i < NUM_SLAVES; i++) begin
      if (psel_o[i]) begin
        active_prdata = prdata_i[i];
        active_pready = pready_i[i];
      end
    end
  end

endmodule
