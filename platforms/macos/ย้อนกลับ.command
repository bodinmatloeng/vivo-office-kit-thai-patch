#!/bin/bash
set -eu
cd -- "$(dirname -- "$0")"
printf 'ย้อนกลับสู่แอปจีนต้นฉบับ — โปรดปิด vivo Office Kit ก่อน\n'
printf 'วาง path โฟลเดอร์สำรองที่ตัวติดตั้งรายงาน (ไม่ต้องใส่เครื่องหมายคำพูด)\n'
read -r -p 'โฟลเดอร์สำรอง: ' backup_folder
python3 installer.py revert --backup "$backup_folder" || { read -r -p 'กด Enter เพื่อปิด' ignored; exit 1; }
read -r -p 'กด Enter เพื่อปิด' ignored
