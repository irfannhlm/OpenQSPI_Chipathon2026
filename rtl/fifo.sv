// Pointer based FIFO
// inspired by cc_fifo.sv from pulp-platform (https://github.com/pulp-platform/common_cells/blob/master/src/cc_fifo.sv)
// Author: Team Crispi - SSCS Chipathon 2026

module fifo #(
    parameter int DATA_WIDTH = 32,
    parameter int DEPTH = 16
) (
    // clock and reset
    input logic clk_i,
    input logic rst_ni,

    // FIFO interface
    input logic flush_i,
    input logic push_i,
    input logic pop_i,
    input logic [DATA_WIDTH-1:0] data_i,
    output logic [DATA_WIDTH-1:0] data_o,
    output logic empty_o,
    output logic full_o
);
  localparam int unsigned FifoDepth = (DEPTH > 0) ? DEPTH : 1;
  localparam int unsigned AddrDepth = (DEPTH > 1) ? $clog2(DEPTH) : 1;

  // FIFO memory and pointers
  logic [DATA_WIDTH-1:0][FifoDepth-1:0] mem_n, mem_q;
  logic [AddrDepth-1:0] rptr_n, rptr_q, wrptr_n, wrptr_q;


endmodule
