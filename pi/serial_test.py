import argparse
import time
import sys

TESTS = [
    ('{"home":1}', '{"ok":1}'),
    ('{"ik":[180,0,60,-90]}', '{"ok":1}'),
    ('{"ik":[900,0,0,-90]}', '{"err":"unreachable"}'),
    ('{"grip":110}', '{"ok":1}'),
    ('not json', '{"err":"bad json"}'),
]

def run_serial_tests(port, tests=TESTS, timeout_lines=20):
    """Run a list of JSON command/expectation pairs on a serial‑like port.

    Args:
        port: Object with .write(bytes) and .readline() -> bytes (b'' on timeout).
        tests: Iterable of (cmd, expected) strings.
        timeout_lines: Max lines to read per command before giving up.

    Returns:
        List of dicts with keys: cmd, expected, reply, ok.
    """
    results = []
    for cmd, expected in tests:
        # Send the command terminated by newline
        port.write((cmd + '\n').encode())

        reply = None
        lines_read = 0
        while lines_read < timeout_lines:
            line_bytes = port.readline()
            # Decode safely, then strip surrounding whitespace
            line = line_bytes.decode(errors='replace').strip()
            lines_read += 1
            if line == '':
                continue          # skip empty lines
            if line.startswith('{"state'):
                continue          # skip status broadcasts
            reply = line          # first non‑empty, non‑state line is the reply
            break

        results.append({
            "cmd": cmd,
            "expected": expected,
            "reply": reply,
            "ok": reply == expected
        })
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run serial servo tests")
    parser.add_argument('device', nargs='?', default='/dev/serial0',
                        help="Serial device path (default: %(default)s)")
    parser.add_argument('--baud', type=int, default=115200,
                        help="Baud rate (default: %(default)s)")
    args = parser.parse_args(argv)

    # Import pyserial only when the script is executed
    import serial
    ser = serial.Serial(args.device, args.baud, timeout=2)
    time.sleep(0.5)          # let the device settle
    ser.reset_input_buffer()
    results = run_serial_tests(ser)
    ser.close()

    passed = 0
    for t in results:
        status = 'PASS' if t['ok'] else 'FAIL'
        print(f"{status} {t['cmd']} -> {t['reply']}")
        if t['ok']:
            passed += 1
    total = len(results)
    print(f"{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == '__main__':
    raise SystemExit(main())