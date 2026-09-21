"""Copy as pyblocks_controller.py beside a hub program; requires Pybricks 3.3+."""

from pybricks.tools import StopWatch, read_input_byte


class Controller:
    """Call update() in the control loop. Stale input becomes neutral after 500 ms."""

    def __init__(self, timeout=500):
        self.left_x = self.left_y = self.right_x = self.right_y = 0
        self.buttons = 0
        self.slider = 0
        self.timeout = timeout
        self._clock = StopWatch()
        self._buffer = bytearray()

    def update(self):
        for _ in range(128):
            value = read_input_byte()
            if value is None:
                break
            if value == 126:  # ~ starts a fresh frame after any partial packet.
                self._buffer = bytearray([value])
            elif self._buffer:
                self._buffer.append(value)
                if value == 10:
                    self._accept()
                    self._buffer = bytearray()
                elif len(self._buffer) >= 16:
                    self._buffer = bytearray()
        if self._clock.time() > self.timeout:
            self.left_x = self.left_y = self.right_x = self.right_y = 0
            self.buttons = 0
            self.slider = 0
        return self

    def _accept(self):
        frame = self._buffer
        if len(frame) != 16:
            return
        try:
            axes = [
                (int(bytes(frame[index : index + 2]), 16) - 100) / 100
                for index in (1, 3, 5, 7)
            ]
            buttons = int(bytes(frame[9:13]), 16)
            slider = int(bytes(frame[13:15]), 16) / 100
            if (
                any(abs(value) > 1 for value in axes)
                or not 0 <= slider <= 1
                or not 0 <= buttons <= 65535
            ):
                return
        except ValueError:
            return
        self.left_x, self.left_y, self.right_x, self.right_y = axes
        self.buttons, self.slider = buttons, slider
        self._clock.reset()
