"""APB driver: pulls ApbItem transactions from the sequencer and runs them
through the ApbBfm, writing results (rdata, wait_states) back into the item."""

from pyuvm import ConfigDB, uvm_driver

from seq_items import ApbKind


class ApbDriver(uvm_driver):
    def build_phase(self):
        self.bfm = ConfigDB().get(self, "", "BFM")

    async def run_phase(self):
        while True:
            item = await self.seq_item_port.get_next_item()
            if item.kind == ApbKind.WRITE:
                item.wait_states = await self.bfm.write(item.addr, item.data)
            else:
                item.rdata, item.wait_states = await self.bfm.read(item.addr)
            self.logger.debug(str(item))
            self.seq_item_port.item_done()
