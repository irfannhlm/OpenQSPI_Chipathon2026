"""Register map of apb_qspi.sv plus field packing helpers.

Mirrors the map documented in rtl/apb_qspi.sv:
  0x00 QSPI_CTRL   0x04 QSPI_CFG0  0x08 QSPI_DLEN  0x0C QSPI_CMD
  0x10 QSPI_ADDR   0x14 QSPI_DR    0x18 QSPI_BCNT  0x1C QSPI_TIMEOUT
"""

# --- register offsets ---
CTRL = 0x00
CFG0 = 0x04
DLEN = 0x08
CMD = 0x0C
ADDR = 0x10
DR = 0x14
BCNT = 0x18
TIMEOUT = 0x1C

# --- QSPI_CTRL bits ---
CTRL_START = 1 << 0
CTRL_ABORT = 1 << 1
CTRL_DONE = 1 << 2  # RO, W1C
CTRL_BUSY = 1 << 3  # RO
CTRL_TIMEOUT = 1 << 4  # RO, W1C
CTRL_FIFO_ERR_SHIFT = 5
CTRL_FIFO_ERR_MASK = 0xF << CTRL_FIFO_ERR_SHIFT  # RO, W1C
CTRL_FLUSH = 1 << 9
CTRL_W1C_ALL = CTRL_DONE | CTRL_TIMEOUT | CTRL_FIFO_ERR_MASK

# FIFO_ERR codes (QSPI_CTRL[8:5])
FIFO_ERR_NONE = 0x0
FIFO_ERR_RX_EMPTY = 0x1
FIFO_ERR_TX_FULL = 0x2
FIFO_ERR_WRONG_DIR = 0x4

# --- QSPI_CFG0 field masks ---
CFG0_WMASK = 0x03FF_FFFF  # implemented bits [25:0]
CMD_WMASK = 0x0000_FFFF  # CMD[7:0] + MODE_BYTE[15:8]


def lanes(mode: int) -> int:
    """Map a 2-bit *_MODE field to its lane count (0 means phase disabled)."""
    return {0: 0, 1: 1, 2: 2, 3: 4}[mode & 3]


def pack_cfg0(
    prescaler=0,
    addr_len4=0,
    dummy=0,
    cmd_mode=0,
    addr_mode=0,
    data_mode=0,
    sck_mode=0,
    dir_write=0,
    crm=0,
    ddr=0,
    endian=0,
    csn_sel=1,  # one-hot CS enable; 0 selects no device (CSn never asserts)
):
    v = prescaler & 0xFF
    v |= (addr_len4 & 0x1) << 8
    v |= (dummy & 0x3F) << 9
    v |= (cmd_mode & 0x3) << 15
    v |= (addr_mode & 0x3) << 17
    v |= (data_mode & 0x3) << 19
    v |= (sck_mode & 0x1) << 21
    v |= (dir_write & 0x1) << 22
    v |= (crm & 0x1) << 23
    v |= (ddr & 0x1) << 24
    v |= (endian & 0x1) << 25
    v |= (csn_sel & 0xF) << 26
    return v


def unpack_cfg0(v: int) -> dict:
    return {
        "prescaler": v & 0xFF,
        "addr_len4": (v >> 8) & 0x1,
        "dummy": (v >> 9) & 0x3F,
        "cmd_mode": (v >> 15) & 0x3,
        "addr_mode": (v >> 17) & 0x3,
        "data_mode": (v >> 19) & 0x3,
        "sck_mode": (v >> 21) & 0x1,
        "dir_write": (v >> 22) & 0x1,
        "crm": (v >> 23) & 0x1,
        "ddr": (v >> 24) & 0x1,
        "endian": (v >> 25) & 0x1,
        "csn_sel": (v >> 26) & 0xF,
    }


def bytes_to_words(data: bytes, endian: int = 0) -> list:
    """Pack a byte stream into 32-bit DR words (endian 0: byte0 -> [31:24])."""
    words = []
    for i in range(0, len(data), 4):
        chunk = list(data[i : i + 4]) + [0] * (4 - len(data[i : i + 4]))
        if endian == 0:  # big endian
            w = (chunk[0] << 24) | (chunk[1] << 16) | (chunk[2] << 8) | chunk[3]
        else:  # little endian
            w = (chunk[3] << 24) | (chunk[2] << 16) | (chunk[1] << 8) | chunk[0]
        words.append(w)
    return words


def words_to_bytes(words: list, nbytes: int, endian: int = 0) -> bytes:
    """Unpack DR words back into a byte stream, truncated to nbytes."""
    out = bytearray()
    for w in words:
        if endian == 0:
            out += bytes([(w >> 24) & 0xFF, (w >> 16) & 0xFF, (w >> 8) & 0xFF, w & 0xFF])
        else:
            out += bytes([w & 0xFF, (w >> 8) & 0xFF, (w >> 16) & 0xFF, (w >> 24) & 0xFF])
    return bytes(out[:nbytes])
