"""Robot arm controller over a line‑based serial link.

Only the Python standard library (json, time) is used.  The serial port
object is injected and must provide ``write(bytes)`` and
``readline() -> bytes`` (empty bytes indicate a timeout).
"""

import json
import time
from typing import Any, Dict, Iterable, List, Mapping, Sequence


class ArmError(Exception):
    """Raised for any error reported by the arm or protocol problems."""
    pass


class Arm:
    def __init__(
        self,
        port,
        sleep=time.sleep,
        clock=time.monotonic,
        poll_interval: float = 0.1,
        timeout: float = 15.0,
        max_lines: int = 50,
    ):
        # store every argument as an attribute of the same name
        self.port = port
        self.sleep = sleep
        self.clock = clock
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.max_lines = max_lines

    # --------------------------------------------------------------------- #
    # Low‑level communication
    # --------------------------------------------------------------------- #
    def send(self, cmd: Mapping[str, Any]) -> Dict[str, Any]:
        """Send a JSON command and return the first valid reply dict.

        The command dictionary is JSON‑encoded in the most compact form,
        a trailing newline is added and the resulting bytes are written to
        the port.

        The method then reads up to ``self.max_lines`` lines from the
        port, discarding:

        * empty lines,
        * lines that do not start with ``'{'``,
        * lines that start with ``'{"state"'`` (status‑only messages).

        The first line that successfully parses to a ``dict`` is taken as
        the reply.  If the reply contains the key ``'err'`` an
        ``ArmError`` is raised with the error string.  If no suitable
        reply is found an ``ArmError('no reply')`` is raised.
        """
        # encode and write the command
        line = json.dumps(cmd, separators=(',', ':')) + "\n"
        self.port.write(line.encode())

        # read and filter lines
        for _ in range(self.max_lines):
            raw = self.port.readline()
            if raw == b"":          # timeout / no more data
                break

            text = raw.decode(errors="replace").strip()
            if not text:
                continue
            if not text.startswith("{"):
                continue
            if text.startswith('{"state"'):
                continue

            try:
                obj = json.loads(text)
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue

            # we have a candidate reply
            if "err" in obj:
                raise ArmError(str(obj["err"]))
            return obj

        # no reply found after exhausting the allowed lines
        raise ArmError("no reply")

    # --------------------------------------------------------------------- #
    # High‑level commands
    # --------------------------------------------------------------------- #
    def home(self) -> Dict[str, Any]:
        return self.send({"home": 1})

    def joints(self, angles: Sequence[float]) -> Dict[str, Any]:
        if len(angles) != 6:
            raise ValueError("exactly 6 joint angles required")
        return self.send({"j": [float(a) for a in angles]})

    def move_to(self, x: float, y: float, z: float, pitch: float = -90) -> Dict[str, Any]:
        return self.send({"ik": [x, y, z, pitch]})

    def grip(self, value: Any) -> Dict[str, Any]:
        return self.send({"grip": value})

    def speed(self, value: Any) -> Dict[str, Any]:
        return self.send({"speed": value})

    def stop(self) -> Dict[str, Any]:
        return self.send({"stop": 1})

    def status(self) -> Dict[str, Any]:
        return self.send({"status": 1})

    def wait_idle(self) -> Dict[str, Any]:
        """Block until the arm reports ``moving == False`` or timeout."""
        start = self.clock()
        while True:
            s = self.status()
            if not s.get("moving"):
                return s
            if self.clock() - start > self.timeout:
                raise ArmError("timeout")
            self.sleep(self.poll_interval)

    def run_program(
        self,
        poses: Iterable[Mapping[str, Any]],
        wait: bool = True,
        delay: float = 0.0,
    ) -> int:
        """Execute a sequence of joint‑pose dictionaries.

        Each pose must contain the key ``'j'`` with an iterable of six
        joint angles.  The method returns the number of poses that were
        processed.
        """
        count = 0
        for p in poses:
            self.joints(p["j"])
            if wait:
                self.wait_idle()
            if delay > 0:
                self.sleep(delay)
            count += 1
        return count