import multiprocessing
import time
import logging
import signal

from telegram import BotAPI

class ReceiveProcess(multiprocessing.Process):
    def __init__(self, token, q):
        multiprocessing.Process.__init__(self)
        self.q = q
        self.api = BotAPI(token)
        self.daemon = True
        self.offset = None

    def fetch_updates(self):
        logging.log("Fetching updates")
        updates = self.api.get_updates(offset = self.offset, timeout = 120) if self.offset != None else self.api.get_updates(timeout = 120)
        if len(updates) > 0:
            self.offset = updates[len(updates) - 1].id + 1
        for update in updates: self.q.put(update)

    def run(self):
        signal.signal(signal.SIGINT, signal.SIG_IGN) # Make sure KeyboardInterrupts are not sent to this process
        try:
            while True:
                self.fetch_updates()
        except Exception as  e:
            logging.error("An exception occurred inside recv process:\n\t" + str(e))
        finally:
            self.q.put(None)
