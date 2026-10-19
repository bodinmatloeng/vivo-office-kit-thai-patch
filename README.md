# vivo Office Kit Thai Patch

<p align="right">
<img width="140" alt="พร้อมเพย์ สนับสนุนค่ากาแฟ" src="coffee-qr.png"><br>
<sub>สนับสนุนค่ากาแฟ</sub>
</p>

โครงโปรเจกต์แพตช์ภาษาไทยอย่างไม่เป็นทางการ สำหรับ Windows และ macOS

ดาวน์โหลดแพตช์ภาษาไทย Windows (ฟรี): [vivo-office-kit-thai-windows.zip](https://github.com/bodinmatloeng/vivo-office-kit-thai-patch/releases/download/windows-7.0.6/vivo-office-kit-thai-windows.zip)

**สถานะ: มีสคริปต์ Windows และตัวติดตั้ง macOS รุ่นทดลองแล้ว ส่วน Mac ผ่าน static และติดตั้ง/ย้อนกลับบนสำเนา ยังรอทดสอบ GUI/ฟังก์ชันจริงก่อนออกชุดใช้งานทั่วไป**

เป้าหมายคือเริ่มจากแอปจีนเดิม เขียนระบบแพตช์ใหม่ และใช้คำแปลไทยที่จัดทำเอง ไม่คัดลอกโครงหรือตัวติดตั้งจากแพตช์ภาษาอังกฤษ ผู้ใช้ต้องดาวน์โหลดแอป vivo เอง

## แพลตฟอร์ม

| ระบบ | สถานะ |
| --- | --- |
| macOS | เป้าหมาย Office Kit China 7.0.6 บน Apple Silicon; [ตัวติดตั้งรุ่นทดลอง](platforms/macos/README.md) ผ่านการทดสอบบนสำเนาต้นฉบับจีนแล้ว ยังรอทดสอบเปิดแอปจริง |
| Windows | สคริปต์สำหรับ Office Kit จีน 7.0.6 บน Windows 64 บิต อยู่ใน [platforms/windows](platforms/windows/README.md) |

ผลใช้งานของแพตช์ Mac เดิมไม่ใช่ผลรับรองตัวติดตั้งใหม่ และยังมีข้อความบางส่วนที่ไม่ได้แปล

## เอกสาร

- [ตัวติดตั้ง macOS และวิธีใช้](platforms/macos/README.md)

- [แผนพัฒนาและเกณฑ์ก่อนแจก](docs/PLAN.md)
- [ไฟล์ที่ต้องเตรียมจาก Windows](docs/WINDOWS-HANDOFF.md)
- [ขอบเขตสิทธิ์และไฟล์ที่แจก](docs/DISTRIBUTION.md)

โครงนี้ไม่มีตัวแอป ไฟล์ ASAR ไฟล์สำรอง หรือข้อมูลผู้ใช้ ส่วน Windows ผู้ใช้จะใช้ Cursor พัฒนาบนอีกเครื่อง
