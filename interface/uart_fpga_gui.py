"""
UART FPGA Bridge GUI
=====================
Simple GUI for sending/receiving UART data (8N1) to/from an FPGA that implements
a QSPI-based register interface.

Protocol:
  - PC sends 1 ADDR byte.
      MSB = 1 -> WRITE mode
      MSB = 0 -> READ mode
  - READ mode:  FPGA responds with 4 data bytes.
  - WRITE mode: PC sends 4 data bytes, FPGA responds with 1 ACK byte.

Requires: pyserial  (pip install pyserial)
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import serial
import serial.tools.list_ports
import threading
import queue
import time

BAUD_RATES = [1200, 2400, 4800, 9600, 19200, 38400, 57600,
              115200, 230400, 460800, 921600]


class UartFpgaGui:
    def __init__(self, root):
        self.root = root
        root.title("UART FPGA Bridge (8N1)")
        root.geometry("720x600")

        self.ser = None
        self.busy = False
        self.result_queue = queue.Queue()

        self._build_ui()
        self.refresh_ports()
        self.root.after(100, self._poll_queue)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self):
        conn_frame = ttk.LabelFrame(self.root, text="Serial Connection")
        conn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var,
                                        width=18, state="readonly")
        self.port_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(conn_frame, text="Refresh", command=self.refresh_ports).grid(
            row=0, column=2, padx=5, pady=5)

        ttk.Label(conn_frame, text="Baud:").grid(row=0, column=3, padx=5, pady=5, sticky="w")
        self.baud_var = tk.StringVar(value="115200")
        ttk.Combobox(conn_frame, textvariable=self.baud_var, width=10,
                     values=[str(b) for b in BAUD_RATES], state="readonly").grid(
            row=0, column=4, padx=5, pady=5)

        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self.toggle_connect)
        self.connect_btn.grid(row=0, column=5, padx=5, pady=5)

        self.status_var = tk.StringVar(value="Disconnected")
        self.status_lbl = ttk.Label(conn_frame, textvariable=self.status_var, foreground="red")
        self.status_lbl.grid(row=0, column=6, padx=10)

        trans_frame = ttk.LabelFrame(self.root, text="Transaction (UART 8N1)")
        trans_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(trans_frame, text="Mode:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.mode_var = tk.StringVar(value="read")
        ttk.Radiobutton(trans_frame, text="Read  (ADDR MSB = 0)", variable=self.mode_var,
                        value="read", command=self._on_mode_change).grid(
            row=0, column=1, padx=5, sticky="w")
        ttk.Radiobutton(trans_frame, text="Write (ADDR MSB = 1)", variable=self.mode_var,
                        value="write", command=self._on_mode_change).grid(
            row=0, column=2, padx=5, sticky="w")

        ttk.Label(trans_frame, text="Address (hex, 00-7F, 7-bit):").grid(
            row=1, column=0, padx=5, pady=5, sticky="w")
        self.addr_var = tk.StringVar(value="00")
        ttk.Entry(trans_frame, textvariable=self.addr_var, width=10).grid(
            row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(trans_frame, text="Write data (hex, 4 bytes, e.g. DEADBEEF):").grid(
            row=2, column=0, padx=5, pady=5, sticky="w")
        self.wdata_var = tk.StringVar(value="00000000")
        self.wdata_entry = ttk.Entry(trans_frame, textvariable=self.wdata_var, width=20)
        self.wdata_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="w")

        self.send_btn = ttk.Button(trans_frame, text="Send", command=self.send_transaction)
        self.send_btn.grid(row=3, column=0, padx=5, pady=10, sticky="w")

        self._on_mode_change()

        result_frame = ttk.LabelFrame(self.root, text="Last Result")
        result_frame.pack(fill="x", padx=10, pady=5)
        self.result_var = tk.StringVar(value="-")
        ttk.Label(result_frame, textvariable=self.result_var, font=("Consolas", 10),
                  justify="left").pack(anchor="w", padx=5, pady=5)

        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

    def _on_mode_change(self):
        if self.mode_var.get() == "write":
            self.wdata_entry.configure(state="normal")
        else:
            self.wdata_entry.configure(state="disabled")

    # --------------------------------------------------------- Connection ---
    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])
        self._log(f"Found {len(ports)} port(s): {', '.join(ports) if ports else 'none'}")

    def toggle_connect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None
            self.status_var.set("Disconnected")
            self.status_lbl.configure(foreground="red")
            self.connect_btn.configure(text="Connect")
            self._log("Disconnected from port.")
            return

        port = self.port_var.get()
        if not port:
            self._log("ERROR: no port selected.")
            return
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=int(self.baud_var.get()),
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0,
            )
            self.status_var.set(f"Connected: {port}")
            self.status_lbl.configure(foreground="green")
            self.connect_btn.configure(text="Disconnect")
            self._log(f"Connected to {port} @ {self.baud_var.get()} baud, 8N1.")
        except serial.SerialException as e:
            self._log(f"ERROR: could not open {port}: {e}")

    def _on_close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.root.destroy()

    # ------------------------------------------------------------ Parsing ---
    def _parse_addr(self):
        raw = self.addr_var.get().strip()
        try:
            val = int(raw, 16)
        except ValueError:
            self._log("ERROR: address must be valid hex.")
            return None
        if not (0 <= val <= 0x7F):
            self._log("ERROR: address must be within 0x00-0x7F (7-bit field, MSB is mode flag).")
            return None
        return val

    def _parse_wdata(self):
        raw = self.wdata_var.get().strip().replace(" ", "")
        if len(raw) != 8:
            self._log("ERROR: write data must be exactly 4 bytes (8 hex characters).")
            return None
        try:
            val = bytes.fromhex(raw)
        except ValueError:
            self._log("ERROR: write data must be valid hex.")
            return None
        return val

    # --------------------------------------------------------- Transaction ---
    def send_transaction(self):
        if self.busy:
            return
        if not (self.ser and self.ser.is_open):
            self._log("ERROR: not connected.")
            return

        addr = self._parse_addr()
        if addr is None:
            return

        mode = self.mode_var.get()
        self.busy = True
        self.send_btn.configure(state="disabled")

        if mode == "write":
            wdata = self._parse_wdata()
            if wdata is None:
                self.busy = False
                self.send_btn.configure(state="normal")
                return
            addr_byte = addr | 0x80
            threading.Thread(target=self._do_write, args=(addr_byte, wdata), daemon=True).start()
        else:
            addr_byte = addr & 0x7F
            threading.Thread(target=self._do_read, args=(addr_byte,), daemon=True).start()

    @staticmethod
    def _bin_str(data_bytes):
        """Format bytes as binary, clearly separated and labeled per byte,
        e.g. b'\\xDE\\xAD' -> 'B0=11011110 B1=10101101'"""
        return " ".join(f"B{i}={b:08b}" for i, b in enumerate(data_bytes))

    def _do_read(self, addr_byte):
        try:
            self.ser.reset_input_buffer()
            self.ser.write(bytes([addr_byte]))
            self.result_queue.put(("log", f"TX ADDR: 0x{addr_byte:02X} "
                                           f"({addr_byte:08b}) [READ mode]"))

            response = self.ser.read(5)
            if len(response) < 5:
                self.result_queue.put(("log", f"ERROR: timeout, only received "
                                               f"{len(response)}/5 bytes "
                                               f"(expected 1 ACK + 4 data)."))
                return

            ack_byte, data = response[0], response[1:5]
            bin_str = self._bin_str(data)
            hex_str = " ".join(f"0x{b:02X}" for b in data)
            data_u32 = int.from_bytes(data, byteorder="big")
            self.result_queue.put(("log", f"RX ACK: 0x{ack_byte:02X} ({ack_byte:08b})"))
            self.result_queue.put(("log", f"RX DATA: {hex_str}  |  {bin_str}"))
            self.result_queue.put(("result",
                f"Mode: READ\nAddress: 0x{addr_byte:02X}\n"
                f"ACK: 0x{ack_byte:02X} ({ack_byte:08b})\n"
                f"Data (hex): {hex_str}\nData (bin): {bin_str}\n"
                f"Data as 32-bit (high byte first): 0x{data_u32:08X}"))
        except serial.SerialException as e:
            self.result_queue.put(("log", f"ERROR: {e}"))
        finally:
            self.result_queue.put(("done", None))

    def _do_write(self, addr_byte, wdata):
        try:
            self.ser.reset_input_buffer()
            self.ser.write(bytes([addr_byte]))
            self.result_queue.put(("log", f"TX ADDR: 0x{addr_byte:02X} "
                                           f"({addr_byte:08b}) [WRITE mode]"))

            self.ser.write(wdata)
            bin_str = self._bin_str(wdata)
            hex_str = " ".join(f"0x{b:02X}" for b in wdata)
            self.result_queue.put(("log", f"TX DATA: {hex_str}  |  {bin_str}"))

            # Test-bridge firmware echoes the 4 data bytes back, then sends
            # 1 ACK byte, so we read 5 bytes total here. (A real FPGA design
            # per the original protocol spec would only send 1 ACK byte --
            # adjust this back to self.ser.read(1) once you move off the
            # ESP32 test bridge.)
            response = self.ser.read(5)
            if len(response) < 5:
                self.result_queue.put(("log", f"ERROR: timeout, only received "
                                               f"{len(response)}/5 response bytes "
                                               f"(expected 4 echoed bytes + 1 ACK)."))
                return

            echoed, ack_byte = response[:4], response[4]
            echoed_hex = " ".join(f"0x{b:02X}" for b in echoed)
            echoed_bin = self._bin_str(echoed)
            match = "MATCH" if echoed == wdata else "MISMATCH"
            sent_u32 = int.from_bytes(wdata, byteorder="big")
            echoed_u32 = int.from_bytes(echoed, byteorder="big")
            self.result_queue.put(("log", f"RX ECHO: {echoed_hex}  |  {echoed_bin}  ({match})"))
            self.result_queue.put(("log", f"RX ACK: 0x{ack_byte:02X} ({ack_byte:08b})"))
            self.result_queue.put(("result",
                f"Mode: WRITE\nAddress: 0x{addr_byte:02X}\n"
                f"Sent data (hex): {hex_str}\nSent data (bin): {bin_str}\n"
                f"Sent as 32-bit (high byte first): 0x{sent_u32:08X}\n"
                f"Echoed back (hex): {echoed_hex}\nEchoed back (bin): {echoed_bin}  [{match}]\n"
                f"Echoed as 32-bit (high byte first): 0x{echoed_u32:08X}\n"
                f"ACK: 0x{ack_byte:02X} ({ack_byte:08b})"))
        except serial.SerialException as e:
            self.result_queue.put(("log", f"ERROR: {e}"))
        finally:
            self.result_queue.put(("done", None))

    # ------------------------------------------------------------- Queue ---
    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.result_queue.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "result":
                    self.result_var.set(payload)
                elif kind == "done":
                    self.busy = False
                    self.send_btn.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        self.log_text.see("end")


if __name__ == "__main__":
    root = tk.Tk()
    app = UartFpgaGui(root)
    root.mainloop()