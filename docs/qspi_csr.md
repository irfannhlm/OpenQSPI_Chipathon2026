# QSPI CSR Mapping

| Offset   | Register         | Bit Field | Name      | Access     | Description                                                                                         |
| :------- | :--------------- | :-------- | :-------- | :--------- | :-------------------------------------------------------------------------------------------------- |
| **0x00** | **QSPI_CTRL**    | `[0]`     | START     | WO (Pulse) | Start transfer.                                                                                     |
|          |                  | `[1]`     | ABORT     | WO (Pulse) | Abort current transfer. Never stalls pready_o.                                                      |
|          |                  | `[2]`     | DONE      | RO (W1C)   | Transfer completed.                                                                                 |
|          |                  | `[3]`     | BUSY      | RO         | Core is currently busy.                                                                             |
|          |                  | `[4]`     | TIMEOUT   | RO (W1C)   | Timeout occurred (mirrors qspi_timeout_o).                                                          |
|          |                  | `[8:5]`   | FIFO_ERR  | RO (W1C)   | FIFO Error flags:<br>• 0001: RX-empty<br>• 0010: TX-full<br>• 0100: Wrong-direction QSPI_DR access  |
|          |                  | `[9]`     | FLUSH     | WO (Pulse) | Flush FIFOs. Blocked while BUSY.                                                                    |
| **0x04** | **QSPI_CFG0**    | `[7:0]`   | PRESCALER | RW         | Clock prescaler selection.                                                                          |
|          |                  | `[8]`     | ADDR_LEN  | RW         | Address length Selection:<br>• 0: 3 bytes<br>• 1: 4 bytes                                           |
|          |                  | `[14:9]`  | DUMMY_LEN | RW         | Dummy cycle length.                                                                                 |
|          |                  | `[16:15]` | CMD_MODE  | RW         | Command mode:<br>• 00: None<br>• 01: Single<br>• 10: Dual<br>• 11: Quad                             |
|          |                  | `[18:17]` | ADDR_MODE | RW         | Address mode.                                                                                       |
|          |                  | `[20:19]` | DATA_MODE | RW         | Data mode.                                                                                          |
|          |                  | `[21]`    | SCK_MODE  | RW         | Serial clock mode.                                                                                  |
|          |                  | `[22]`    | DATA_DIR  | RW         | Data direction.                                                                                     |
|          |                  | `[23]`    | CRM       | RW         | Continuous Read Mode.                                                                               |
|          |                  | `[24]`    | DDR       | RW         | Double Data Rate control.                                                                           |
|          |                  | `[25]`    | ENDIAN    | RW         | Endianness configuration.                                                                           |
|          |                  | `[29:26]` | CSN_SEL   | -          | Reserved (Tied off in this single chip-select wrapper).                                             |
| **0x08** | **QSPI_DLEN**    | `[31:0]`  | DATA_LEN  | RW         | Total data length for transfer.                                                                     |
| **0x0C** | **QSPI_CMD**     | `[7:0]`   | CMD       | RW         | SPI Command byte.                                                                                   |
|          |                  | `[15:8]`  | MODE_BYTE | RW         | SPI Mode byte.                                                                                      |
| **0x10** | **QSPI_ADDR**    | `[31:0]`  | ADDR      | RW         | SPI Transfer start address.                                                                         |
| **0x14** | **QSPI_DR**      | `[31:0]`  | DATA      | RW         | Push (write when DATA_DIR=write) / pop (read when DATA_DIR=read) window into the shared TX/RX FIFO. |
| **0x18** | **QSPI_BCNT**    | `[31:0]`  | BYTE_CNT  | RO         | Current byte count.                                                                                 |
| **0x1C** | **QSPI_TIMEOUT** | `[31:0]`  | TIMEOUT   | RW         | Timeout threshold in clock cycles (0: no timeout).                                                  |

## [Back to README](../README.md)
