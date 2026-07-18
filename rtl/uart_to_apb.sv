// UART to APB bridge module
// strictly half duplex communication with 8N1 protocol (8 data bits, no parity, 1 stop bit)
// has fixed custom protocol with big endian byte order
// configurable number of slaves and their address maps using parameters
// Author: Team Crispi - SSCS Chipathon 2026

module uart_to_apb #(
    // UART to APB protocol parameters
    parameter logic [4:0] NUM_ADDR_BYTES = 5'd1,  // Number of address bytes to receive from UART
    parameter logic [7:0] ACK_BYTE = 8'h55,  // Ack byte to send back to UART (for successful write)
    parameter logic [7:0] ERR_BYTE = 8'hFF,  // Error byte to send back to UART (for invalid write)

    // UART parameters
    parameter int CLOCK_FREQ = 50_000_000,
    parameter int BAUD_RATE  = 921_600,

    // APB parameters
    parameter int NUM_SLAVES = 1,
    parameter logic [(NUM_SLAVES*32)-1:0] SLAVE_BASE = {
      32'h0000_0000
    },  // Base addresses for each slave
    parameter logic [(NUM_SLAVES*32)-1:0] SLAVE_SIZE = {
      32'd64
    }  // Size of each slave address space (MUST be power of 2)
) (
    // Clock and reset
    input logic clk_i,
    input logic rst_ni,

    // UART interface
    input  logic uart_rx_i,
    output logic uart_tx_o,

    // APB master interface
    output logic [31:0] paddr_o,
    output logic [31:0] pwdata_o,
    output logic pwrite_o,
    output logic penable_o,

    output logic [NUM_SLAVES-1:0] psel_o,
    input logic [(NUM_SLAVES*32)-1:0] prdata_i,
    input logic [NUM_SLAVES-1:0] pready_i,
    input logic [NUM_SLAVES-1:0] pslverr_i

);

  // UART BLOCK INSTANCE
  logic tx_start, tx_done, rx_valid, rx_error, uart_busy, uart_en;
  logic [7:0] tx_data, rx_data;
  uart_simple #(
      .CLOCK_FREQ(CLOCK_FREQ),
      .BAUD_RATE (BAUD_RATE)
  ) uart_inst (
      .clk_i(clk_i),
      .rst_ni(rst_ni),
      .uart_en_i(uart_en),
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


  // APB MASTER CONTROL LOGIC

  // address decoder
  logic [NUM_SLAVES-1:0] psel;
  logic [31:0] paddr;
  generate
    for (genvar i = 0; i < NUM_SLAVES; i++) begin : gen_addr_decode
      localparam logic [31:0] BASE = SLAVE_BASE[i*32+:32];
      localparam logic [31:0] SIZE = SLAVE_SIZE[i*32+:32];
      localparam logic [31:0] MASK = ~(SIZE - 1);  // convert size to mask
      assign psel[i] = ((paddr & MASK) == BASE);
    end
  endgenerate
  assign psel_o  = psel;
  assign paddr_o = paddr;

  // read mux
  logic [31:0] rdata;
  logic pready;
  always_comb begin
    rdata  = 'd0;
    pready = 1'b1;
    for (int i = 0; i < NUM_SLAVES; i++) begin
      if (psel_o[i]) begin
        rdata  = prdata_i[i*32+:32];
        pready = pready_i[i];
      end
    end
  end

  // apb control register
  logic apb_handshake, apb_start, apb_error;
  assign apb_handshake = (psel && penable_o && pready);
  always_ff @(posedge clk_i, negedge rst_ni) begin : apb_control_reg
    if (!rst_ni) begin
      penable_o <= 1'b0;
      apb_error <= 1'b0;
    end else begin
      // penable control
      if (apb_start) begin
        penable_o <= 1'b1;
      end else if (apb_handshake) begin
        penable_o <= 1'b0;
      end

      // apb error flag
      if (apb_handshake && pslverr_i) begin
        apb_error <= 1'b1;
      end else if (apb_start) begin
        apb_error <= 1'b0;
      end

    end
  end

  // uart byte counter
  logic [4:0] byte_cnt;
  logic byte_cnt_rst;
  wire uart_done = (rx_valid || tx_done);
  always_ff @(posedge clk_i, negedge rst_ni) begin : byte_counter
    if (!rst_ni) begin
      byte_cnt <= 'd0;
    end else if (byte_cnt_rst) begin
      byte_cnt <= 'd0;
    end else if (uart_done) begin
      byte_cnt <= byte_cnt + 1;
    end
  end

  // mode register
  logic apb_mode;  // 0: APB read, 1: APB write
  logic apb_done, apb_rst;
  always_ff @(posedge clk_i, negedge rst_ni) begin : mode_state_reg
    if (!rst_ni) begin
      apb_mode <= 1'b0;
      apb_done <= 1'b0;
    end else if (apb_rst) begin
      apb_mode <= 1'b0;
      apb_done <= 1'b0;
    end else if (apb_handshake) begin
      apb_done <= 1'b1;
    end else if (rx_valid && (byte_cnt == 5'd0)) begin
      apb_mode <= rx_data[7];  // set mode based on R/W bit
    end
  end
  assign pwrite_o = apb_mode;  // write when apb_mode is high

  // address register
  logic [31:0] addr_reg;
  logic addr_rst, addr_en;
  always_ff @(posedge clk_i, negedge rst_ni) begin : addr_reg_block
    if (!rst_ni) begin
      addr_reg <= 'd0;
    end else if (addr_rst) begin
      addr_reg <= 'd0;  // reset address register after final byte
    end else if (rx_valid && addr_en) begin
      // shift in address bytes (high byte first)
      if (byte_cnt == 5'd0) begin
        addr_reg <= {addr_reg[24:0], rx_data[6:0]};  // ignore MSB (R/W bit)
      end else begin
        addr_reg <= {addr_reg[23:0], rx_data};
      end
    end
  end
  assign paddr = addr_reg;

  // wdata register
  logic [31:0] wdata_reg;
  logic wdata_rst, wdata_en;
  always_ff @(posedge clk_i, negedge rst_ni) begin : wdata_reg_block
    if (!rst_ni) begin
      wdata_reg <= 'd0;
    end else if (wdata_rst) begin
      wdata_reg <= 'd0;
    end else if (rx_valid && wdata_en) begin
      wdata_reg <= {wdata_reg[23:0], rx_data};  // shift in data bytes (high byte first)
    end
  end
  assign pwdata_o = wdata_reg;

  // rdata register
  logic [31:0] rdata_reg;
  logic [7:0] rdata_byte;
  logic rdata_en;
  always_ff @(posedge clk_i, negedge rst_ni) begin : rdata_reg_block
    if (!rst_ni) begin
      rdata_reg <= 'd0;
    end else if (apb_handshake && !pslverr_i) begin
      rdata_reg <= rdata;  // latch read data after succesful APB read
    end else if (tx_done && rdata_en) begin
      rdata_reg <= {rdata_reg[23:0], 8'd0};  // shift out data bytes (high byte first)
    end
  end
  assign rdata_byte = rdata_reg[31:24];  // send high byte first to UART

  // UART control signals
  always_comb begin : uart_control_comb
    // TX data mux
    if (apb_handshake) begin
      if (pslverr_i) begin
        tx_data = ERR_BYTE;  // send error byte on APB error
      end else begin
        tx_data = ACK_BYTE;  // send ack byte on successful transaction
      end
    end else begin
      tx_data = rdata_byte;  // default to APB read data byte
    end
  end

  // MAIN CONTROL FSM
  typedef enum logic [1:0] {
    ADDR,
    DATA,
    ACK
  } fsm_state_t;
  fsm_state_t fsm_cstate, fsm_nstate;

  always_ff @(posedge clk_i, negedge rst_ni) begin : fsm_reg
    if (!rst_ni) begin
      fsm_cstate <= ADDR;
    end else begin
      fsm_cstate <= fsm_nstate;
    end
  end

  always_comb begin : simplify_assigns
    addr_rst  = byte_cnt_rst;
    wdata_rst = byte_cnt_rst;
    apb_rst   = byte_cnt_rst;
  end
  always_comb begin : fsm_comb
    byte_cnt_rst = 1'b0;

    addr_en = 1'b0;
    wdata_en = 1'b0;
    rdata_en = 1'b0;

    apb_start = 1'b0;
    tx_start = 1'b0;

    uart_en = 1'b1;  // enable UART by default

    fsm_nstate = fsm_cstate;
    case (fsm_cstate)

      ADDR: begin  // receive address bytes
        addr_en = 1'b1;
        if (rx_valid && (byte_cnt == NUM_ADDR_BYTES - 5'd1)) begin
          if ((rx_data[7] && byte_cnt == 5'd0) || apb_mode) begin
            fsm_nstate = DATA;  // write operation
          end else begin
            fsm_nstate = ACK;  // read operation
          end
        end
      end

      DATA: begin  // receive wdata or send rdata bytes
        if (apb_mode) begin
          wdata_en = 1'b1;
          if (rx_valid && (byte_cnt == NUM_ADDR_BYTES + 5'd3)) begin
            fsm_nstate = ACK;  // go to ACK state after receiving all wdata bytes
          end
        end else begin
          rdata_en = 1'b1;  // start sending rdata bytes after successful APB read
          tx_start = !uart_busy;  // start UART transmission of rdata bytes
          if (tx_done && (byte_cnt == NUM_ADDR_BYTES + 5'd3 + 5'd1)) begin
            tx_start = 1'b0;  // stop UART transmission after sending all rdata bytes
            byte_cnt_rst = 1'b1;  // reset byte counter
            fsm_nstate = ADDR;  // reset back to ADDR state
          end
        end
      end

      ACK: begin  // send ACK byte
        if (!apb_done) begin
          uart_en = (apb_handshake) ? 1'b1 : 1'b0;  // disable UART while waiting for APB
          apb_start = (apb_handshake) ? 1'b0 : 1'b1;  // start APB transaction if not already started
          tx_start = (apb_handshake) ? 1'b1 : 1'b0;  // start UART transmission of ACK byte at handshake
        end else begin
          if (tx_done) begin
            if (apb_mode) begin  // write mode
              byte_cnt_rst = 1'b1;
              fsm_nstate   = ADDR;  // go back to ADDR state after ACK
            end else begin  // read mode
              if (apb_error) begin
                byte_cnt_rst = 1'b1;
                fsm_nstate   = ADDR;  // reset back to ADDR state after error
              end else begin
                fsm_nstate = DATA;  // continue to DATA state if success
              end
            end
          end
        end
      end

      default: begin
        fsm_nstate = ADDR;
      end
    endcase
  end


endmodule
