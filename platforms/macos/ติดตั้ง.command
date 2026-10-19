#!/bin/bash
set -eu
cd -- "$(dirname -- "$0")"
printf 'แพตช์ภาษาไทย Mac รุ่นทดลอง — ใช้เฉพาะแอปจีนต้นฉบับที่รองรับ\n'
printf 'โปรดปิด vivo Office Kit ตามปกติก่อนติดตั้ง\n'
if ! command -v python3 >/dev/null 2>&1; then
  printf 'ต้องติดตั้ง Python 3.9 ขึ้นไปก่อน ไม่ดาวน์โหลดให้อัตโนมัติ\n'
  read -r -p 'กด Enter เพื่อปิด' ignored
  exit 1
fi
if ! python3 installer.py check; then
  read -r -p 'กด Enter เพื่อปิด' ignored
  exit 1
fi
read -r -p 'ติดตั้งพร้อมสำรองต้นฉบับหรือไม่? พิมพ์ y แล้วกด Enter: ' answer
if [ "$answer" = 'y' ]; then
  python3 installer.py install || { read -r -p 'กด Enter เพื่อปิด' ignored; exit 1; }
fi
read -r -p 'กด Enter เพื่อปิด' ignored
