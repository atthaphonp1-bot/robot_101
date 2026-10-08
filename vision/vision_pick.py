"""Camera + OpenCV: find colored objects, then pick & place them with the arm.

Examples
  python vision_pick.py --source sim_camera.png --sim-calib --dry-run   # image saved from the web sim
  python vision_pick.py --source 0 --calibrate                           # webcam: click 4 points -> calib.json
  python vision_pick.py --source 0 --ws ws://192.168.4.1:81 --color red  # pick red objects with the real arm
  python vision_pick.py --source http://<esp32-cam-ip>:81/stream ...     # ESP32-CAM MJPEG stream
"""
import argparse
import json
import sys
import time

import cv2

from calib import compute_homography, load_calibration, pixel_to_robot, save_calibration
from detect import DEFAULT_COLORS, detect_objects
from planner import pick_place_commands

# web sim top camera: orthographic 500 x 500 mm centred on robot (x=100, y=0), image top = +X, image left = +Y
SIM_SPAN, SIM_CX = 500.0, 100.0


def sim_homography(w, h):
    px = [(0, 0), (w, 0), (w, h), (0, h)]
    rb = [(SIM_CX + SIM_SPAN / 2, SIM_SPAN / 2), (SIM_CX + SIM_SPAN / 2, -SIM_SPAN / 2),
          (SIM_CX - SIM_SPAN / 2, -SIM_SPAN / 2), (SIM_CX - SIM_SPAN / 2, SIM_SPAN / 2)]
    return compute_homography(px, rb)


def open_source(src):
    cap = cv2.VideoCapture(int(src) if src.isdigit() else src)
    if not cap.isOpened():
        sys.exit(f"เปิดกล้อง/สตรีมไม่ได้: {src}")
    return cap


def grab(args, cap):
    if cap is None:
        img = cv2.imread(args.source)
        if img is None:
            sys.exit(f"อ่านไฟล์ภาพไม่ได้: {args.source}")
        return img
    ok, frame = cap.read()
    if not ok:
        sys.exit("อ่านเฟรมจากกล้องไม่ได้")
    return frame


def calibrate(args, cap):
    """Click 4 floor points in the image, then type their robot (x, y) in mm."""
    img = grab(args, cap)
    pts = []
    win = "calibrate: click 4 points (Esc = cancel)"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, lambda e, u, v, *_: pts.append((u, v)) if e == cv2.EVENT_LBUTTONDOWN and len(pts) < 4 else None)
    while len(pts) < 4:
        view = img.copy()
        for i, p in enumerate(pts):
            cv2.circle(view, p, 6, (0, 255, 255), -1)
            cv2.putText(view, str(i + 1), (p[0] + 8, p[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.imshow(win, view)
        if cv2.waitKey(30) == 27:
            sys.exit("ยกเลิก")
    cv2.destroyAllWindows()
    robot = []
    for i, p in enumerate(pts, 1):
        x, y = map(float, input(f"จุด {i} pixel {p} -> robot x,y (mm): ").split(","))
        robot.append((x, y))
    H = compute_homography(pts, robot)
    save_calibration(args.calib, H)
    print(f"บันทึก {args.calib} แล้ว")


class Arm:
    """Sends JSON commands over WebSocket and waits until the firmware reports moving=false."""

    def __init__(self, url):
        import websocket  # pip install websocket-client
        self.ws = websocket.create_connection(url, timeout=10)

    def send(self, cmd, timeout=15):
        self.ws.send(json.dumps(cmd))
        print("  →", cmd)
        time.sleep(0.15)
        end = time.time() + timeout
        while time.time() < end:
            msg = json.loads(self.ws.recv())
            if "err" in msg:
                raise RuntimeError(f"แขนตอบ error: {msg['err']} ({cmd})")
            if "state" in msg and not msg.get("moving", True):
                return
        raise TimeoutError(f"รอนานเกินไป: {cmd}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="0", help="webcam index, stream URL or image file")
    ap.add_argument("--calib", default="calib.json")
    ap.add_argument("--calibrate", action="store_true", help="create calib.json by clicking 4 points")
    ap.add_argument("--sim-calib", action="store_true", help="use the web sim's known top-camera mapping")
    ap.add_argument("--color", default="all", choices=["all", *DEFAULT_COLORS])
    ap.add_argument("--place", default="30,170", help="place position x,y (mm)")
    ap.add_argument("--ws", default="ws://192.168.4.1:81")
    ap.add_argument("--dry-run", action="store_true", help="print commands, do not connect")
    ap.add_argument("--no-gui", action="store_true")
    args = ap.parse_args()

    is_image = not args.source.isdigit() and not args.source.startswith(("http", "rtsp"))
    cap = None if is_image else open_source(args.source)
    if args.calibrate:
        return calibrate(args, cap)

    img = grab(args, cap)
    H = sim_homography(img.shape[1], img.shape[0]) if args.sim_calib else load_calibration(args.calib)
    colors = DEFAULT_COLORS if args.color == "all" else {args.color: DEFAULT_COLORS[args.color]}
    found = detect_objects(img, colors)
    for d in found:
        d["x"], d["y"] = pixel_to_robot(H, d["u"], d["v"])
        print(f"{d['color']:>6}  pixel ({d['u']:.0f},{d['v']:.0f})  ->  robot ({d['x']:.1f}, {d['y']:.1f}) mm")
    if not args.no_gui:
        view = img.copy()
        for d in found:
            c = (int(d["u"]), int(d["v"]))
            cv2.drawMarker(view, c, (255, 255, 255), cv2.MARKER_CROSS, 18, 2)
            cv2.putText(view, f"{d['color']} {d['x']:.0f},{d['y']:.0f}", (c[0] + 10, c[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.imshow("detections (any key)", view)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    if not found:
        return print("ไม่พบวัตถุ")

    px, py = map(float, args.place.split(","))
    arm = None if args.dry_run else Arm(args.ws)
    for level, d in enumerate(found):
        print(f"หยิบ {d['color']} ที่ ({d['x']:.0f}, {d['y']:.0f}) → วางชั้น {level + 1}")
        for cmd in pick_place_commands(d["x"], d["y"], px, py, place_z=17 + level * 30):
            arm.send(cmd) if arm else print("  ", json.dumps(cmd))
    if arm:
        arm.send({"home": 1})


if __name__ == "__main__":
    main()
