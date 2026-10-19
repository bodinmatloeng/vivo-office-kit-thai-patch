<table align="right">
<tr>
<td align="right">สนับสนุนค่ากาแฟ<br><img width="140" alt="พร้อมเพย์ สนับสนุนค่ากาแฟ" src="coffee-qr.png"></td>
</tr>
</table>

<p><b>Vivo Office Kit Thai Patch</b></p>

โครงโปรเจกต์แพตช์ภาษาไทยอย่างไม่เป็นทางการ สำหรับ Windows และ macOS

ดาวน์โหลดแพตช์ภาษาไทย Windows (ฟรี): [vivo-office-kit-thai-windows.zip](https://github.com/bodinmatloeng/vivo-office-kit-thai-patch/releases/download/windows-7.0.6/vivo-office-kit-thai-windows.zip)

**สถานะ: มีสคริปต์ Windows และตัวติดตั้ง macOS รุ่นทดลองแล้ว ส่วน Mac ผ่านทดสอบเปิดแอป ฟอร์ม เชื่อมต่อ สะท้อนหน้าจอ ส่งไฟล์ และย้อนกลับบนเครื่องทดสอบแล้ว ยังเป็นรุ่นทดลอง**

เป้าหมายคือเริ่มจากแอปจีนเดิม เขียนระบบแพตช์ใหม่ และใช้คำแปลไทยที่จัดทำเอง ไม่คัดลอกโครงหรือตัวติดตั้งจากแพตช์ภาษาอังกฤษ ผู้ใช้ต้องดาวน์โหลดแอป vivo เอง

## แพลตฟอร์ม

| ระบบ | สถานะ |
| --- | --- |
| macOS | เป้าหมาย Office Kit China 7.0.6 บน Apple Silicon; [ตัวติดตั้งรุ่นทดลอง](platforms/macos/README.md) ผ่านการติดตั้ง เปิดใช้งาน และย้อนกลับบน Mac เครื่องทดสอบแล้ว |
| Windows | สคริปต์สำหรับ Office Kit จีน 7.0.6 บน Windows 64 บิต อยู่ใน [platforms/windows](platforms/windows/README.md) |

ผลใช้งานของแพตช์ Mac เดิมไม่ใช่ผลรับรองตัวติดตั้งใหม่ และยังมีข้อความบางส่วนที่ไม่ได้แปล

## เอกสาร

- [ตัวติดตั้ง macOS และวิธีใช้](platforms/macos/README.md)

- [แผนพัฒนาและเกณฑ์ก่อนแจก](docs/PLAN.md)
- [ไฟล์ที่ต้องเตรียมจาก Windows](docs/WINDOWS-HANDOFF.md)
- [ขอบเขตสิทธิ์และไฟล์ที่แจก](docs/DISTRIBUTION.md)

โครงนี้ไม่มีตัวแอป ไฟล์ ASAR ไฟล์สำรอง หรือข้อมูลผู้ใช้ ส่วน Windows ผู้ใช้จะใช้ Cursor พัฒนาบนอีกเครื่อง
