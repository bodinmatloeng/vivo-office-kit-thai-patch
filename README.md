<table align="right">
<tr>
<td align="right">สนับสนุนค่ากาแฟ<br><img width="140" alt="พร้อมเพย์ สนับสนุนค่ากาแฟ" src="coffee-qr.png"></td>
</tr>
</table>

<img src="title.svg" alt="Vivo Office Kit Thai Patch" width="490" height="48">

โครงโปรเจกต์แพตช์ภาษาไทยอย่างไม่เป็นทางการ สำหรับ Windows และ macOS

ดาวน์โหลดแพตช์ภาษาไทย Windows (ฟรี, ไม่ต้องติดตั้ง Node.js): [vivo-office-kit-thai-windows.zip](https://github.com/bodinmatloeng/vivo-office-kit-thai-patch/releases/download/windows-7.0.6/vivo-office-kit-thai-windows.zip)

ดาวน์โหลดแพตช์ภาษาไทย Mac (Apple Silicon, ไม่ต้องลง Python): [Vivo-Thai-macOS-0.2.0-preview.pkg](https://github.com/bodinmatloeng/vivo-office-kit-thai-patch/releases/download/macos-0.2.0-preview/Vivo-Thai-macOS-0.2.0-preview.pkg)

**Mac: รองรับเฉพาะชิป Apple Silicon (M1 เป็นต้นไป) — ยังไม่รองรับ Mac ชิป Intel**

Mac PKG เป็นรุ่นทดลอง ยังไม่มี Developer ID/notarization หาก macOS ปฏิเสธให้หยุดและรายงาน ไม่ปิดระบบป้องกัน

**สถานะ: ตัวติดตั้ง Windows ไม่ต้องลง Node.js และมีตัวติดตั้ง macOS รุ่นทดลองแล้ว ส่วน Mac ผ่านทดสอบเปิดแอป ฟอร์ม เชื่อมต่อ สะท้อนหน้าจอ ส่งไฟล์ และย้อนกลับบนเครื่องทดสอบแล้ว ยังเป็นรุ่นทดลอง**

เป้าหมายคือเริ่มจากแอปจีนเดิม เขียนระบบแพตช์ใหม่ และใช้คำแปลไทยที่จัดทำเอง ไม่คัดลอกโครงหรือตัวติดตั้งจากแพตช์ภาษาอังกฤษ ผู้ใช้ต้องดาวน์โหลดแอป vivo เอง

## แพลตฟอร์ม

| ระบบ | สถานะ |
| --- | --- |
| macOS | เป้าหมาย Office Kit China 7.0.6 บน Apple Silicon เท่านั้น (**ยังไม่รองรับ Mac ชิป Intel**); [คู่มือ Mac และการย้อนกลับ](platforms/macos/native/README.md) ผ่านการติดตั้ง เปิดใช้งาน และย้อนกลับบน Mac เครื่องทดสอบแล้ว |
| Windows | ตัวติดตั้งสำหรับ Office Kit จีน 7.0.6 บน Windows 64 บิต ไม่ต้องลง Node.js อยู่ใน [platforms/windows](platforms/windows/README.md) |

ผลใช้งานของแพตช์ Mac เดิมไม่ใช่ผลรับรองตัวติดตั้งใหม่ และยังมีข้อความบางส่วนที่ไม่ได้แปล

## เอกสาร

- [ตัวติดตั้ง macOS และวิธีใช้](platforms/macos/README.md)

- [แผนพัฒนาและเกณฑ์ก่อนแจก](docs/PLAN.md)
- [ไฟล์ที่ต้องเตรียมจาก Windows](docs/WINDOWS-HANDOFF.md)
- [ขอบเขตสิทธิ์และไฟล์ที่แจก](docs/DISTRIBUTION.md)

โครงนี้ไม่มีตัวแอป ไฟล์ ASAR ไฟล์สำรอง หรือข้อมูลผู้ใช้ ส่วน Windows ผู้ใช้จะใช้ Cursor พัฒนาบนอีกเครื่อง
