const BOM = [
    {id: 'esp32', group: 'ควบคุม', name: 'ESP32 DevKit V1', spec: 'ESP32-WROOM-32 38 ขา', qty: 1, min: 150, max: 250, kw: 'esp32 devkit v1 wroom 32', optional: false},
    {id: 'esp32base', group: 'ควบคุม', name: 'บอร์ดขยายขา ESP32', spec: 'terminal expansion 38 pin', qty: 1, min: 60, max: 120, kw: 'esp32 expansion board 38 pin', optional: false},
    {id: 'pca9685', group: 'ควบคุม', name: 'PCA9685', spec: '16 ช่อง I2C', qty: 1, min: 80, max: 150, kw: 'pca9685', optional: false},
    {id: 'oled', group: 'ควบคุม', name: 'จอ OLED', spec: '0.96" SSD1306 I2C', qty: 1, min: 60, max: 120, kw: 'oled 0.96 ssd1306 i2c', optional: false},
    {id: 'servo', group: 'กลไก', name: 'Servo MG996R', spec: 'metal gear', qty: 6, min: 90, max: 150, kw: 'mg996r', optional: false},
    {id: 'armkit', group: 'กลไก', name: 'ชุดโครงแขน 6DOF', spec: 'อะลูมิเนียม (ไม่รวม servo)', qty: 1, min: 600, max: 1500, kw: '6dof robot arm kit aluminium', optional: false},
    {id: 'killsw', group: 'ไฟ', name: 'สวิตช์ตัดไฟ servo (แนะนำ)', spec: 'สวิตช์ ≥15A ต่ออนุกรมสายไฟ servo · ตัดไฟได้แม้เว็บ/WiFi ล่ม', qty: 1, min: 20, max: 60, kw: 'toggle switch 15a 12v', optional: true},
    {id: 'psu', group: 'ไฟ', name: 'PSU 12V 12.5A', spec: 'เช่น Mean Well LRS-150-12', qty: 1, min: 700, max: 1200, kw: 'mean well lrs-150-12', optional: false},
    {id: 'buck6', group: 'ไฟ', name: 'Buck converter servo', spec: 'ปรับได้ ตั้ง 6V ≥ 20A', qty: 1, min: 250, max: 500, kw: 'dc dc step down 20a 300w', optional: false},
    {id: 'buck5', group: 'ไฟ', name: 'Buck converter Pi', spec: '5.1V 5A / USB-C PD 27W', qty: 1, min: 150, max: 350, kw: 'step down usb c pd 5v 5a', optional: false},
    {id: 'fuse', group: 'ไฟ', name: 'ฟิวส์ + กระบอก', spec: '15A และ 5A', qty: 2, min: 15, max: 40, kw: 'fuse holder inline', optional: false},
    {id: 'cap', group: 'ไฟ', name: 'ตัวเก็บประจุ', spec: '1000µF 16V', qty: 2, min: 5, max: 15, kw: 'capacitor 1000uf 16v', optional: false},
    {id: 'pi5', group: 'Raspberry Pi', name: 'Raspberry Pi 5', spec: '4GB (8GB ถ้าจะรัน VLM บนเครื่อง)', qty: 1, min: 2300, max: 3500, kw: 'raspberry pi 5', optional: false},
    {id: 'cooler', group: 'Raspberry Pi', name: 'Active Cooler', spec: 'สำหรับ Pi 5', qty: 1, min: 150, max: 300, kw: 'raspberry pi 5 active cooler', optional: false},
    {id: 'sd', group: 'Raspberry Pi', name: 'microSD', spec: '32GB ขึ้นไป', qty: 1, min: 120, max: 250, kw: 'microsd 32gb', optional: false},
    {id: 'cam', group: 'Raspberry Pi', name: 'กล้อง USB', spec: '720p–1080p', qty: 1, min: 300, max: 700, kw: 'usb webcam 1080p', optional: false},
    {id: 'usb', group: 'สาย', name: 'สาย USB data', spec: 'ส่งข้อมูลได้ ไม่ใช่สายชาร์จอย่างเดียว', qty: 1, min: 50, max: 120, kw: 'usb data cable', optional: false},
    {id: 'dupont', group: 'สาย', name: 'สาย Dupont', spec: 'ชุด M-M / M-F / F-F', qty: 1, min: 50, max: 100, kw: 'dupont jumper wire set', optional: false},
    {id: 'wire', group: 'สาย', name: 'สายไฟ 16 AWG', spec: 'สายไฟ servo/12V ยาว 2 เมตร', qty: 1, min: 50, max: 120, kw: 'silicone wire 16awg', optional: false},
    {id: 'meter', group: 'สาย', name: 'มัลติมิเตอร์', spec: 'ไว้ตั้งแรงดัน buck (ถ้ามีแล้วไม่ต้องซื้อ)', qty: 1, min: 250, max: 600, kw: 'digital multimeter', optional: true}
];

function shopeeUrl(kw) {
    return 'https://shopee.co.th/search?keyword=' + encodeURIComponent(kw);
}

function lineRange(item) {
    return [item.min * item.qty, item.max * item.qty];
}

function totals(items, prices, included) {
    let estMin = 0, estMax = 0, actual = 0, priced = 0, missing = 0;

    items.forEach(item => {
        const isIncluded = included[item.id] !== undefined ? included[item.id] : !item.optional;
        if (!isIncluded) return;

        const [min, max] = lineRange(item);
        estMin += min;
        estMax += max;

        const price = prices[item.id];
        if (price > 0) {
            actual += price * item.qty;
            priced++;
        } else {
            missing++;
        }
    });

    return {estMin, estMax, actual, priced, missing};
}

if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        const bomBody = document.getElementById('bomBody');
        const totEst = document.getElementById('totEst');
        const totActual = document.getElementById('totActual');
        const missingEl = document.getElementById('missing');
        const csvBtn = document.getElementById('csv');

        let state = {prices: {}, included: {}};

        // Load state
        try {
            const saved = localStorage.getItem('robot101.bom');
            if (saved) {
                state = JSON.parse(saved);
            }
        } catch (e) {
            console.error('Error loading state:', e);
        }

        // Render table
        function renderTable() {
            bomBody.innerHTML = '';
            let currentGroup = null;

            BOM.forEach(item => {
                const isIncluded = state.included[item.id] !== undefined ? state.included[item.id] : !item.optional;
                const [min, max] = lineRange(item);
                const price = state.prices[item.id] || 0;
                const lineActual = price > 0 ? price * item.qty : null;

                // Group header
                if (item.group !== currentGroup) {
                    const groupRow = document.createElement('tr');
                    groupRow.className = 'grp';
                    groupRow.innerHTML = `<td colspan="7">${item.group}</td>`;
                    bomBody.appendChild(groupRow);
                    currentGroup = item.group;
                }

                // Item row
                const row = document.createElement('tr');
                if (!isIncluded) row.className = 'off';

                // Cell 1: Checkbox + name/spec
                const cell1 = document.createElement('td');
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.checked = isIncluded;
                checkbox.addEventListener('change', () => {
                    state.included[item.id] = checkbox.checked;
                    saveState();
                    renderTable();
                    updateTotals();
                });
                cell1.appendChild(checkbox);
                const nameEl = document.createElement('b');
                nameEl.textContent = item.name;
                cell1.appendChild(nameEl);
                const specEl = document.createElement('div');
                specEl.className = 'spec';
                specEl.textContent = item.spec;
                cell1.appendChild(specEl);

                // Cell 2: Quantity
                const cell2 = document.createElement('td');
                cell2.textContent = item.qty;

                // Cell 3: Unit estimate
                const cell3 = document.createElement('td');
                cell3.textContent = `฿${item.min.toLocaleString()}–${item.max.toLocaleString()}`;

                // Cell 4: Line estimate
                const cell4 = document.createElement('td');
                cell4.textContent = `฿${min.toLocaleString()}–${max.toLocaleString()}`;

                // Cell 5: Shopee link
                const cell5 = document.createElement('td');
                const link = document.createElement('a');
                link.href = shopeeUrl(item.kw);
                link.target = '_blank';
                link.rel = 'noopener';
                link.textContent = 'ค้นใน Shopee ↗';
                cell5.appendChild(link);

                // Cell 6: Price input
                const cell6 = document.createElement('td');
                const priceInput = document.createElement('input');
                priceInput.type = 'number';
                priceInput.min = '0';
                priceInput.step = '1';
                priceInput.className = 'price';
                priceInput.dataset.id = item.id;
                priceInput.placeholder = '฿';
                priceInput.value = price > 0 ? price : '';
                // while typing: update this row and the totals only (re-rendering would steal focus)
                priceInput.addEventListener('input', () => {
                    const value = parseFloat(priceInput.value);
                    state.prices[item.id] = isNaN(value) || value <= 0 ? 0 : value;
                    const p = state.prices[item.id];
                    cell7.textContent = p > 0 ? `฿${(p * item.qty).toLocaleString()}` : '—';
                    saveState();
                    updateTotals();
                });
                priceInput.addEventListener('change', () => {
                    renderTable();
                    updateTotals();
                });
                cell6.appendChild(priceInput);

                // Cell 7: Line actual
                const cell7 = document.createElement('td');
                cell7.textContent = lineActual !== null ? `฿${lineActual.toLocaleString()}` : '—';

                row.appendChild(cell1);
                row.appendChild(cell2);
                row.appendChild(cell3);
                row.appendChild(cell4);
                row.appendChild(cell5);
                row.appendChild(cell6);
                row.appendChild(cell7);

                bomBody.appendChild(row);
            });

            updateTotals();
        }

        // Update totals display
        function updateTotals() {
            const {estMin, estMax, actual, missing} = totals(BOM, state.prices, state.included);

            totEst.textContent = `฿${estMin.toLocaleString()}–${estMax.toLocaleString()}`;
            totActual.textContent = `฿${actual.toLocaleString()}`;
            missingEl.textContent = `${missing} รายการยังไม่ใส่ราคา`;
        }

        // Save state
        function saveState() {
            try {
                localStorage.setItem('robot101.bom', JSON.stringify(state));
            } catch (e) {
                console.error('Error saving state:', e);
            }
        }

        // CSV export
        function exportCSV() {
            const header = 'กลุ่ม,รายการ,สเปก,จำนวน,ราคาประมาณต่ำ,ราคาประมาณสูง,ราคาจริงต่อชิ้น,ลิงก์\n';
            let csv = header;

            BOM.forEach(item => {
                const isIncluded = state.included[item.id] !== undefined ? state.included[item.id] : !item.optional;
                if (!isIncluded) return;

                const [min, max] = lineRange(item);
                const price = state.prices[item.id] || 0;
                const lineActual = price > 0 ? price * item.qty : '';

                const fields = [
                    item.group,
                    item.name,
                    item.spec,
                    item.qty,
                    min,
                    max,
                    price > 0 ? price : '',
                    shopeeUrl(item.kw)
                ];

                const escapedFields = fields.map(field => {
                    if (typeof field === 'string') {
                        if (field.includes(',') || field.includes('"')) {
                            return `"${field.replace(/"/g, '""')}"`;
                        }
                        return field;
                    }
                    return field;
                });

                csv += escapedFields.join(',') + '\n';
            });

            // Add UTF-8 BOM
            const bom = '\uFEFF';
            const blob = new Blob([bom + csv], {type: 'text/csv;charset=utf-8;'});
            const url = URL.createObjectURL(blob);

            const link = document.createElement('a');
            link.href = url;
            link.download = 'robot101-bom.csv';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        }

        // Event listeners
        csvBtn.addEventListener('click', exportCSV);

        // Initial render
        renderTable();
    });
}

if (typeof module !== 'undefined') {
    module.exports = { BOM, shopeeUrl, lineRange, totals };
}