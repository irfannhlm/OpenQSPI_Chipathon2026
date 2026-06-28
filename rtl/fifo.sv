// Pointer based FIFO
// inspired by fifo_v3.sv from pulp-platform (https://github.com/pulp-platform/common_cells/blob/master/src/fifo_v3.sv)
// Author: Team Crispi - SSCS Chipathon 2026

module fifo #(
    parameter int DEPTH = 16
) (
    // clock and reset
    input logic clk_i,
    input logic rst_ni,

    // FIFO interface
    input logic flush_i,
    input logic push_i,
    input logic pop_i,
    input logic [31:0] data_i,
    output logic [31:0] data_o,
    output logic empty_o,
    output logic full_o
);
  localparam int unsigned FifoDepth = (DEPTH > 0) ? DEPTH : 1;
  localparam int unsigned AddrDepth = (DEPTH > 1) ? $clog2(DEPTH) : 1;

  // FIFO memory and pointers
  logic [FifoDepth-1:0] mem_n, mem_q;
  logic [AddrDepth-1:0] rptr_n, rptr_q, wrptr_n, wrptr_q;


endmodule
