// Pointer based FIFO
// inspired by cc_fifo.sv from pulp-platform (https://github.com/pulp-platform/common_cells/blob/master/src/cc_fifo.sv)
// supports simultaneous push and pop operations, with flush and reset functionality
// supports arbitrary depth (not only powers of 2)
// Author: Team Crispi - SSCS Chipathon 2026

module fifo #(
    parameter int DATA_WIDTH = 32,
    parameter int DEPTH = 16
) (
    // clock and reset
    input logic clk_i,  
    input logic rst_ni,  // Reset pointers, flags, and data. Active Low 
    input logic flush_i, // Only reset internal pointers

    // FIFO Interface Write
    input logic [DATA_WIDTH-1:0] data_i,  // Data to be written
    input logic push_i,                   // Write enable
    output logic full_o,                  // FIFO Full Flag

    // FIFO Interface Read
    output logic [DATA_WIDTH-1:0] data_o, // Data to be read
    input logic pop_i,                    // Read enable
    output logic empty_o                  // FIFO Empty Flag 
);

  localparam int unsigned FifoDepth = (DEPTH > 0) ? DEPTH : 1;
  localparam int unsigned AddrDepth = (DEPTH > 1) ? $clog2(DEPTH) : 1;

  // FIFO memory and pointers
  logic [FifoDepth-1:0][DATA_WIDTH-1:0] mem_n, mem_q; // Next and current memory state
  logic [AddrDepth-1:0] rptr_n, rptr_q, wrptr_n, wrptr_q; // Next and current read/write pointers
  logic [AddrDepth:0] count_n, count_q;   // Next and current count

  // FIFO full and empty flags
  assign full_o = (count_q == FifoDepth);
  assign empty_o = (count_q == 0);

  // Output assignment
  assign data_o = mem_q[rptr_q];

  // Next state logic
  always_comb begin
    // Default next state values
    mem_n = mem_q;
    rptr_n = rptr_q;
    wrptr_n = wrptr_q;
    count_n = count_q;

    // Write operation
    if (push_i && !full_o) begin
      mem_n[wrptr_q] = data_i;
      // Wrap around logic
      if (wrptr_q == FifoDepth - 1) begin
        wrptr_n = 0;
      end else begin
        wrptr_n = wrptr_q + 1;
      end
    end

    // Read operation
    else if (pop_i && !empty_o) begin
      // Output assignment is already handled by data_o

      // Wrap around logic
      if (rptr_q == FifoDepth - 1) begin
        rptr_n = 0;
      end
      else begin
        rptr_n = rptr_q + 1;
      end
    end

    // Update count
    if (push_i && !full_o && pop_i && !empty_o) begin
      // Both push and pop, count remains the same
      count_n = count_q;
    end
    else if (push_i && !full_o) begin
      count_n = count_q + 1;
    end
    else if (pop_i && !empty_o) begin
      count_n = count_q - 1;
    end
  end

  // Sequential logic for state updates
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      // Hard reset: clear everything including memory
      mem_q <= '0;
      rptr_q <= '0;
      wrptr_q <= '0;
      count_q <= '0;
    end else if (flush_i) begin
       // Soft flush: clear pointers and count, but leave memory contents as-is to save power
      rptr_q <= '0;
      wrptr_q <= '0;
      count_q <= '0;
    end else begin
      // Normal operation: update current state with next state
      mem_q <= mem_n;
      rptr_q <= rptr_n;
      wrptr_q <= wrptr_n;
      count_q <= count_n;
    end
  end

endmodule