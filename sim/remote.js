// Configuration and state
let client = null;
let armOnline = false;
let estop = false;
let moving = false;
let playing = false;
let touching = false;
let pendingPlayResolve = null;
let target = {x: 180, y: 0, z: 150, p: -45};
let step = 10;
let jogInterval = null;

// Joint configuration
const jointNames = ['ฐานหมุน', 'ไหล่', 'ศอก', 'ข้อมือก้ม-เงย', 'ข้อมือหมุน', 'กริปเปอร์'];
const jointRanges = [[0, 180], [15, 165], [0, 180], [0, 180], [0, 180], [10, 120]];
const initialJoints = [90, 90, 135, 135, 90, 80];

// Load configuration from localStorage
function loadConfig() {
    try {
        const cfg = JSON.parse(localStorage.getItem('armRemote.cfg')) || {};
        document.getElementById('brokerUrl').value = cfg.url || 'wss://broker.hivemq.com:8884/mqtt';
        document.getElementById('topicPrefix').value = cfg.prefix || 'robot101/arm1';
        document.getElementById('mqttUser').value = cfg.user || '';
    } catch (e) {
        console.error('Failed to load config:', e);
    }
}

// Save configuration to localStorage (excluding password)
function saveConfig() {
    try {
        const cfg = {
            url: document.getElementById('brokerUrl').value,
            prefix: document.getElementById('topicPrefix').value,
            user: document.getElementById('mqttUser').value
        };
        localStorage.setItem('armRemote.cfg', JSON.stringify(cfg));
    } catch (e) {
        console.error('Failed to save config:', e);
    }
}

// Toast notification
function toast(msg) {
    const toastEl = document.getElementById('toast');
    toastEl.textContent = msg;
    toastEl.classList.add('show');
    setTimeout(() => toastEl.classList.remove('show'), 2500);
}

// Log message
function log(msg) {
    const logEl = document.getElementById('log');
    const now = new Date();
    const time = now.toLocaleTimeString('th-TH', {hour12: false});
    const line = `${time} ${msg}`;
    logEl.textContent = line + '\n' + logEl.textContent;
    const lines = logEl.textContent.split('\n');
    if (lines.length > 30) {
        logEl.textContent = lines.slice(0, 30).join('\n');
    }
}

// Haptic feedback
function haptic() {
    if (navigator.vibrate) {
        navigator.vibrate(10);
    }
}

// Update status display
function setStatus() {
    const statusEl = document.getElementById('status');
    if (!client || !client.connected) {
        statusEl.textContent = 'ออฟไลน์';
        statusEl.className = 'pill';
    } else if (estop) {
        statusEl.textContent = 'E-STOP';
        statusEl.className = 'pill bad';
    } else if (armOnline) {
        statusEl.textContent = 'แขน online';
        statusEl.className = 'pill ok';
    } else {
        statusEl.textContent = 'เชื่อมต่อ broker';
        statusEl.className = 'pill acc';
    }

    document.getElementById('settingsCard').hidden = !!client?.connected;
}

// Send command to MQTT
function send(obj) {
    if (!client?.connected) {
        toast('ยังไม่ได้เชื่อมต่อ');
        return false;
    }

    const prefix = document.getElementById('topicPrefix').value;
    const json = JSON.stringify(obj);
    client.publish(prefix + '/cmd', json);
    log('→ ' + json);
    return true;
}

// Initialize joint sliders
function initJointSliders() {
    const container = document.getElementById('jointSliders');
    container.innerHTML = '';

    const throttledSendJoints = throttle(() => {
        const values = Array.from(container.querySelectorAll('input[type="range"]'))
            .map(el => Number(el.value));
        send({j: values});
    }, 120);

    initialJoints.forEach((value, i) => {
        const field = document.createElement('div');
        field.className = 'field';

        const label = document.createElement('label');
        label.innerHTML = `J${i+1} ${jointNames[i]} <span>${value}°</span>`;

        const input = document.createElement('input');
        input.type = 'range';
        input.min = jointRanges[i][0];
        input.max = jointRanges[i][1];
        input.value = value;

        input.addEventListener('pointerdown', () => touching = true);
        input.addEventListener('pointerup', () => {
            touching = false;
            throttledSendJoints();
        });
        input.addEventListener('pointercancel', () => {
            touching = false;
            throttledSendJoints();
        });

        input.addEventListener('input', () => {
            label.querySelector('span').textContent = input.value + '°';
            if (!touching) {
                throttledSendJoints();
            }
        });

        field.appendChild(label);
        field.appendChild(input);
        container.appendChild(field);
    });
}

// Throttle function
function throttle(func, limit) {
    let lastFunc;
    let lastRan;
    return function() {
        const context = this;
        const args = arguments;
        if (!lastRan) {
            func.apply(context, args);
            lastRan = Date.now();
        } else {
            clearTimeout(lastFunc);
            lastFunc = setTimeout(function() {
                if ((Date.now() - lastRan) >= limit) {
                    func.apply(context, args);
                    lastRan = Date.now();
                }
            }, limit - (Date.now() - lastRan));
        }
    };
}

// Initialize UI
function initUI() {
    // Load config
    loadConfig();

    // Set up gear button
    document.getElementById('gearBtn').addEventListener('click', () => {
        const card = document.getElementById('settingsCard');
        card.hidden = !card.hidden;
    });

    // Set up connect button
    document.getElementById('connectBtn').addEventListener('click', () => {
        if (client) {
            client.end(true);
            client = null;
            document.getElementById('connectBtn').textContent = 'เชื่อมต่อ';
            log('ตัดการเชื่อมต่อ');
            setStatus();
            return;
        }

        if (!window.mqtt) {
            toast('MQTT library not loaded');
            return;
        }

        const url = document.getElementById('brokerUrl').value;
        const prefix = document.getElementById('topicPrefix').value;
        const user = document.getElementById('mqttUser').value;
        const pass = document.getElementById('mqttPass').value;

        saveConfig();

        client = window.mqtt.connect(url, {
            clientId: 'remote-' + Math.random().toString(16).slice(2, 10),
            clean: true,
            reconnectPeriod: 3000,
            ...(user ? {username: user, password: pass} : {})
        });

        client.on('connect', () => {
            document.getElementById('connectBtn').textContent = 'ตัดการเชื่อมต่อ';
            log('เชื่อมต่อสำเร็จ');
            setStatus();

            client.subscribe([
                prefix + '/state',
                prefix + '/status',
                prefix + '/reply'
            ]);
        });

        client.on('close', () => {
            log('การเชื่อมต่อถูกปิด');
            setStatus();
        });

        client.on('error', (err) => {
            log('MQTT error: ' + err.message);
        });

        client.on('message', (topic, buf) => {
            const str = buf.toString();
            const prefix = document.getElementById('topicPrefix').value;

            if (topic.endsWith('/status')) {
                armOnline = str === 'online';
            } else if (topic.endsWith('/reply')) {
                try {
                    const obj = JSON.parse(str);
                    if (obj.err) {
                        toast('ผิดพลาด: ' + obj.err);
                        log('← ' + str);
                    }
                } catch (e) {
                    console.error('Failed to parse reply:', e);
                }
            } else if (topic.endsWith('/state')) {
                try {
                    const obj = JSON.parse(str);
                    estop = obj.estop || false;
                    moving = obj.moving || false;

                    // Update joints text
                    const jointsText = obj.state.map((v, i) =>
                        `J${i+1} ${Math.round(v)}°`).join(' · ');
                    document.getElementById('jointsText').textContent = jointsText;

                    // Update move status
                    const moveStatus = document.getElementById('moveStatus');
                    if (moving) {
                        moveStatus.textContent = 'กำลังขยับ';
                        moveStatus.className = 'pill acc';
                    } else {
                        moveStatus.textContent = 'นิ่ง';
                        moveStatus.className = 'pill';
                    }

                    // Update sliders if not touching
                    if (!touching) {
                        const sliders = document.querySelectorAll('#jointSliders input[type="range"]');
                        obj.state.forEach((v, i) => {
                            if (sliders[i]) {
                                sliders[i].value = v;
                                const label = sliders[i].previousElementSibling;
                                label.querySelector('span').textContent = Math.round(v) + '°';
                            }
                        });
                    }

                    // Draw arm
                    drawArm(obj.state);

                    // Resolve pending play if not moving
                    if (pendingPlayResolve && !moving) {
                        pendingPlayResolve();
                        pendingPlayResolve = null;
                    }
                } catch (e) {
                    console.error('Failed to parse state:', e);
                }
            }

            setStatus();
        });
    });

    // Set up stop button
    document.getElementById('stopBtn').addEventListener('click', () => {
        send({stop: 1});
        playing = false;
        haptic();
    });

    // Set up mode segmented buttons
    document.querySelectorAll('#modeSeg button').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#modeSeg button').forEach(b =>
                b.classList.remove('active'));
            btn.classList.add('active');

            const mode = btn.dataset.mode;
            document.getElementById('jointPanel').hidden = mode !== 'joint';
            document.getElementById('cartPanel').hidden = mode !== 'cart';
        });
    });

    // Set up step segmented buttons
    document.querySelectorAll('#stepSeg button').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#stepSeg button').forEach(b =>
                b.classList.remove('active'));
            btn.classList.add('active');
            step = Number(btn.dataset.step);
        });
    });

    // Set up jog buttons
    document.querySelectorAll('[data-jog]').forEach(btn => {
        btn.addEventListener('pointerdown', () => {
            haptic();
            const jog = btn.dataset.jog;

            if (jog === 'home') {
                send({home: 1});
                target = {x: 182, y: 0, z: 148, p: -45};
                updateTargetText();
                return;
            }

            // Handle jog command
            const axis = jog[0];
            const sign = jog[1] === '+' ? 1 : -1;

            if (axis === 'p') {
                target.p = Math.max(-90, Math.min(90, target.p + sign * step));
            } else {
                const axisMap = {x: 'x', y: 'y', z: 'z'};
                target[axisMap[axis]] += sign * step;
            }

            updateTargetText();
            send({ik: [
                Math.round(target.x * 10) / 10,
                Math.round(target.y * 10) / 10,
                Math.round(target.z * 10) / 10,
                Math.round(target.p * 10) / 10
            ]});

            // Set up interval for continuous jog
            if (jogInterval) clearInterval(jogInterval);
            jogInterval = setInterval(() => {
                if (axis === 'p') {
                    target.p = Math.max(-90, Math.min(90, target.p + sign * step));
                } else {
                    target[axisMap[axis]] += sign * step;
                }

                updateTargetText();
                send({ik: [
                    Math.round(target.x * 10) / 10,
                    Math.round(target.y * 10) / 10,
                    Math.round(target.z * 10) / 10,
                    Math.round(target.p * 10) / 10
                ]});
            }, 200);
        });

        btn.addEventListener('pointerup', () => {
            if (jogInterval) {
                clearInterval(jogInterval);
                jogInterval = null;
            }
        });

        btn.addEventListener('pointerleave', () => {
            if (jogInterval) {
                clearInterval(jogInterval);
                jogInterval = null;
            }
        });

        btn.addEventListener('pointercancel', () => {
            if (jogInterval) {
                clearInterval(jogInterval);
                jogInterval = null;
            }
        });
    });

    // Set up grip buttons
    document.getElementById('gripOpen').addEventListener('click', () => {
        send({grip: 110});
    });

    document.getElementById('gripClose').addEventListener('click', () => {
        send({grip: 20});
    });

    // Set up speed control
    const speedInput = document.getElementById('speed');
    const speedVal = document.getElementById('speedVal');

    speedVal.textContent = speedInput.value + ' °/s';
    speedInput.addEventListener('input', () => {
        speedVal.textContent = speedInput.value + ' °/s';
    });

    speedInput.addEventListener('change', () => {
        send({speed: Number(speedInput.value)});
    });

    // Set up play buttons
    document.getElementById('playBtn').addEventListener('click', async () => {
        playing = true;
        let poses = [];

        try {
            const saved = JSON.parse(localStorage.getItem('robotArmSim.program')) || [];
            poses = saved.filter(p => Array.isArray(p.j) && p.j.length === 6);
        } catch (e) {
            console.error('Failed to load poses:', e);
        }

        document.getElementById('posesInfo').textContent =
            poses.length > 0 ? `มี ${poses.length} ท่า` : 'ยังไม่มีท่า — บันทึกจากหน้า Simulator';

        if (poses.length === 0) {
            toast('ไม่มีท่าที่บันทึก');
            return;
        }

        for (const pose of poses) {
            if (!playing) break;

            send({j: pose.j});

            // Wait for movement to complete
            await new Promise((resolve) => {
                pendingPlayResolve = resolve;
                setTimeout(() => {
                    if (pendingPlayResolve) {
                        pendingPlayResolve = null;
                        resolve();
                    }
                }, 8000);
            });

            // Small delay between poses
            if (playing) {
                await new Promise(resolve => setTimeout(resolve, 300));
            }
        }
    });

    document.getElementById('stopPlayBtn').addEventListener('click', () => {
        playing = false;
    });

    // Initialize joint sliders
    initJointSliders();

    // Initialize target text
    updateTargetText();

    // Initialize poses info
    try {
        const saved = JSON.parse(localStorage.getItem('robotArmSim.program')) || [];
        const poses = saved.filter(p => Array.isArray(p.j) && p.j.length === 6);
        document.getElementById('posesInfo').textContent =
            poses.length > 0 ? `มี ${poses.length} ท่า` : 'ยังไม่มีท่า — บันทึกจากหน้า Simulator';
    } catch (e) {
        console.error('Failed to load poses:', e);
    }

    // Initial status
    setStatus();
    document.getElementById('settingsCard').hidden = false;

    // Initial arm drawing
    drawArm(initialJoints);

    // Set up resize handler
    window.addEventListener('resize', () => drawArm(initialJoints));
}

// Update target text display
function updateTargetText() {
    const text = `เป้าหมาย X ${Math.round(target.x)} · Y ${Math.round(target.y)} · Z ${Math.round(target.z)} mm · pitch ${Math.round(target.p)}°`;
    document.getElementById('targetText').textContent = text;
}

// Draw the arm on canvas
function drawArm(state) {
    const canvas = document.getElementById('armCanvas');
    const ctx = canvas.getContext('2d');

    // Set canvas size
    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvas.clientWidth * dpr;
    canvas.height = 200 * dpr;
    ctx.scale(dpr, dpr);

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Convert degrees to radians
    const degToRad = (deg) => deg * Math.PI / 180;

    // Calculate joint positions
    const t2 = state[1] - 90;
    const t3 = state[2] - 45;
    const t4 = state[3] - 90;

    const S = {x: 0, y: 95};
    const a1 = degToRad(t2);
    const E = {
        x: S.x + 120 * Math.sin(a1),
        y: S.y + 120 * Math.cos(a1)
    };

    const a2 = a1 + degToRad(t3);
    const W = {
        x: E.x + 115 * Math.sin(a2),
        y: E.y + 115 * Math.cos(a2)
    };

    const a3 = a2 + degToRad(t4);
    const T = {
        x: W.x + 95 * Math.sin(a3),
        y: W.y + 95 * Math.cos(a3)
    };

    // Map coordinates to canvas
    // uniform scale in CSS pixels (ctx is already scaled by dpr), region x[-100,300] y[-10,320]
    const cw = canvas.clientWidth, ch = 200;
    const k = Math.min(cw / 400, ch / 330);
    const ox = (cw - 400 * k) / 2, oy = (ch - 330 * k) / 2;
    const mapX = (x) => ox + (x + 100) * k;
    const mapY = (y) => oy + (320 - y) * k;

    // Draw ground line
    ctx.beginPath();
    ctx.moveTo(0, mapY(0));
    ctx.lineTo(cw, mapY(0));
    ctx.strokeStyle = '#888';
    ctx.lineWidth = 1;
    ctx.stroke();

    // Draw base
    ctx.fillStyle = '#ccc';
    ctx.fillRect(mapX(-30), mapY(95), mapX(30) - mapX(-30), mapY(0) - mapY(95));

    // Draw links
    ctx.beginPath();
    ctx.moveTo(mapX(S.x), mapY(S.y));
    ctx.lineTo(mapX(E.x), mapY(E.y));
    ctx.lineTo(mapX(W.x), mapY(W.y));
    ctx.lineTo(mapX(T.x), mapY(T.y));

    ctx.strokeStyle = getComputedStyle(document.body).color;
    ctx.globalAlpha = 0.9;
    ctx.lineWidth = 14;
    ctx.lineCap = 'round';
    ctx.stroke();
    ctx.globalAlpha = 1;

    // Draw joints
    const drawJoint = (x, y) => {
        ctx.beginPath();
        ctx.arc(mapX(x), mapY(y), 7, 0, Math.PI * 2);
        ctx.fillStyle = 'white';
        ctx.fill();
        ctx.strokeStyle = '#0a84ff';
        ctx.lineWidth = 3;
        ctx.stroke();
    };

    drawJoint(S.x, S.y);
    drawJoint(E.x, E.y);
    drawJoint(W.x, W.y);

    // Draw tip
    ctx.beginPath();
    ctx.arc(mapX(T.x), mapY(T.y), 5, 0, Math.PI * 2);
    ctx.fillStyle = '#0a84ff';
    ctx.fill();

    // Draw base angle text
    ctx.font = '12px sans-serif';
    ctx.fillStyle = getComputedStyle(document.body).color;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(`ฐาน ${Math.round(state[0])}°`, 10, 10);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initUI);