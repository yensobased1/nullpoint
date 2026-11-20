"""Optional Discord Rich Presence (off by default). Fails silently if Discord isn't running or no client ID."""
import asyncio
import queue
import threading


class Presence:
    def __init__(self):
        self.jobs = queue.Queue()
        self.thread = None

    def set(self, client_id, state):
        """state: text like 'Profile: VALORANT', or None to clear / stop."""
        if not client_id or not str(client_id).isdigit():
            return
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._run, args=(str(client_id),), daemon=True)
            self.thread.start()
        self.jobs.put(state)

    def stop(self):
        if self.thread and self.thread.is_alive():
            self.jobs.put(StopIteration)

    def _run(self, client_id):
        asyncio.set_event_loop(asyncio.new_event_loop())
        rpc = None
        while True:
            state = self.jobs.get()
            if state is StopIteration:
                break
            try:
                if rpc is None:
                    from pypresence import Presence as RPC
                    rpc = RPC(client_id)
                    rpc.connect()
                if state is None:
                    rpc.clear()
                else:
                    rpc.update(details="Using Nullpoint", state=state[:120])
            except Exception:
                rpc = None  # Discord closed / not installed: stay quiet, retry on the next update
        try:
            if rpc:
                rpc.close()
        except Exception:  # nosec B110 - closing a dead Discord connection: nothing left to do
            pass
