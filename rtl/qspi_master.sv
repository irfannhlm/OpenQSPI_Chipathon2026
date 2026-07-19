// Fully configurable 32-bit QSPI master module
// Supports single, dual and quad modes for command, address (3 or 4 bytes) and data phases
// Supports DDR and XIP with configurable prescaler (minimum 2)
// Author: Team Crispi - SSCS Chipathon 2026

module qspi_master #(
    parameter int CS_NUM = 3  // number of chip selects
) (
    // Clock and reset
    input logic clk_i,
    input logic rst_ni,

    // QSPI interface
    output logic [CS_NUM-1:0] qspi_csn_o,
    output logic qspi_sck_o,

    input  logic [3:0] qspi_i,
    output logic [3:0] qspi_o,
    output logic [3:0] qspi_oe, // output enable for qspi_o

    // QSPI control signals
    input  logic qspi_abort_i,   // abort current transfer (will avoid MODE or DUMMY phase)
    input  logic qspi_start_i,   // start the transfer
    output logic qspi_busy_o,    // transfer in progress
    output logic qspi_done_o,    // transfer done
    output logic qspi_timeout_o, // transfer timeout

    // QSPI config
    input logic [31:0] qspi_timeout_i,  // timeout in clock cycles (0: no timeout)
    input logic [7:0] qspi_prescaler_i,  // QSPI clock = clk_i / (qspi_prescaler_i*2 + 2)
    input logic qspi_addr_len_i,  // 0: 3 bytes, 1: 4 bytes
    input logic [5:0] qspi_dummy_len_i,  // number of dummy cycles (max 63)
    input logic [31:0] qspi_data_len_i,  // number of bytes to read/write
    input logic [1:0] qspi_cmd_mode_i,  // 00: no command, 01: single, 10: dual, 11: quad
    input logic [1:0] qspi_addr_mode_i,  // 00: no address, 01: single, 10: dual, 11: quad
    input logic [1:0] qspi_data_mode_i,  // 00: no data, 01: single, 10: dual, 11: quad
    input logic [CS_NUM-1:0] qspi_csn_sel_i,  // csn selector
    input logic qspi_sck_mode_i,  // 0: (mode 0) CPOL=0, CPHA=0; 1: (mode 3) CPOL=1, CPHA=1
    input logic qspi_data_dir_i,  // 0: read, 1: write
    input logic qspi_crm_i,  // continuous read mode, ignores data length and keeps reading
    input logic qspi_ddr_i,  // double data rate mode
    input logic qspi_endian_i,  // 0: big endian, 1: little endian

    // QSPI rx/tx data
    input logic [7:0] qspi_cmd_i,  // command to send
    input logic [31:0] qspi_addr_i,  // address to send, length is determined by qspi_addr_len_i
    input logic [7:0] qspi_mode_byte_i,  // mode byte to send after address phase
    input logic [31:0] qspi_wdata_i,  // data to send, length is determined by qspi_data_len_i
    output logic [31:0] qspi_rdata_o,  // data received, length is determined by qspi_data_len_i
    output logic [31:0] qspi_byte_cnt_o,  // the current byte count

    // FIFO interface
    input  logic fifo_empty_i,
    input  logic fifo_full_i,
    output logic fifo_push_o,
    output logic fifo_pop_o
);

  // QSPI SCK GEN
  // clock counter
  logic [7:0] clk_cnt;
  logic clk_cnt_rst;
  always_ff @(posedge clk_i, negedge rst_ni) begin : clock_counter
    if (!rst_ni) begin
      clk_cnt <= 'd0;
    end else if (clk_cnt_rst) begin
      clk_cnt <= 'd0;
    end else begin
      if (clk_cnt == qspi_prescaler_i) begin
        clk_cnt <= 'd0;
      end else begin
        clk_cnt <= clk_cnt + 1;
      end
    end
  end

  // qspi_sck generation
  logic qspi_sck;
  logic qspi_sck_rst, qspi_sck_pause;
  always_ff @(posedge clk_i, negedge rst_ni) begin : qspi_sck_gen
    if (!rst_ni) begin
      qspi_sck <= 1'b0;
    end else if (qspi_sck_rst) begin
      qspi_sck <= qspi_sck_mode_i;  // reset to idle state
    end else if (clk_cnt == qspi_prescaler_i && ~qspi_sck_pause) begin
      qspi_sck <= ~qspi_sck;
    end
  end
  wire qspi_sck_posedge = ~qspi_sck && (clk_cnt == qspi_prescaler_i);
  wire qspi_sck_negedge = qspi_sck && (clk_cnt == qspi_prescaler_i);

  // qspi_csn generation
  logic [CS_NUM-1:0] qspi_csn;
  logic qspi_csn_en;
  always_ff @(posedge clk_i, negedge rst_ni) begin : qspi_csn_gen
    if (!rst_ni) begin
      qspi_csn <= {CS_NUM{1'b1}};  // reset to idle state
    end else if (~qspi_csn_en) begin
      qspi_csn <= {CS_NUM{1'b1}};  // reset to idle state
    end else begin
      qspi_csn <= ~qspi_csn_sel_i;  // assert selected CSn
    end
  end

  // bit counter
  logic [2:0] bit_cnt_limit;
  logic [1:0] bit_cnt_mode;  // 0x: single, 10: dual, 11: quad
  always_comb begin : adjust_bit_cnt
    case (bit_cnt_mode)
      2'd0: bit_cnt_limit = 3'd0;  // 0 for no limit
      2'd1: bit_cnt_limit = 3'd7;  // x1 for single
      2'd2: bit_cnt_limit = 3'd3;  // x2 for dual
      2'd3: bit_cnt_limit = 3'd1;  // x4 for quad
      default: bit_cnt_limit = 3'd7;
    endcase
  end
  logic [5:0] bit_cnt;  // same size as qspi_dummy_len_i
  logic bit_cnt_rst;
  logic bit_cnt_ddr;
  wire bit_cnt_edge = qspi_sck_negedge || (qspi_sck_posedge && bit_cnt_ddr);
  always_ff @(posedge clk_i, negedge rst_ni) begin : bit_counter
    if (!rst_ni) begin
      bit_cnt <= 'd0;
    end else if (bit_cnt_rst) begin
      bit_cnt <= 'd0;
    end else if (bit_cnt_edge && ~qspi_sck_pause) begin
      if (bit_cnt[2:0] == bit_cnt_limit && bit_cnt_limit != 0) begin
        bit_cnt <= 'd0;  // reset counter if limit reached
      end else begin
        bit_cnt <= bit_cnt + 1;
      end
    end
  end

  // byte counter
  logic [31:0] byte_cnt;
  logic byte_cnt_rst;
  wire byte_cnt_edge = (bit_cnt[2:0] == bit_cnt_limit && qspi_sck_negedge);
  wire last_byte = (byte_cnt == (qspi_data_len_i - 1));
  always_ff @(posedge clk_i, negedge rst_ni) begin : byte_counter
    if (!rst_ni) begin
      byte_cnt <= 'd0;
    end else if (byte_cnt_rst) begin
      byte_cnt <= 'd0;
    end else if (byte_cnt_edge && ~qspi_sck_pause) begin
      byte_cnt <= byte_cnt + 1;
    end
  end

  // TX ENGINE
  // main tx shifter
  logic [7:0] tx_shifter;
  logic [7:0] tx_shifter_in;  // input to shifter
  logic [3:0] tx_shifter_out;  // output to qspi_o
  logic [1:0] tx_shifter_mode;  // 0x: single, 10: dual, 11: quad
  logic [1:0] tx_shifter_in_sel;  // 0: command, 1: address, 2: mode byte, 3: data
  logic tx_shifter_en, tx_shifter_load, tx_shifter_ddr;
  logic tx_shifter_preset;  // preset shifter with first byte of address/data
  wire  tx_shift = tx_shifter_en && (qspi_sck_negedge || (qspi_sck_posedge && tx_shifter_ddr));
  always_ff @(posedge clk_i, negedge rst_ni) begin : output_shifter
    if (!rst_ni) begin
      tx_shifter <= 8'd0;
    end else if ((tx_shifter_load || tx_shifter_preset) && ~qspi_sck_pause) begin
      tx_shifter <= tx_shifter_in;
    end else if (tx_shift && ~qspi_sck_pause) begin
      case (tx_shifter_mode)
        2'd0: tx_shifter <= {tx_shifter[6:0], 1'b0};  // single mode, shift 1 bit
        2'd1: tx_shifter <= {tx_shifter[6:0], 1'b0};  // single mode, shift 1 bit
        2'd2: tx_shifter <= {tx_shifter[5:0], 2'b00};  // dual mode, shift 2 bits
        2'd3: tx_shifter <= {tx_shifter[3:0], 4'b0000};  // quad mode, shift 4 bits
        default: tx_shifter <= {tx_shifter[6:0], 1'b0};
      endcase
    end
  end
  always_comb begin : tx_shifter_out_mux
    case (tx_shifter_mode)
      2'd0: tx_shifter_out = {1'b0, 1'b0, 1'b0, tx_shifter[7]};
      2'd1: tx_shifter_out = {1'b0, 1'b0, 1'b0, tx_shifter[7]};
      2'd2: tx_shifter_out = {1'b0, 1'b0, tx_shifter[7], tx_shifter[6]};
      2'd3: tx_shifter_out = {tx_shifter[7], tx_shifter[6], tx_shifter[5], tx_shifter[4]};
      default: tx_shifter_out = {4{1'b0}};
    endcase
  end

  // tx shifter input mux
  logic [7:0] qspi_addr_byte;
  logic [7:0] qspi_wdata_byte;
  logic qspi_wdata_ready;
  always_comb begin : tx_shifter_in_mux
    case (tx_shifter_in_sel)
      2'd0: tx_shifter_in = qspi_cmd_i;
      2'd1: tx_shifter_in = qspi_addr_byte;
      2'd2: tx_shifter_in = qspi_mode_byte_i;
      2'd3: tx_shifter_in = qspi_wdata_byte;
      default: tx_shifter_in = 8'd0;
    endcase
  end
  always_comb begin : qspi_addr_mux
    if (tx_shifter_preset) begin
      // preset first byte of address into shifter
      if (qspi_addr_len_i) begin
        qspi_addr_byte = qspi_addr_i[31:24];  // 4 bytes address
      end else begin
        qspi_addr_byte = qspi_addr_i[23:16];  // 3 bytes address
      end
    end else begin
      if (qspi_addr_len_i) begin
        // 4 bytes address
        case (byte_cnt[1:0])
          2'd0: qspi_addr_byte = qspi_addr_i[23:16];
          2'd1: qspi_addr_byte = qspi_addr_i[15:8];
          2'd2: qspi_addr_byte = qspi_addr_i[7:0];
          default: qspi_addr_byte = 8'd0;
        endcase
      end else begin
        // 3 bytes address
        case (byte_cnt[1:0])
          2'd0: qspi_addr_byte = qspi_addr_i[15:8];
          2'd1: qspi_addr_byte = qspi_addr_i[7:0];
          default: qspi_addr_byte = 8'd0;
        endcase
      end
    end
  end
  always_comb begin : qspi_wdata_mux
    if (tx_shifter_preset) begin
      // preset first byte of data into shifter
      if (qspi_endian_i) begin
        qspi_wdata_byte = qspi_wdata_i[7:0];  // little endian
      end else begin
        qspi_wdata_byte = qspi_wdata_i[31:24];  // big endian
      end
    end else begin
      if (qspi_endian_i) begin
        // little endian
        case (byte_cnt[1:0])
          2'd0: qspi_wdata_byte = qspi_wdata_i[15:8];
          2'd1: qspi_wdata_byte = qspi_wdata_i[23:16];
          2'd2: qspi_wdata_byte = qspi_wdata_i[31:24];
          2'd3: qspi_wdata_byte = qspi_wdata_i[7:0];
          default: qspi_wdata_byte = 8'd0;
        endcase
      end else begin
        // big endian
        case (byte_cnt[1:0])
          2'd0: qspi_wdata_byte = qspi_wdata_i[23:16];
          2'd1: qspi_wdata_byte = qspi_wdata_i[15:8];
          2'd2: qspi_wdata_byte = qspi_wdata_i[7:0];
          2'd3: qspi_wdata_byte = qspi_wdata_i[31:24];
          default: qspi_wdata_byte = 8'd0;
        endcase
      end
    end
  end

  // RX ENGINE
  // main rx shifter
  logic [7:0] rx_shifter;
  logic [3:0] rx_shifter_in;  // input from qspi_i
  logic [1:0] rx_shifter_mode;  // 0x: single, 10: dual, 11: quad
  logic rx_shifter_en, rx_shifter_ddr;
  wire rx_shift = rx_shifter_en && (qspi_sck_posedge || (qspi_sck_negedge && rx_shifter_ddr));
  always_ff @(posedge clk_i, negedge rst_ni) begin : input_shifter
    if (!rst_ni) begin
      rx_shifter <= 8'd0;
    end else if (rx_shift && ~qspi_sck_pause) begin
      case (rx_shifter_mode)
        2'd0: rx_shifter <= {rx_shifter[6:0], rx_shifter_in[1]};  // single mode, shift 1 bit
        2'd1: rx_shifter <= {rx_shifter[6:0], rx_shifter_in[1]};  // single mode, shift 1 bit
        2'd2: rx_shifter <= {rx_shifter[5:0], rx_shifter_in[1:0]};  // dual mode, shift 2 bits
        2'd3: rx_shifter <= {rx_shifter[3:0], rx_shifter_in[3:0]};  // quad mode, shift 4 bits
        default: rx_shifter <= {rx_shifter[6:0], rx_shifter_in[0]};
      endcase
    end
  end

  // rx data register
  logic [31:0] rx_data;
  logic qspi_rdata_rst, qspi_rdata_load, qspi_rdata_valid;
  always_ff @(posedge clk_i, negedge rst_ni) begin : rx_data_delay
    if (!rst_ni) begin
      qspi_rdata_valid <= 'd0;
      qspi_rdata_load  <= 1'b0;
    end else begin
      qspi_rdata_load <= rx_shifter_en && byte_cnt_edge && ~qspi_sck_pause;  // load every byte
      // ready every 4 bytes or at the end of data
      qspi_rdata_valid <= rx_shifter_en && byte_cnt_edge && ((byte_cnt == (qspi_data_len_i-1)) || (byte_cnt[1:0] == 2'd3)) && ~qspi_sck_pause;
    end
  end
  always_ff @(posedge clk_i, negedge rst_ni) begin : rx_data_reg
    if (!rst_ni) begin
      rx_data <= 'd0;
    end else if (qspi_rdata_rst) begin
      rx_data <= 'd0;
    end else begin
      if (qspi_rdata_load) begin
        if (qspi_endian_i) begin
          // little endian
          case (byte_cnt[1:0])
            2'd0: rx_data[31:24] <= rx_shifter;
            2'd1: rx_data[7:0] <= rx_shifter;
            2'd2: rx_data[15:8] <= rx_shifter;
            2'd3: rx_data[23:16] <= rx_shifter;
            default: rx_data <= 'd0;
          endcase
        end else begin
          // big endian
          case (byte_cnt[1:0])
            2'd0: rx_data[7:0] <= rx_shifter;
            2'd1: rx_data[31:24] <= rx_shifter;
            2'd2: rx_data[23:16] <= rx_shifter;
            2'd3: rx_data[15:8] <= rx_shifter;
            default: rx_data <= 'd0;
          endcase
        end
      end
    end
  end


  // CONTROL FSM
  logic qspi_done;
  typedef enum logic [2:0] {
    IDLE,
    PREPARE,
    COMMAND,
    ADDRESS,
    MODE,
    DUMMY,
    DATA,
    DONE
  } qspi_state_t;

  // FSM state registers
  qspi_state_t qspi_nstate, qspi_cstate;
  always_ff @(posedge clk_i, negedge rst_ni) begin : fsm_reg
    if (!rst_ni) begin
      qspi_cstate <= IDLE;
    end else begin
      qspi_cstate <= qspi_nstate;
    end
  end

  // CRM state register
  logic crm_active;
  always_ff @(posedge clk_i, negedge rst_ni) begin : crm_state
    if (!rst_ni) begin
      crm_active <= 1'b0;
    end else if (qspi_done) begin
      crm_active <= qspi_crm_i;  // only lock CRM if first transfer is done
    end
  end

  // Abort lock register
  logic qspi_abort;
  always_ff @(posedge clk_i, negedge rst_ni) begin : abort_lock
    if (!rst_ni) begin
      qspi_abort <= 1'b0;
    end else if (qspi_abort_i) begin
      qspi_abort <= 1'b1;  // lock abort until next transfer
    end else if (qspi_done) begin
      qspi_abort <= 1'b0;  // unlock abort after transfer is done
    end
  end

  // clock timer
  logic [31:0] clk_timer;
  logic clk_timer_rst;
  wire clk_timer_expired = (clk_timer == qspi_timeout_i) && (qspi_timeout_i != 32'd0);
  always_ff @(posedge clk_i, negedge rst_ni) begin : clk_timer_reg
    if (!rst_ni) begin
      clk_timer <= 'd0;
    end else if (clk_timer_rst) begin
      clk_timer <= 'd0;  // reset timer
    end else begin
      clk_timer <= clk_timer + 1;  // increment timer every clock cycle
    end
  end

  // FSM next state logic
  logic cphase_ddr;
  logic [1:0] cphase_mode;
  logic cnt_rst;
  always_comb begin : simplify_assigns
    bit_cnt_ddr = cphase_ddr;
    tx_shifter_ddr = cphase_ddr;
    rx_shifter_ddr = cphase_ddr;
    bit_cnt_mode = cphase_mode;
    tx_shifter_mode = cphase_mode;
    rx_shifter_mode = cphase_mode;

    clk_cnt_rst = cnt_rst;
    bit_cnt_rst = cnt_rst;
    byte_cnt_rst = cnt_rst;
  end
  always_comb begin : fsm_logic
    cnt_rst = 1'b1;
    clk_timer_rst = 1'b1;

    qspi_csn_en = 1'b0;
    qspi_sck_pause = 1'b0;
    qspi_sck_rst = 1'b0;

    rx_shifter_en = 1'b0;
    tx_shifter_en = 1'b0;
    tx_shifter_load = 1'b0;
    tx_shifter_preset = 1'b0;
    tx_shifter_in_sel = 2'd0;  // 0: command, 1: address, 2: mode byte, 3: data

    qspi_wdata_ready = 1'b0;
    qspi_rdata_rst = 1'b0;

    cphase_ddr = 1'b0;  // default to SDR
    cphase_mode = 2'b00;  // default to output disabled

    qspi_done = 1'b0;
    qspi_busy_o = 1'b0;

    qspi_nstate = qspi_cstate;  // default to stay in current state

    case (qspi_cstate)
      IDLE: begin
        qspi_busy_o = 1'b0;  // transfer not in progress
        cnt_rst = 1'b1;  // reset counters
        clk_timer_rst = 1'b1;  // reset timeout timer

        qspi_sck_rst = 1'b1;  // reset SCK to idle state
        qspi_csn_en = 1'b0;  // reset CSN to idle state

        cphase_mode = 2'b00;  // disable output

        if (qspi_start_i) begin
          qspi_csn_en = 1'b1;  // assert CSN
          qspi_rdata_rst = 1'b1;  // reset rx data register
          tx_shifter_preset = 1'b1;  // preset tx byte into shifter
          if (crm_active) begin
            tx_shifter_in_sel = 2'd1;  // load address byte directly if CRM is active
          end else begin
            tx_shifter_in_sel = 2'd0;  // load command byte into shifter
          end
          qspi_nstate = PREPARE;
        end else begin
          qspi_nstate = IDLE;
        end
      end

      PREPARE: begin  // 1 cycle delay
        qspi_busy_o = 1'b1;  // transfer in progress
        cnt_rst = 1'b1;  // dont start counters
        clk_timer_rst = 1'b0;  // start timeout timer
        qspi_sck_rst = 1'b0;  // start SCK generation

        qspi_csn_en = 1'b1;  // keep CSN asserted

        if (crm_active) begin
          cphase_mode = qspi_addr_mode_i;  // start output address
          qspi_nstate = ADDRESS;  // skip command phase if CRM is active
        end else begin
          cphase_mode = qspi_cmd_mode_i;  // start output command
          qspi_nstate = COMMAND;  // default to command phase
        end
      end

      COMMAND: begin
        qspi_busy_o = 1'b1;  // transfer in progress
        cnt_rst = 1'b0;  // start counters
        clk_timer_rst = 1'b0;  // start timeout timer
        qspi_sck_rst = 1'b0;  // dont reset SCK

        qspi_csn_en = 1'b1;  // keep CSN asserted
        tx_shifter_en = 1'b1;  // enable tx shifter

        cphase_ddr = 1'b0;  // COMMAND always in SDR mode
        cphase_mode = qspi_cmd_mode_i;  // set command phase mode

        if (qspi_abort) begin
          cnt_rst = 1'b1;  // reset counters for next phase
          qspi_sck_rst = 1'b1;  // reset SCK to idle state
          qspi_nstate = DONE;  // go to done state if abort is asserted
        end else if (byte_cnt_edge) begin
          cnt_rst = 1'b1;  // reset counters for next phase
          if (qspi_addr_mode_i != 'd0) begin
            tx_shifter_in_sel = 2'd1;  // select address byte
            tx_shifter_preset = 1'b1;  // preset first address byte into shifter
            qspi_nstate = ADDRESS;  // go to address phase
          end else if (qspi_dummy_len_i != 'd0) begin
            qspi_nstate = DUMMY;
          end else if (qspi_data_mode_i != 'd0 && qspi_data_len_i != 'd0) begin
            tx_shifter_in_sel = 2'd3;  // select data byte
            tx_shifter_preset = 1'b1;  // preset first data byte into shifter
            if ((fifo_empty_i && qspi_data_dir_i) || (fifo_full_i && !qspi_data_dir_i)) begin
              cnt_rst = 1'b0;  // dont reset counters when pausing
              qspi_sck_pause = 1'b1;  // pause SCK if fifo still empty or already full
            end else begin
              qspi_nstate = DATA;  // go to data phase
            end
          end else begin
            qspi_sck_rst = 1'b1;  // reset SCK to idle state
            qspi_nstate  = DONE;  // go to done state if no more phases
          end
        end
      end

      ADDRESS: begin
        qspi_busy_o = 1'b1;  // transfer in progress
        cnt_rst = 1'b0;  // start counters
        clk_timer_rst = 1'b0;  // start timeout timer
        qspi_sck_rst = 1'b0;  // dont reset SCK

        qspi_csn_en = 1'b1;  // keep CSN asserted
        tx_shifter_en = 1'b1;  // enable tx shifter

        cphase_ddr = qspi_ddr_i;  // enable DDR if configured
        cphase_mode = qspi_addr_mode_i;  // set address phase mode

        if (qspi_abort) begin
          cnt_rst = 1'b1;  // reset counters for next phase
          qspi_sck_rst = 1'b1;  // reset SCK to idle state
          qspi_nstate = DONE;  // go to done state if abort is asserted
        end else if (byte_cnt_edge) begin
          if (byte_cnt[1:0] == ((qspi_addr_len_i ? 2'd3 : 2'd2))) begin
            cnt_rst = 1'b1;  // reset counters for next phase
            if (qspi_crm_i && qspi_dummy_len_i != 'd0) begin
              tx_shifter_in_sel = 2'd2;  // select mode byte
              tx_shifter_preset = 1'b1;  // load mode byte into shifter
              qspi_nstate = MODE;  // go to mode phase
            end else if (qspi_dummy_len_i != 'd0) begin
              qspi_nstate = DUMMY;  // go to dummy phase
            end else if (qspi_data_mode_i != 'd0 && qspi_data_len_i != 'd0) begin
              tx_shifter_in_sel = 2'd3;  // select data byte
              tx_shifter_preset = 1'b1;  // preset first data byte into shifter
              if ((fifo_empty_i && qspi_data_dir_i) || (fifo_full_i && !qspi_data_dir_i)) begin
                cnt_rst = 1'b0;  // dont reset counters when pausing
                qspi_sck_pause = 1'b1;  // pause SCK if fifo still empty or already full
              end else begin
                qspi_nstate = DATA;  // go to data phase
              end
            end else begin
              qspi_sck_rst = 1'b1;  // reset SCK to idle state
              qspi_nstate  = DONE;  // go to done state if no more phases
            end
          end else begin
            tx_shifter_in_sel = 2'd1;  // select address byte
            tx_shifter_load = 1'b1;  // load next address byte into shifter
            qspi_nstate = ADDRESS;
          end
        end
      end

      MODE: begin
        qspi_busy_o = 1'b1;  // transfer in progress
        cnt_rst = 1'b0;  // start counters
        clk_timer_rst = 1'b0;  // start timeout timer
        qspi_sck_rst = 1'b0;  // dont reset SCK

        qspi_csn_en = 1'b1;  // keep CSN asserted
        tx_shifter_en = 1'b1;  // enable tx shifter

        cphase_ddr = qspi_ddr_i;  // enable DDR if configured
        cphase_mode = qspi_addr_mode_i;  // set mode phase mode

        if (qspi_sck_negedge) begin
          // count mode bits as dummy bits
          if (bit_cnt == (qspi_dummy_len_i - 1)) begin
            if (qspi_data_mode_i != 'd0) begin
              tx_shifter_in_sel = 2'd3;  // select data byte
              tx_shifter_preset = 1'b1;  // preset first data byte into shifter
              if ((fifo_empty_i && qspi_data_dir_i) || (fifo_full_i && !qspi_data_dir_i)) begin
                cnt_rst = 1'b0;  // dont reset counters when pausing
                qspi_sck_pause = 1'b1;  // pause SCK if fifo still empty or already full
              end else begin
                cnt_rst = 1'b1;  // reset counters for next phase
                qspi_nstate = DATA;  // go to data phase
              end
            end else begin
              cnt_rst = 1'b1;  // reset counters for next phase
              qspi_sck_rst = 1'b1;  // reset SCK to idle state
              qspi_nstate = DONE;  // go to done state if no more phases
            end
          end else if (byte_cnt_edge) begin
            if (qspi_dummy_len_i != 'd0) begin
              cnt_rst = 1'b0;  // continue counters for dummy phase
              qspi_nstate = DUMMY;  // go to dummy phase
            end else if (qspi_data_mode_i != 'd0 && qspi_data_len_i != 'd0) begin
              tx_shifter_in_sel = 2'd3;  // select data byte
              tx_shifter_preset = 1'b1;  // preset first data byte into shifter
              if ((fifo_empty_i && qspi_data_dir_i) || (fifo_full_i && !qspi_data_dir_i)) begin
                cnt_rst = 1'b0;  // dont reset counters when pausing
                qspi_sck_pause = 1'b1;  // pause SCK if fifo still empty or already full
              end else begin
                cnt_rst = 1'b1;  // reset counters for next phase
                qspi_nstate = DATA;  // go to data phase
              end
            end else begin
              cnt_rst = 1'b1;  // reset counters for next phase
              qspi_sck_rst = 1'b1;  // reset SCK to idle state
              qspi_nstate = DONE;  // go to done state if no more phases
            end
          end
        end
      end

      DUMMY: begin
        qspi_busy_o = 1'b1;  // transfer in progress
        cnt_rst = 1'b0;  // start counters
        clk_timer_rst = 1'b0;  // start timeout timer
        qspi_sck_rst = 1'b0;  // dont reset SCK

        qspi_csn_en = 1'b1;  // keep CSN asserted

        cphase_ddr = 1'b0;  // DUMMY always in SDR mode
        cphase_mode = 2'b00;  // disable output for DUMMY phase

        if (qspi_sck_negedge) begin
          if (bit_cnt == (qspi_dummy_len_i - 1)) begin
            cnt_rst = 1'b1;  // reset counters for next phase
            if (qspi_data_mode_i != 'd0) begin
              tx_shifter_in_sel = 2'd3;  // select data byte
              tx_shifter_preset = 1'b1;  // preset first data byte into shifter
              if ((fifo_empty_i && qspi_data_dir_i) || (fifo_full_i && !qspi_data_dir_i)) begin
                cnt_rst = 1'b0;  // dont reset counters when pausing
                qspi_sck_pause = 1'b1;  // pause SCK if fifo still empty or already full
              end else begin
                qspi_nstate = DATA;  // go to data phase
              end
            end else begin
              qspi_sck_rst = 1'b1;  // reset SCK to idle state
              qspi_nstate  = DONE;  // go to done state if no more phases
            end
          end
        end
      end

      DATA: begin
        qspi_busy_o = 1'b1;  // transfer in progress
        cnt_rst = 1'b0;  // start counters
        clk_timer_rst = 1'b0;  // start timeout timer
        qspi_sck_rst = 1'b0;  // dont reset SCK

        qspi_csn_en = 1'b1;  // keep CSN asserted
        if (qspi_data_dir_i) begin
          tx_shifter_en = 1'b1;  // enable tx shifter for writing
        end else begin
          rx_shifter_en = 1'b1;  // enable rx shifter for reading
        end

        cphase_ddr  = qspi_ddr_i;  // enable DDR if configured
        cphase_mode = qspi_data_mode_i;  // set data phase mode

        if (qspi_abort || clk_timer_expired) begin
          qspi_sck_rst = 1'b1;  // reset SCK to idle state
          qspi_nstate  = DONE;  // go to done state if abort is asserted
        end else if (byte_cnt_edge) begin
          if (last_byte) begin
            qspi_wdata_ready = qspi_data_dir_i;  // pop out any remainding data if just one word
            if (byte_cnt[1:0] == 2'd0) begin
              qspi_rdata_rst = ~qspi_data_dir_i;  // reset rx data register for next read
            end
            qspi_sck_rst = 1'b1;  // reset SCK to idle state
            qspi_nstate  = DONE;  // go to done state if no more data
          end else begin
            if (byte_cnt[1:0] == 2'd3) begin
              // pause SCK if FIFO is full when reading or FIFO is empty when writing
              qspi_sck_pause = (fifo_full_i && !qspi_data_dir_i) || (fifo_empty_i && qspi_data_dir_i);
            end else if (byte_cnt[1:0] == 2'd2) begin
              qspi_wdata_ready = qspi_data_dir_i;  // load next write data word into register
            end else if (byte_cnt[1:0] == 2'd0) begin
              qspi_rdata_rst = ~qspi_data_dir_i;  // reset rx data register for next read
            end
            tx_shifter_in_sel = 2'd3;  // select data byte
            tx_shifter_load = 1'b1;  // load next data byte into shifter
            qspi_nstate = DATA;
          end
        end
      end

      DONE: begin
        qspi_busy_o = 1'b0;  // transfer finished
        cnt_rst = 1'b1;  // stop counters
        clk_timer_rst = 1'b1;  // stop timeout timer
        qspi_sck_rst = 1'b1;  // stop SCK generation

        qspi_csn_en = 1'b1;  // keep CSN asserted
        cphase_mode = 2'b00;  // disable output

        qspi_done = 1'b1;  // signal transfer done
        qspi_nstate = IDLE;
      end

      default: begin
        qspi_nstate = IDLE;
      end
    endcase
  end

  // OUTPUT ASSIGNS
  assign qspi_csn_o = qspi_csn;  // drive CSN for each chip select
  assign qspi_sck_o = qspi_sck;
  assign qspi_o = tx_shifter_out;
  assign rx_shifter_in = qspi_i;

  always_comb begin : qspi_oe_mux
    if (rx_shifter_en) begin
      qspi_oe = 4'b0000;  // disable output when reading
    end else begin
      case (cphase_mode)
        2'b00:   qspi_oe = 4'b0000;  // disable output
        2'b01:   qspi_oe = 4'b0001;  // single mode
        2'b10:   qspi_oe = 4'b0011;  // dual mode
        2'b11:   qspi_oe = 4'b1111;  // quad mode
        default: qspi_oe = 4'b0000;
      endcase
    end
  end

  assign qspi_rdata_o = rx_data;
  assign qspi_byte_cnt_o = byte_cnt;

  assign fifo_pop_o = qspi_wdata_ready && !fifo_empty_i;  // pop FIFO when requesting write data

  logic fifo_push;
  always_ff @(posedge clk_i, negedge rst_ni) begin : fifo_push_lock
    if (!rst_ni) begin
      fifo_push <= 1'b0;
    end else begin
      if (qspi_rdata_valid) begin
        fifo_push <= 1'b1;  // lock push signal
      end else if (~fifo_full_i) begin
        fifo_push <= 1'b0;  // unlock push signal when FIFO is not full
      end
    end
  end
  assign fifo_push_o = fifo_push && ~fifo_full_i;  // output push signal when FIFO is not full

  always_ff @(posedge clk_i, negedge rst_ni) begin : delayed_output
    if (!rst_ni) begin
      qspi_done_o <= 1'b0;
      qspi_timeout_o <= 1'b0;
    end else begin
      qspi_done_o <= qspi_done;
      qspi_timeout_o <= clk_timer_expired;
    end
  end

endmodule
