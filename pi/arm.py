import argparse
import json
import sys


def parse_cli(argv):
    parser = argparse.ArgumentParser(
        prog='arm.py', description='Control the robot arm over serial (USB: /dev/ttyUSB0, Pi UART: /dev/serial0).',
        epilog='examples: arm.py home | arm.py ik 180 0 100 | arm.py --port /dev/serial0 status | arm.py run poses.json --loop')
    parser.add_argument('--port', default='/dev/ttyUSB0', help='serial device (default /dev/ttyUSB0)')
    parser.add_argument('--baud', type=int, default=115200)
    # --port / --baud are also accepted after the subcommand (arm.py home --port /dev/serial0)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--port', default=argparse.SUPPRESS)
    common.add_argument('--baud', type=int, default=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest='cmd', required=True)

    # home
    subparsers.add_parser(parents=[common], name='home')
    # stop
    subparsers.add_parser(parents=[common], name='stop')
    # status
    subparsers.add_parser(parents=[common], name='status')
    # repl
    subparsers.add_parser(parents=[common], name='repl')
    # j
    pj = subparsers.add_parser(parents=[common], name='j')
    pj.add_argument('angles', nargs=6, type=float)
    # ik
    pik = subparsers.add_parser(parents=[common], name='ik')
    pik.add_argument('x', type=float)
    pik.add_argument('y', type=float)
    pik.add_argument('z', type=float)
    pik.add_argument('pitch', nargs='?', type=float, default=-90.0)
    # grip
    pg = subparsers.add_parser(parents=[common], name='grip')
    pg.add_argument('value', type=float)
    # speed
    ps = subparsers.add_parser(parents=[common], name='speed')
    ps.add_argument('value', type=float)
    # run
    pr = subparsers.add_parser(parents=[common], name='run')
    pr.add_argument('path')
    pr.add_argument('--loop', action='store_true')
    pr.add_argument('--delay', type=float, default=0.3)

    ns = parser.parse_args(argv)
    result = {'port': ns.port, 'baud': ns.baud, 'cmd': ns.cmd}
    args = {}
    if ns.cmd == 'home':
        args = {}
    elif ns.cmd == 'stop':
        args = {}
    elif ns.cmd == 'status':
        args = {}
    elif ns.cmd == 'repl':
        args = {}
    elif ns.cmd == 'j':
        args = {'angles': list(ns.angles)}
    elif ns.cmd == 'ik':
        args = {
            'x': ns.x,
            'y': ns.y,
            'z': ns.z,
            'pitch': ns.pitch,
        }
    elif ns.cmd == 'grip':
        args = {'value': ns.value}
    elif ns.cmd == 'speed':
        args = {'value': ns.value}
    elif ns.cmd == 'run':
        args = {
            'path': ns.path,
            'loop': ns.loop,
            'delay': ns.delay,
        }
    result['args'] = args
    result['cmd'] = {'j': 'joints', 'ik': 'move_to'}.get(ns.cmd, ns.cmd)
    return result


def load_program(text):
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError('Program JSON must be a list')
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f'Item {i} is not a dict')
        if 'j' not in item:
            raise ValueError(f'Item {i} missing key "j"')
        val = item['j']
        if not isinstance(val, list) or len(val) != 6:
            raise ValueError(f'Item {i}["j"] must be a list of exactly 6 numbers')
        for n in val:
            if not isinstance(n, (int, float)):
                raise ValueError(f'Item {i}["j"] contains non-number: {n}')
    return data


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    opts = parse_cli(argv)

    # Delayed imports
    import time
    import serial
    from arm_core import Arm, ArmError

    port = serial.Serial(opts['port'], opts['baud'], timeout=2)
    time.sleep(0.5)
    port.reset_input_buffer()
    arm = Arm(port)

    def do_command(o):
        cmd = o['cmd']
        args = o['args']
        if cmd == 'home':
            reply = arm.home()
        elif cmd == 'stop':
            reply = arm.stop()
        elif cmd == 'status':
            reply = arm.status()
        elif cmd == 'joints':
            reply = arm.joints(**args)
        elif cmd == 'move_to':
            reply = arm.move_to(**args)
        elif cmd == 'grip':
            reply = arm.grip(**args)
        elif cmd == 'speed':
            reply = arm.speed(**args)
        else:
            raise ValueError(f'Unsupported command {cmd}')
        print(json.dumps(reply))

    try:
        if opts['cmd'] == 'run':
            path = opts['args']['path']
            loop = opts['args']['loop']
            delay = opts['args']['delay']
            poses = load_program(open(path).read())
            while True:
                n = arm.run_program(poses, wait=True, delay=delay)
                print(f'ran {n} poses')
                if not loop:
                    break
        elif opts['cmd'] == 'repl':
            print('Available commands: home stop status j ik grip speed run repl quit/exit')
            while True:
                try:
                    line = input('arm> ').strip()
                except EOFError:
                    break
                if not line:
                    continue
                if line in ('quit', 'exit'):
                    break
                if line.startswith('{'):
                    try:
                        j = json.loads(line)
                        reply = arm.send(j)
                        print(json.dumps(reply))
                    except Exception as e:
                        print(f'error: {e}')
                    continue
                # Disallow run/repl inside repl
                parts = line.split()
                if parts and parts[0] in ('run', 'repl'):
                    print('error: run/repl not allowed inside repl')
                    continue
                try:
                    subopts = parse_cli(['--port', opts['port']] + parts)
                except SystemExit:
                    # argparse error; just continue
                    continue
                if subopts['cmd'] == 'run':
                    print('error: run not allowed inside repl')
                    continue
                try:
                    do_command(subopts)
                except (ArmError, ValueError) as e:
                    print(f'error: {e}')
        else:
            do_command(opts)
    except ArmError as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        # Should not reach here outside run loop, but handle gracefully
        try:
            arm.stop()
        except Exception:
            pass
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())