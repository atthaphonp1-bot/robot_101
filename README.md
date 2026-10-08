# Robot Arm 101

แขนกล 6DOF งบประหยัด: Simulator 3D บนเว็บ, firmware ESP32 (Wokwi), กล้อง + OpenCV, ควบคุมผ่าน MQTT/มือถือ

- **Simulator:** https://atthaphonp1-bot.github.io/robot_101/
- **แดชบอร์ดมือถือ:** https://atthaphonp1-bot.github.io/robot_101/remote.html

| โฟลเดอร์ | เนื้อหา |
|---|---|
| `sim/` | Simulator 3D (Three.js) + แดชบอร์ดมือถือ (MQTT) |
| `firmware/` | ESP32 firmware, Wokwi diagram, PlatformIO |
| `vision/` | OpenCV หาวัตถุ + หยิบ (`vision_pick.py`) |
| `ROBOT_ARM_GUIDE.md` | คู่มือเริ่มต้น |

> broker สาธารณะใครก็ส่งคำสั่งได้ — เปลี่ยน topic prefix เป็นชื่อเฉพาะ หรือใช้ broker ส่วนตัว
