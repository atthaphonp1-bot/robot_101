/* -------------------------------------------------------------
   cmm-calc.js – pure functions + tiny DOM UI (no modules, no libs)
   ------------------------------------------------------------- */

/* 1️⃣ Encoder catalogue ------------------------------------------------ */
const ENCODERS = [
  { id: 'servo',   label: 'Servo MG996R (~1°)',          deg: 1 },
  { id: 'pca',     label: 'PCA9685 step (0.44°)',       deg: 0.44 },
  { id: 'as5600',  label: 'AS5600 12-bit',              deg: 360 / 4096 },
  { id: 'as5047',  label: 'AS5047P 14-bit',             deg: 360 / 16384 },
  { id: 'b17',     label: 'Absolute 17-bit',            deg: 360 / 131072 },
  { id: 'b19',     label: 'Absolute 19-bit',            deg: 360 / 524288 },
  { id: 'custom',  label: 'กำหนดเอง (°)',               deg: null },
];

/* 2️⃣ Core calculation ------------------------------------------------ */
function estimateError(levers, stepDeg, mechMm, dT, alpha = 23e-6) {
  // keep only positive, finite lever lengths
  const valid = levers.filter(v => typeof v === 'number' && isFinite(v) && v > 0);
  const rad = stepDeg * Math.PI / 180;               // step size in radians

  // encoder contributions
  let sumSq = 0;
  let sum   = 0;
  for (const L of valid) {
    const term = L * rad;
    sumSq += term * term;
    sum   += term;
  }
  const encRss   = Math.sqrt(sumSq);   // RSS
  const encWorst = sum;                // worst‑case (sum)

  // thermal contribution (only the longest lever matters)
  const maxL = valid.length ? Math.max(...valid) : 0;
  const thermal = alpha * Math.abs(dT) * maxL;

  // total error (RSS of independent sources)
  const total = Math.sqrt(encRss * encRss + mechMm * mechMm + thermal * thermal);

  return {
    stepDeg,
    encRss,
    encWorst,
    thermal,
    mech: mechMm,
    total,
  };
}

/* 3️⃣ Verdict ----------------------------------------------------------- */
function verdict(totalMm) {
  if (totalMm < 0.05)      return 'ระดับแขนวัดเชิงพาณิชย์';
  if (totalMm < 0.5)       return 'ตรวจชิ้นงานทั่วไปได้';
  if (totalMm < 2)         return 'เก็บรูปทรงชิ้นงาน (digitize) ได้';
  return 'หยิบ-วางได้ แต่ไม่เหมาะกับการวัด';
}

/* -------------------------------------------------------------
   4️⃣ UI – only executed when a browser document is present
   ------------------------------------------------------------- */
if (typeof document !== 'undefined') {
  // run after the DOM is ready
  document.addEventListener('DOMContentLoaded', () => {
    /* ---- populate the encoder <select> --------------------------- */
    const encSelect = document.getElementById('enc');
    ENCODERS.forEach(e => {
      const opt = document.createElement('option');
      opt.value = e.id;
      opt.textContent = e.label;
      encSelect.appendChild(opt);
    });
    encSelect.value = 'as5047'; // default selection

    /* ---- helper: show / hide the custom‑degree field ------------- */
    const customField = document.getElementById('encCustom')
          ? document.getElementById('encCustom').closest('.field')
          : null;

    function updateCustomVisibility() {
      if (!customField) return;
      customField.hidden = encSelect.value !== 'custom';
    }
    encSelect.addEventListener('change', updateCustomVisibility);
    updateCustomVisibility();   // initial run

    /* ---- main calculation routine -------------------------------- */
    const outStep    = document.getElementById('outStep');
    const outRss     = document.getElementById('outRss');
    const outWorst   = document.getElementById('outWorst');
    const outThermal = document.getElementById('outThermal');
    const outTotal   = document.getElementById('outTotal');
    const outVerdict= document.getElementById('outVerdict');
    const barsDiv    = document.getElementById('bars');

    // formatting helper for millimetres
    function fmtMm(v) {
      const abs = Math.abs(v);
      const txt = (abs < 0.1 ? v.toFixed(3) : v.toFixed(2));
      return txt + ' mm';
    }

    // create / refresh the three bar rows
    function renderBars(res) {
      // clear previous bars
      barsDiv.innerHTML = '';

      const maxVal = Math.max(res.encRss, res.mech, res.thermal, 1e-9);
      const rows = [
        { label: 'จาก encoder', value: res.encRss },
        { label: 'จากกลไก', value: res.mech   },
        { label: 'จากอุณหภูมิ',    value: res.thermal},
      ];

      rows.forEach(row => {
        const wrapper = document.createElement('div');
        wrapper.className = 'bar-row';

        const labelSpan = document.createElement('span');
        labelSpan.textContent = row.label;
        labelSpan.style.display = 'inline-block';
        labelSpan.style.width = '120px'; // a bit of space for the label
        wrapper.appendChild(labelSpan);

        const bar = document.createElement('div');
        bar.className = 'bar';
        const perc = (row.value / maxVal) * 100;
        bar.style.width = perc + '%';
        bar.style.background = 'var(--accent)';
        bar.style.height = '1rem';
        wrapper.appendChild(bar);

        barsDiv.appendChild(wrapper);
      });
    }

    // recalculate and update UI
    function recalc(event) {
      if (event) event.preventDefault(); // for form submit

      // --- read inputs -------------------------------------------------
      const r1 = parseFloat(document.getElementById('r1').value);
      const r2 = parseFloat(document.getElementById('r2').value);
      const r3 = parseFloat(document.getElementById('r3').value);
      const r4 = parseFloat(document.getElementById('r4').value);
      const levers = [r1, r2, r3, r4];

      const mech = parseFloat(document.getElementById('mech').value) || 0;
      const dT   = parseFloat(document.getElementById('dT').value)   || 0;

      // encoder step size
      let stepDeg;
      const selId = encSelect.value;
      if (selId === 'custom') {
        stepDeg = parseFloat(document.getElementById('encCustom').value) || 0;
      } else {
        const encObj = ENCODERS.find(e => e.id === selId);
        stepDeg = encObj ? encObj.deg : 0;
      }

      // --- core computation ---------------------------------------------
      const result = estimateError(levers, stepDeg, mech, dT);

      // --- write results ------------------------------------------------
      outStep.textContent    = stepDeg.toFixed(4) + '°';
      outRss.textContent     = fmtMm(result.encRss);
      outWorst.textContent   = fmtMm(result.encWorst);
      outThermal.textContent = fmtMm(result.thermal);
      outTotal.textContent   = fmtMm(result.total);
      outVerdict.textContent = verdict(result.total);

      // --- bars ---------------------------------------------------------
      renderBars(result);
    }

    /* ---- wire up the form ---------------------------------------- */
    const form = document.getElementById('calc');
    if (form) {
      // any change inside the form triggers recompute
      form.addEventListener('input', recalc);
      form.addEventListener('change', recalc);
      // prevent actual submission (page reload)
      form.addEventListener('submit', e => e.preventDefault());
    }

    // initial calculation so UI is not empty
    recalc();
  });
}

/* -------------------------------------------------------------
   Export for Node tests
   ------------------------------------------------------------- */
if (typeof module !== 'undefined') {
  module.exports = { estimateError, verdict, ENCODERS };
}