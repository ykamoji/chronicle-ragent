import threading
import time

# -----------------------------
# RATE LIMITER
# -----------------------------

class RateLimiter:
    def __init__(self, max_calls, period):
        self.max_calls = max_calls
        self.period = period
        self.lock = threading.Lock()
        self.calls = []

    def acquire(self):
        while True:
            with self.lock:
                now = time.time()

                # remove calls older than window
                self.calls = [t for t in self.calls if now - t < self.period]

                if len(self.calls) < self.max_calls:
                    self.calls.append(now)
                    return

                # calculate sleep time
                sleep_time = self.period - (now - self.calls[0])

            time.sleep(sleep_time)