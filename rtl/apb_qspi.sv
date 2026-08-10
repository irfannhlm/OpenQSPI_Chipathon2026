// APB Wrapper for QSPI Master
// Author: Team Crispi - SSCS Chipathon 2026
//
// Register map (byte offsets, all registers 32-bit, word aligned):
//   0x00 QSPI_CTRL  [0] START (WO, pulse) [1] ABORT (WO, pulse) [2] DONE (RO, W1C)
//                    [3] BUSY (RO) [4] TIMEOUT (RO, W1C, mirrors qspi_timeout_o)
//                    [8:5] FIFO_ERR (RO, W1C: 0001 RX-empty, 0010 TX-full, 0100
//                    wrong-direction QSPI_DR access) [9] FLUSH (WO, pulse, blocked
//                    while BUSY)
//   0x04 QSPI_CFG0  [7:0] PRESCALER [8] ADDR_LEN (0: 3 bytes, 1: 4 bytes)
//                    [14:9] DUMMY_LEN [16:15] CMD_MODE (00: none, 01: single,
//                    10: dual, 11: quad) [18:17] ADDR_MODE [20:19] DATA_MODE
//                    [21] SCK_MODE [22] DATA_DIR [23] CRM [24] DDR [25] ENDIAN
//                    [29:26] CSN_SEL (one-hot chip-select enable, low CS_NUM
//                    bits used; active-high, selected line driven low on qspi_csn_o)
//   0x08 QSPI_DLEN  [31:0] DATA_LEN
//   0x0C QSPI_CMD   [7:0] CMD [15:8] MODE_BYTE
//   0x10 QSPI_ADDR  [31:0] ADDR
//   0x14 QSPI_DR    push (write, DATA_DIR=write) / pop (read, DATA_DIR=read) window
//                    into the shared TX/RX FIFO
//   0x18 QSPI_BCNT  [31:0] BYTE_CNT (RO)
//   0x1C QSPI_TIMEOUT [31:0] TIMEOUT (clock cycles, 0: no timeout)
//
// Writes to QSPI_CTRL.START/FLUSH and to QSPI_CFG0/QSPI_DLEN/QSPI_CMD/QSPI_ADDR/
// QSPI_TIMEOUT stall pready_o while BUSY, since qspi_master samples its config ports
// live and isn't internally latched. QSPI_CTRL.ABORT is never stalled. QSPI_DR access
// is never stalled; wrong-direction or full/empty access completes immediately and
// reports an error via QSPI_CTRL.FIFO_ERR instead.

module apb_qspi #(
    parameter int FIFO_DEPTH = 16,
    parameter int CS_NUM = 1  // number of chip selects
) (
    // clock and reset
    input logic clk_i,
    input logic rst_ni,

    // APB interface
    input logic psel_i,
    input logic penable_i,
    input logic pwrite_i,
    input logic [31:0] paddr_i,
    input logic [31:0] pwdata_i,
    output logic [31:0] prdata_o,
    output logic pready_o,
    output logic pslverr_o,

    // QSPI interface
    output logic [CS_NUM-1:0] qspi_csn_o,
    output logic qspi_sck_o,
    input logic [3:0] qspi_i,
    output logic [3:0] qspi_o,
    output logic [3:0] qspi_oe  // output enable for qspi_o
);

  assign pslverr_o = 1'b0;  // no error reporting implemented

  // Register byte offsets
  localparam logic [7:0] ADDR_CTRL = 8'h00;
  localparam logic [7:0] ADDR_CFG0 = 8'h04;
  localparam logic [7:0] ADDR_DLEN = 8'h08;
  localparam logic [7:0] ADDR_CMD = 8'h0C;
  localparam logic [7:0] ADDR_ADDR = 8'h10;
  localparam logic [7:0] ADDR_DR = 8'h14;
  localparam logic [7:0] ADDR_BCNT = 8'h18;
  localparam logic [7:0] ADDR_TIMEOUT = 8'h1C;

  wire [7:0] reg_addr = paddr_i[7:0];

  // CSR storage
  logic [31:0] cfg0_q;
  logic [31:0] dlen_q;
  logic [31:0] cmd_q;
  logic [31:0] addr_q;
  logic [31:0] timeout_q;
  logic done_q;
  logic busy_q;
  logic timeout_status_q;
  logic [3:0] fifo_err_q;

  wire data_dir_w = cfg0_q[22];  // 0: read, 1: write

  // APB access-phase / completion strobes
  wire apb_access = psel_i && penable_i;

  wire is_ctrl_write = apb_access && pwrite_i && (reg_addr == ADDR_CTRL);
  wire is_start_write = is_ctrl_write && pwdata_i[0];
  wire is_abort_write = is_ctrl_write && pwdata_i[1];
  wire is_flush_write = is_ctrl_write && pwdata_i[9];
  wire is_cfg_write = apb_access && pwrite_i &&
      (reg_addr == ADDR_CFG0 || reg_addr == ADDR_DLEN ||
       reg_addr == ADDR_CMD || reg_addr == ADDR_ADDR || reg_addr == ADDR_TIMEOUT);

  // ABORT is never stalled; START/FLUSH/config writes wait out an in-flight transfer
  // since qspi_master's config ports aren't internally latched
  wire stall_for_busy = busy_q && !is_abort_write && (is_start_write || is_flush_write || is_cfg_write);

  assign pready_o = !(apb_access && stall_for_busy);

  wire         apb_wr_done = apb_access && pwrite_i && pready_o;
  wire         apb_rd_done = apb_access && !pwrite_i && pready_o;

  wire         qspi_start_pulse = apb_wr_done && (reg_addr == ADDR_CTRL) && pwdata_i[0];
  wire         qspi_abort_pulse = apb_wr_done && (reg_addr == ADDR_CTRL) && pwdata_i[1];
  wire         qspi_flush_pulse = apb_wr_done && (reg_addr == ADDR_CTRL) && pwdata_i[9];
  wire         ctrl_err_clear = apb_wr_done && (reg_addr == ADDR_CTRL) && (pwdata_i[8:5] != 4'd0);
  wire         ctrl_done_clear = apb_wr_done && (reg_addr == ADDR_CTRL) && pwdata_i[2];
  wire         ctrl_timeout_clear = apb_wr_done && (reg_addr == ADDR_CTRL) && pwdata_i[4];

  // QSPI_DR access, gated by DATA_DIR; wrong-direction / full / empty never stalls,
  // it completes immediately and is reported through FIFO_ERR instead
  wire         apb_dr_write_access = apb_wr_done && (reg_addr == ADDR_DR);
  wire         apb_dr_read_access = apb_rd_done && (reg_addr == ADDR_DR);

  // qspi_master <-> apb_qspi wires
  logic [31:0] qm_rdata;
  logic [31:0] qm_byte_cnt;
  logic        qm_done;
  logic        qm_timeout;
  logic        qm_fifo_push;
  logic        qm_fifo_pop;

  // shared FIFO wires
  logic [31:0] fifo_data_o;
  logic        fifo_empty;
  logic        fifo_full;
  logic        fifo_push;
  logic        fifo_pop;
  logic [31:0] fifo_data_i_mux;

  wire         apb_dr_push_strobe = apb_dr_write_access && data_dir_w && !fifo_full;
  wire         apb_dr_pop_strobe = apb_dr_read_access && !data_dir_w && !fifo_empty;

  assign fifo_push = data_dir_w ? apb_dr_push_strobe : qm_fifo_push;
  assign fifo_pop = data_dir_w ? qm_fifo_pop : apb_dr_pop_strobe;
  assign fifo_data_i_mux = data_dir_w ? pwdata_i : qm_rdata;

  // FIFO error capture (sticky until write-1-to-clear via QSPI_CTRL[7:4])
  wire dr_wrong_dir_err = (apb_dr_write_access && !data_dir_w) || (apb_dr_read_access && data_dir_w);
  wire dr_full_err = apb_dr_write_access && data_dir_w && fifo_full;
  wire dr_empty_err = apb_dr_read_access && !data_dir_w && fifo_empty;
  wire qm_full_err = qm_fifo_push && fifo_full;
  wire qm_empty_err = qm_fifo_pop && fifo_empty;

  logic [3:0] fifo_err_next;
  always_comb begin
    if (dr_wrong_dir_err) fifo_err_next = 4'b0100;
    else if (dr_full_err || qm_full_err) fifo_err_next = 4'b0010;
    else if (dr_empty_err || qm_empty_err) fifo_err_next = 4'b0001;
    else fifo_err_next = 4'b0000;
  end

  always_ff @(posedge clk_i) begin : csr_regs
    if (!rst_ni) begin
      cfg0_q           <= 32'd0;
      dlen_q           <= 32'd0;
      cmd_q            <= 32'd0;
      addr_q           <= 32'd0;
      timeout_q        <= 32'd0;
      done_q           <= 1'b0;
      busy_q           <= 1'b0;
      timeout_status_q <= 1'b0;
      fifo_err_q       <= 4'd0;
    end else begin
      if (apb_wr_done && (reg_addr == ADDR_CFG0)) cfg0_q <= pwdata_i;
      if (apb_wr_done && (reg_addr == ADDR_DLEN)) dlen_q <= pwdata_i;
      if (apb_wr_done && (reg_addr == ADDR_CMD)) cmd_q <= pwdata_i;
      if (apb_wr_done && (reg_addr == ADDR_ADDR)) addr_q <= pwdata_i;
      if (apb_wr_done && (reg_addr == ADDR_TIMEOUT)) timeout_q <= pwdata_i;

      if (qm_done) busy_q <= 1'b0;
      else if (qspi_start_pulse) busy_q <= 1'b1;

      if (qm_done) done_q <= 1'b1;
      else if (ctrl_done_clear) done_q <= 1'b0;

      if (qm_timeout) timeout_status_q <= 1'b1;
      else if (ctrl_timeout_clear) timeout_status_q <= 1'b0;

      if (fifo_err_next != 4'd0) fifo_err_q <= fifo_err_next;
      else if (ctrl_err_clear) fifo_err_q <= 4'd0;
    end
  end

  // Readback mux
  always_comb begin : prdata_mux
    case (reg_addr)
      ADDR_CTRL:    prdata_o = {22'd0, 1'b0, fifo_err_q, timeout_status_q, busy_q, done_q, 2'b00};
      ADDR_CFG0:    prdata_o = cfg0_q;
      ADDR_DLEN:    prdata_o = dlen_q;
      ADDR_CMD:     prdata_o = cmd_q;
      ADDR_ADDR:    prdata_o = addr_q;
      ADDR_DR:      prdata_o = fifo_data_o;
      ADDR_BCNT:    prdata_o = qm_byte_cnt;
      ADDR_TIMEOUT: prdata_o = timeout_q;
      default:      prdata_o = 32'd0;
    endcase
  end

  qspi_master #(
      .CS_NUM(CS_NUM)
  ) u_qspi_master (
      .clk_i (clk_i),
      .rst_ni(rst_ni),

      .qspi_csn_o(qspi_csn_o),
      .qspi_sck_o(qspi_sck_o),

      .qspi_i (qspi_i),
      .qspi_o (qspi_o),
      .qspi_oe(qspi_oe),

      .qspi_abort_i  (qspi_abort_pulse),
      .qspi_start_i  (qspi_start_pulse),
      .qspi_done_o   (qm_done),
      .qspi_timeout_o(qm_timeout),
      .qspi_busy_o   (/*not used*/),

      .qspi_timeout_i  (timeout_q),
      .qspi_prescaler_i(cfg0_q[7:0]),
      .qspi_addr_len_i (cfg0_q[8]),
      .qspi_dummy_len_i(cfg0_q[14:9]),
      .qspi_data_len_i (dlen_q),
      .qspi_cmd_mode_i (cfg0_q[16:15]),
      .qspi_addr_mode_i(cfg0_q[18:17]),
      .qspi_data_mode_i(cfg0_q[20:19]),
      .qspi_csn_sel_i  (cfg0_q[26+:CS_NUM]),
      .qspi_sck_mode_i (cfg0_q[21]),
      .qspi_data_dir_i (cfg0_q[22]),
      .qspi_crm_i      (cfg0_q[23]),
      .qspi_ddr_i      (cfg0_q[24]),
      .qspi_endian_i   (cfg0_q[25]),

      .qspi_cmd_i      (cmd_q[7:0]),
      .qspi_addr_i     (addr_q),
      .qspi_mode_byte_i(cmd_q[15:8]),
      .qspi_wdata_i    (fifo_data_o),
      .qspi_rdata_o    (qm_rdata),
      .qspi_byte_cnt_o (qm_byte_cnt),

      .fifo_empty_i(fifo_empty),
      .fifo_full_i (fifo_full),
      .fifo_push_o (qm_fifo_push),
      .fifo_pop_o  (qm_fifo_pop)
  );

  fifo #(
      .DEPTH(FIFO_DEPTH)
  ) u_fifo (
      .clk_i (clk_i),
      .rst_ni(rst_ni),

      .flush_i(qspi_flush_pulse),
      .push_i (fifo_push),
      .pop_i  (fifo_pop),
      .data_i (fifo_data_i_mux),
      .data_o (fifo_data_o),
      .empty_o(fifo_empty),
      .full_o (fifo_full)
  );

endmodule
