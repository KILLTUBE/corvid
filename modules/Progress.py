import time

class Progress:
    """Progress reporter for the conversion pipeline.

    Callbacks are optional — when no callback is provided, messages go to print().
    This allows modules to report progress without depending on the UI layer.
    """

    def __init__(self, on_log=None, on_overall=None, on_current=None, throttle_ms=50):
        self._on_log = on_log
        self._on_overall = on_overall
        self._on_current = on_current
        self._throttle_s = throttle_ms / 1000.0
        self._last_current = 0.0

    def log(self, message):
        if self._on_log:
            self._on_log(message)
        else:
            print(message)

    def overall(self, step, total):
        if self._on_overall:
            self._on_overall(step, total)

    def current(self, step, total):
        if self._on_current:
            now = time.monotonic()
            # always fire on the last item, throttle everything else
            if step >= total or now - self._last_current >= self._throttle_s:
                self._last_current = now
                self._on_current(step, total)


# Default instance for modules that don't receive an explicit progress object.
_default = Progress()
