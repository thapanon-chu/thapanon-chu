# Team Champion — Visualization

- **ผู้ใช้ที่เลือก (2 กลุ่ม):**
  1. *คนขับรถโม่ & หัวหน้าหน้างาน (Mixer Drivers & Field Dispatchers):* ติดตามสถานะเที่ยวรถ, เวลาถึงหน้างาน, และ Slump Life แบบ Real-time เพื่อป้องกันการเกิด Cold Joint
  2. *ผู้บริหาร & ฝ่ายความยั่งยืน (Executives & Green Logistics Officers):* ติดตามตัวชี้วัดกำไร Contribution รวม (1.495M THB), การผ่านเกณฑ์ SLA 100%, และการลดคาร์บอนฟุตพริ้นต์ (~4.2 ตัน CO2)

- **ไฟล์ / ลิงก์:** `dashboard_champion.html`
- **วิธีเปิด:** ดับเบิลคลิกเปิดไฟล์ `dashboard_champion.html` ในเว็บบราวเซอร์ใดก็ได้ (Chrome, Edge, Safari) ไม่ต้องเชื่อมต่ออินเทอร์เน็ต
- **ข้อมูลที่ใช้:** `out/day1` ถึง `out/day4` (`plan_loads.csv` และผลการคำนวณ KPIs จาก `evaluate.py`)
- **ทำไมดีกว่าหน้าจอเดิม (1–3 บรรทัด):**
  - แสดง Slump Life Countdown ด้วยแถบสถานะสี (Visual Safety Gauge) ทำให้คนขับและหน้างานเห็นความสดของคอนกรีตทันทีโดยไม่ต้องคำนวณเวลาเองในใจ
  - รวมมุมมองผู้บริหารที่แสดงผลลัพธ์ทั้งมิติด้านการเงิน (Contribution) และสิ่งแวดล้อม (ESG / CO2) ไว้ในหน้าเดียว ทำให้เห็นคุณค่าของการขับเคลื่อน Green Logistics อย่างชัดเจน
