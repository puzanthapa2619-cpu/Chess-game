"""Chess clock with optional Fischer increment."""
import time


class ChessTimer:
    """Two-sided countdown clock. Times stored in seconds (float)."""

    def __init__(self, minutes: float = 10, increment: float = 0):
        self.initial = minutes * 60.0
        self.increment = float(increment)
        self.white_time = self.initial
        self.black_time = self.initial
        self.turn = True  # True = white
        self.running = False
        self._last = None

    def start(self):
        if not self.running:
            self.running = True
            self._last = time.time()

    def stop(self):
        self.update()
        self.running = False
        self._last = None

    def switch(self):
        """Called after a move: add increment to the player who just moved,
        then switch clock."""
        self.update()
        if self.turn:
            self.white_time += self.increment
        else:
            self.black_time += self.increment
        self.turn = not self.turn
        self._last = time.time() if self.running else None

    def update(self):
        if not self.running or self._last is None:
            return
        now = time.time()
        elapsed = now - self._last
        self._last = now
        if self.turn:
            self.white_time = max(0.0, self.white_time - elapsed)
        else:
            self.black_time = max(0.0, self.black_time - elapsed)

    def flagged(self):
        """Returns 'white' / 'black' / None."""
        self.update()
        if self.white_time <= 0:
            return "white"
        if self.black_time <= 0:
            return "black"
        return None

    @staticmethod
    def format(t: float) -> str:
        t = max(0, int(t))
        m, s = divmod(t, 60)
        return f"{m:02d}:{s:02d}"
