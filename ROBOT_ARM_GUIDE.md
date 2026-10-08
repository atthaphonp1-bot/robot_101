# Robot Arm 101: คู่มือเริ่มต้นแบบงบไม่สูง

> เป้าหมาย: สร้างแขนกล 4–6 แกน (DOF) ที่ควบคุมได้ทั้งจากปุ่มบนตัว, คอมพิวเตอร์ และมือถือ/เว็บ
> โดย **เริ่มเขียนและทดสอบโค้ดใน Simulator ก่อน** แล้วค่อยย้ายไปฮาร์ดแวร์จริง
>
> ราคาในเอกสารนี้เป็นราคาประมาณ (Shopee/Lazada/AliExpress) อาจต่างไปตามร้านและช่วงเวลา

---

## 0. ภาพรวมระบบ

```
 [มือถือ / Web Browser]
          │  WiFi (WebSocket / MQTT)
          ▼
 [ESP32  ── Firmware]  ◄── USB Serial ──► [PC: Python / ROS 2 / Simulator]
    │ I2C        │ GPIO
    ▼            ▼
 [PCA9685]   [OLED, ปุ่ม, Joystick, E-Stop]
    │ PWM
    ▼
 [Servo x6] ◄── [Power Supply 5–6V แยก]
```

**หลักสำคัญ:** ออกแบบให้ "คำสั่ง" (command protocol) เป็นมาตรฐานเดียว
เช่น `{"j":[90,45,120,90,90,30]}` แล้วให้ทั้ง Simulator และบอร์ดจริงรับคำสั่งเดียวกัน
→ โค้ดที่ทดสอบใน sim ใช้กับของจริงได้ทันที

---

## 1. โครงสร้างของ Robot Arm

### 1.1 ความรู้พื้นฐานที่ควรรู้

| คำ | ความหมาย |
|---|---|
| DOF (Degree of Freedom) | จำนวนข้อต่อที่ขยับได้อิสระ — 4 DOF พอสำหรับหยิบ-วาง, 6 DOF ปรับมุมปลายมือได้ครบ |
| Joint / Link | ข้อต่อ / ท่อนแขนระหว่างข้อต่อ |
| End-effector | ปลายแขน เช่น กริปเปอร์ หัวดูด ปากกา |
| Workspace | พื้นที่ที่ปลายแขนเอื้อมถึง |
| Payload | น้ำหนักที่ยกได้ (แขนงานอดิเรกส่วนใหญ่ 100–500 g) |
| Torque | แรงบิด — ข้อต่อที่ไหล่ (shoulder) ต้องการแรงบิดมากที่สุด |

ประเภทที่พบบ่อย: **Articulated** (แบบแขนคน, นิยมสุด), **SCARA** (เคลื่อนแนวราบ เร็ว), **Delta** (หยิบวางเร็วมาก), **Cartesian** (แบบเครื่อง 3D printer)

### 1.2 ตัวเลือกโครงสร้างตามงบ

| ตัวเลือก | DOF | มอเตอร์ | งบประมาณ (โดยประมาณ) | เหมาะกับ |
|---|---|---|---|---|
| **MeArm** (อะคริลิก/ไม้) | 4 | SG90 | ฿400–900 | เริ่มเรียนแบบถูกสุด แต่แรงน้อย สั่น |
| **Kit อะคริลิก/อลูมิเนียม 6DOF** | 6 | MG996R | ฿1,200–2,500 (ไม่รวมบอร์ด) | สมดุลราคา/ความสามารถ ⭐ แนะนำเริ่ม |
| **EEZYbotArm MK2** (พิมพ์ 3D) | 3+1 | MG996R | ฿600–1,200 + ค่าพิมพ์ | ถ้ามี 3D printer |
| **SO-ARM100 / SO-101** (โอเพนซอร์ส, LeRobot) | 6 | Feetech STS3215 (bus servo) | ~฿4,000–8,000 ต่อแขน | อยากต่อยอด AI / imitation learning |
| **Hiwonder xArm / LeArm** | 6 | Bus servo | ฿5,000–12,000 | อยากได้ของสำเร็จ แม่นกว่า |
| **PAROL6 / Thor** (stepper) | 6 | Stepper + gearbox | ฿15,000+ | ขั้นสูง แม่นยำ |

**คำแนะนำ:** เริ่มที่ **Kit 6DOF + MG996R** (ถูกและหาง่าย) หรือถ้ามีงบเพิ่มและสนใจ AI → **SO-101**

### 1.3 มอเตอร์: เลือกอะไรดี

| ชนิด | ข้อดี | ข้อเสีย |
|---|---|---|
| Servo PWM (SG90, MG90S, MG996R, DS3218) | ถูก ใช้ง่าย | ไม่มี feedback ตำแหน่ง, กระตุกได้ |
| **Bus Servo** (STS3215, LX-16A) | อ่านตำแหน่ง/อุณหภูมิ/โหลดกลับได้, ต่อพ่วงสายเดียว | แพงกว่า ต้องมีบอร์ดแปลง |
| Stepper + driver | แรงบิดสูง แม่น | ต้องมี homing/limit switch, ซับซ้อน |

---

## 2. วงจร, Driver, อุปกรณ์เสริม, จอแสดงผล

### 2.1 รายการอุปกรณ์หลัก (แบบ Servo PWM)

| อุปกรณ์ | หน้าที่ | ราคาประมาณ |
|---|---|---|
| **ESP32 DevKit** | สมองหลัก มี WiFi/Bluetooth ในตัว | ฿150–250 |
| **PCA9685** 16-ch | สร้าง PWM ให้ servo ผ่าน I2C (2 สาย) | ฿80–150 |
| **Power supply 5–6V 10A** (หรือ 6V/7.4V + Buck XL4016) | จ่ายไฟให้ servo **แยกจากบอร์ด** | ฿250–450 |
| Capacitor 1000–2200µF 16V | กันไฟตกตอน servo กระชาก | ฿10–20 |
| OLED 0.96" SSD1306 (I2C) | แสดงมุมแต่ละข้อ, สถานะ WiFi, IP | ฿60–120 |
| Joystick module x2 / Potentiometer x6 | ควบคุมด้วยมือ | ฿50–150 |
| ปุ่ม E-Stop (ปุ่มหยุดฉุกเฉิน) | ตัดไฟ servo | ฿50–100 |
| สาย Dupont, breadboard, terminal block | | ฿100–200 |

**ทางเลือกจอ:** LCD 1602 + I2C (ถูกสุด), TFT ST7789/ILI9341 (สี, ทำ GUI ได้), Nextion (จอสัมผัสมี GUI editor)

**ถ้าใช้ Bus Servo (STS3215):** ใช้ Waveshare Bus Servo Driver / Feetech URT-1 แทน PCA9685
**ถ้าใช้ Stepper:** Arduino CNC Shield + TMC2209 (เงียบ) หรือ A4988 + limit switch ทุกแกน

### 2.2 การต่อวงจร (ESP32 + PCA9685)

```
ESP32            PCA9685
3V3  ─────────►  VCC   (ไฟเลี้ยงชิปลอจิก)
GND  ─────────►  GND   ◄──┐  *** GND ต้องต่อร่วมกันทั้งหมด ***
GPIO21 (SDA) ─►  SDA      │
GPIO22 (SCL) ─►  SCL      │
                 V+ ◄── PSU 5–6V (+) ── [Cap 1000µF] ──┐
                 GND ◄─ PSU (–) ─────────────────────── ┘
                 CH0..CH5 ──► Servo 1..6 (สายส้ม=สัญญาณ, แดง=V+, น้ำตาล=GND)

OLED SSD1306 ── ต่อบัส I2C เดียวกัน (SDA/SCL) แอดเดรส 0x3C (PCA9685 = 0x40)
E-Stop ── ต่ออนุกรมกับไฟ V+ ของ servo (ตัดไฟจริง) + ต่อเข้า GPIO เพื่อให้ซอฟต์แวร์รู้
```

### 2.3 ข้อผิดพลาดที่มือใหม่เจอบ่อย ⚠️

1. **จ่ายไฟ servo จากพอร์ต USB/5V ของบอร์ด** → บอร์ดรีเซ็ต/ไหม้ — MG996R กินกระแสกระชากได้ ~2.5A ต่อตัว
2. **ไม่ต่อ GND ร่วม** → servo สั่นมั่ว
3. สั่ง servo ไปมุมสุดขอบที่กลไกติด → servo ร้อนและพัง → ต้องกำหนด **joint limit** ในซอฟต์แวร์
4. ใช้ LM2596 (3A) จ่ายให้ servo 6 ตัว → ไฟไม่พอ ใช้ XL4016 (8A) หรือ PSU โดยตรง

---

## 3. Software ควบคุม (แบ่งเป็นชั้น)

```
ชั้น 4  UI: Web / Mobile / Desktop GUI
ชั้น 3  Motion planning: IK, เส้นทาง, บันทึก/เล่นซ้ำท่า (teach & playback)
ชั้น 2  Protocol: Serial / WebSocket / MQTT ส่งคำสั่ง JSON
ชั้น 1  Firmware: อ่านคำสั่ง → จำกัดมุม → ทำให้เคลื่อนนุ่ม → สั่ง servo
```

### 3.1 Firmware (ESP32)
- เครื่องมือ: **Arduino IDE** (ง่าย) หรือ **PlatformIO ใน VS Code** (แนะนำ จัดการไลบรารีดีกว่า)
- ไลบรารี: `Adafruit PWM Servo Driver`, `ESP32Servo`, `Adafruit SSD1306`, `ArduinoJson`, `ESPAsyncWebServer`
- ฟีเจอร์ที่ควรมี:
  - **Joint limits** (มุมต่ำสุด/สูงสุดต่อข้อ) และ calibration offset
  - **Smooth motion** — ไม่กระโดดไปมุมเป้าหมายทันที ใช้ interpolation/ramp ความเร็ว
  - **Non-blocking loop** (ห้ามใช้ `delay()` ยาว ๆ) เพื่อรับคำสั่งไปพร้อมขยับ
  - Watchdog / E-Stop / ท่า Home เมื่อเปิดเครื่อง

### 3.2 Kinematics (คณิตศาสตร์ของแขนกล)
- **Forward Kinematics (FK):** รู้มุมทุกข้อ → คำนวณตำแหน่งปลายแขน (x, y, z)
- **Inverse Kinematics (IK):** อยากให้ปลายแขนไปที่ (x, y, z) → คำนวณมุมแต่ละข้อ
- เริ่มจาก IK แบบเรขาคณิตของแขน 2 ท่อน (law of cosines) แล้วขยายเป็น 3–4 DOF
- เรียนต่อ: **DH parameters**, Jacobian
- ไลบรารี Python: `ikpy`, `roboticstoolbox-python` (Peter Corke — มีหนังสือ/คอร์สประกอบ ดีมาก)

### 3.3 ฝั่ง PC
- **Python + pyserial** ส่งคำสั่งผ่าน USB, ทำ GUI ด้วย Tkinter / PyQt / Gradio
- ขั้นสูง: **ROS 2 + MoveIt 2** (วางแผนเส้นทาง หลบสิ่งกีดขวาง), **LeRobot** (Hugging Face, สอนแขนด้วย AI)

---

## 4. อุปกรณ์ต่อพ่วง

| หมวด | อุปกรณ์ | ใช้ทำอะไร |
|---|---|---|
| End-effector | Servo gripper, หัวดูดสุญญากาศ (ปั๊ม + โซลินอยด์วาล์ว + relay/MOSFET), ที่จับปากกา, แม่เหล็กไฟฟ้า | หยิบ, ดูด, วาด |
| Vision | ESP32-CAM, USB webcam, Pi Camera + Raspberry Pi | หาวัตถุด้วย OpenCV / YOLO แล้วสั่งไปหยิบ |
| Sensor | Limit switch, INA219 (วัดกระแส = รู้ว่าจับของ/ชน), ToF VL53L0X, Ultrasonic, IMU MPU6050 | ความปลอดภัย, homing, ตรวจวัตถุ |
| Input | Joystick, potentiometer, Leader arm (แขนจำลองหมุนตาม), เกมแพด Bluetooth (ไลบรารี Bluepad32) | ควบคุมด้วยมือ |
| ระบบงาน | สายพานลำเลียง (stepper/DC motor), ไฟ LED สถานะ, buzzer | ทำ mini production line |

---

## 5. ควบคุมผ่านมือถือ / เว็บ

| วิธี | ความยาก | ระยะ | หมายเหตุ |
|---|---|---|---|
| **ESP32 Web Server + WebSocket** | ⭐⭐ | WiFi วงเดียวกัน | แนะนำเริ่มที่นี่: เปิดเว็บจากมือถือ มี slider คุมแต่ละข้อ ไม่ต้องลงแอป |
| ESP32 เป็น Access Point เอง | ⭐⭐ | ใกล้ ๆ | ใช้นอกสถานที่ไม่มีเราเตอร์ |
| **MQTT** (Mosquitto / EMQX / HiveMQ Cloud) | ⭐⭐⭐ | ผ่านอินเทอร์เน็ต | คุมจากที่ไหนก็ได้, หลายเครื่อง, ต่อ dashboard ได้ |
| Node-RED Dashboard | ⭐⭐ | — | ลาก-วางทำ UI เร็ว ต่อ MQTT ได้ |
| Blynk / Arduino IoT Cloud | ⭐ | อินเทอร์เน็ต | เร็วที่สุด แต่ผูกกับแพลตฟอร์ม |
| Web Serial API (Chrome) | ⭐⭐ | สาย USB | เว็บคุมบอร์ดผ่าน USB โดยตรง |
| แอปจริง: Flutter / React Native / PWA | ⭐⭐⭐⭐ | — | ทำทีหลังเมื่อ protocol นิ่งแล้ว |

**Topic MQTT ตัวอย่าง:** `robot/arm1/cmd` (ส่งคำสั่ง), `robot/arm1/state` (ส่งสถานะ/มุมปัจจุบัน), `robot/arm1/estop`

**ความปลอดภัย:** ถ้าเปิดให้ควบคุมจากอินเทอร์เน็ต ต้องมี username/password + TLS และห้ามเปิดพอร์ตตรงเข้าบ้าน — แขนกลขยับได้จริง อาจชนคน/ของ

---

## 6. ⭐ ยังไม่มีฮาร์ดแวร์? Simulate ได้หมดทุกชั้น

| สิ่งที่อยากทดสอบ | เครื่องมือ | ราคา | จุดเด่น |
|---|---|---|---|
| **โค้ด ESP32/Arduino + วงจร** | **Wokwi** (wokwi.com / ส่วนขยาย VS Code) | ฟรี (มีแผนเสียเงิน) | จำลอง ESP32, Servo, OLED SSD1306, ILI9341, ปุ่ม, Potentiometer, Joystick และ **WiFi ได้** — ทดสอบ Web Server/MQTT ได้จริง |
| โค้ด Arduino Uno แบบง่าย | Tinkercad Circuits | ฟรี | เหมาะเริ่มต้นสุด ๆ แต่ไม่มี ESP32 |
| **Kinematics (FK/IK)** | Python + `matplotlib` / `roboticstoolbox-python` + Swift viewer / `ikpy` | ฟรี | เห็นแขนขยับเป็น 3D, ทดสอบ IK |
| **ฟิสิกส์ (แรงโน้มถ่วง, การหยิบจับ)** | **MuJoCo**, PyBullet | ฟรี | MuJoCo Menagerie มีโมเดล SO-ARM100 ให้ใช้ทันที |
| หุ่นยนต์ทั้งระบบ + กล้อง | **Webots**, CoppeliaSim (edu ฟรี), Gazebo | ฟรี | มีแขนกลสำเร็จรูป, จำลองกล้อง/เซนเซอร์ |
| Motion planning ระดับอุตสาหกรรม | ROS 2 + MoveIt 2 + RViz | ฟรี | ต้องใช้ Linux/Docker, เรียนรู้นานกว่า |
| UI เว็บ/มือถือ | **แขนจำลอง 3D บนเว็บ (Three.js)** + Mock server / MQTT broker สาธารณะ | ฟรี | ทดสอบ UI โดยไม่ต้องมีบอร์ด |
| ออกแบบโครงสร้าง | Fusion 360 (personal ฟรี), Onshape, FreeCAD | ฟรี | ส่งออก URDF ไปใช้ใน sim ได้ |

### แนวทาง "Digital Twin" (แนะนำมาก)
```
            ┌──► Simulator (Three.js / Python / MuJoCo)   ← ช่วงยังไม่มีของ
UI / Python ┤      (รับ JSON command เดียวกัน)
            └──► ESP32 จริง (Serial / WebSocket / MQTT)    ← ช่วงมีฮาร์ดแวร์
```
เขียนโค้ดชั้นบนให้คุยผ่าน interface เดียว (`send_joints([...])`) แล้วสลับ backend ได้
ตอนได้ฮาร์ดแวร์มา จะเหลือแค่ calibrate มุม ไม่ต้องเขียนใหม่

---

## 7. แผนการเรียน (แนะนำ 8 สัปดาห์)

| สัปดาห์ | ทำอะไร | ต้องมีฮาร์ดแวร์? |
|---|---|---|
| 1 | Wokwi: ESP32 คุม servo 1 ตัว, อ่าน potentiometer, แสดงผล OLED | ❌ |
| 2 | Wokwi: คุม servo 6 ตัว + smooth motion + joint limits + รับคำสั่ง JSON ผ่าน Serial | ❌ |
| 3 | Python: FK/IK แขน 2–4 DOF, plot 3D ด้วย matplotlib / roboticstoolbox | ❌ |
| 4 | Wokwi: ESP32 Web Server + WebSocket + หน้าเว็บ slider บนมือถือ | ❌ |
| 5 | Simulator 3D บนเว็บ / MuJoCo — ทำ teach & playback, หยิบ-วางเสมือน | ❌ |
| 6 | สั่งซื้อและประกอบ Kit, ต่อวงจรไฟแยก, calibrate | ✅ |
| 7 | อัปโหลด firmware เดิมลงของจริง, ปรับจูน, เพิ่ม E-Stop | ✅ |
| 8 | ต่อยอด: MQTT ควบคุมระยะไกล, กล้อง + OpenCV หาวัตถุแล้วหยิบ | ✅ |

**งบชุดเริ่มต้น (Kit 6DOF MG996R + ESP32 + PCA9685 + PSU + OLED + อุปกรณ์จุกจิก): ประมาณ ฿2,500–4,000**

---

## 8. แหล่งเรียนรู้ (คำค้นแนะนำ)

- **Wokwi docs** — ESP32 servo, SSD1306, WiFi simulation
- **Random Nerd Tutorials** — "ESP32 WebSocket Server", "ESP32 MQTT", "PCA9685" (สอนละเอียด มีวงจร)
- **Peter Corke — Robotics Toolbox for Python** และหนังสือ *Robotics, Vision and Control* (ทฤษฎี FK/IK/DH)
- **Hugging Face LeRobot + SO-ARM100 (GitHub: TheRobotStudio/SO-ARM100)** — แขนโอเพนซอร์สสาย AI
- **MuJoCo Menagerie** (GitHub: google-deepmind/mujoco_menagerie) — โมเดลแขนพร้อมใช้
- **MoveIt 2 Tutorials** — เมื่อพร้อมขึ้น ROS 2
- YouTube: "How To Mechatronics robot arm", "EEZYbotArm", "inverse kinematics explained"
