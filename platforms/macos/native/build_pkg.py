#!/usr/bin/env python3
# coding: utf-8
"""Developer build helper only; installed package has no Python dependency."""
import argparse, hashlib, json, os, pathlib, shutil, subprocess, plistlib

R = pathlib.Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--work', required=True)
parser.add_argument('--output', required=True)
a = parser.parse_args()
w = pathlib.Path(a.work).resolve(); output = pathlib.Path(a.output).resolve()
w.mkdir(parents=True, exist_ok=True); output.parent.mkdir(parents=True, exist_ok=True)
def run(*args): subprocess.run(list(map(str,args)), check=True)
engine = w / 'VivoThaiPatch'
run('/usr/bin/swiftc', '-O', '-target', 'arm64-apple-macos11.0', '-module-cache-path', (w/'module-cache').resolve(), R/'VivoThaiPatch.swift', '-o', engine)
manifest = json.loads((R.parent/'translations.json').read_text())
if not manifest.get('native_patched_sha256'):
    raise SystemExit('Native build checksum must be validated before packaging')
root = w/'payload'; app = root/'Applications/Vivo Thai Patch.app'; resources = app/'Contents/Resources'; executable = app/'Contents/MacOS/VivoThaiPatch'
resources.mkdir(parents=True, exist_ok=True); executable.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(engine,executable); shutil.copy2(R.parent/'translations.json',resources/'translations.json')
shutil.copy2(R/'README.md', resources/'README.md')
shutil.copy2(R/'validation.json', resources/'validation.json')
info = {'CFBundleIdentifier':'community.vivo.officekit.thai.installer', 'CFBundleName':'Vivo Thai Patch',
        'CFBundleDisplayName':'ตัวติดตั้งภาษาไทย vivo', 'CFBundleExecutable':'VivoThaiPatch', 'CFBundlePackageType':'APPL',
        'CFBundleVersion':'0.2.0','CFBundleShortVersionString':'0.2.0','LSMinimumSystemVersion':'11.0',
        'NSHighResolutionCapable':True, 'LSApplicationCategoryType':'public.app-category.utilities'}
(app/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
scripts = w/'scripts'; scripts.mkdir(exist_ok=True)
shutil.copy2(engine,scripts/'VivoThaiPatch'); shutil.copy2(R.parent/'translations.json',scripts/'translations.json')
for name, action in [('preinstall','preflight'),('postinstall','install')]:
    p = scripts/name
    p.write_text('#!/bin/sh\nset -eu\nSCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"\n"$SCRIPT_DIR/VivoThaiPatch" '+action+' --manifest "$SCRIPT_DIR/translations.json" --app /Applications/pcsuite.app\n')
    p.chmod(0o755)
components = w/'components.plist'
components.write_bytes(plistlib.dumps([{'RootRelativeBundlePath':'Applications/Vivo Thai Patch.app','BundleIsRelocatable':False,'BundleHasStrictIdentifier':True,'BundleIsVersionChecked':True,'BundleOverwriteAction':'upgrade'}]))
component = w/'component.pkg' 
run('/usr/bin/pkgbuild','--root',root,'--scripts',scripts,'--identifier','community.vivo.officekit.thai.installer',
    '--component-plist',components,'--version','0.2.0','--install-location','/','--ownership','recommended',component)
docs = w/'installer-resources'; docs.mkdir(exist_ok=True)
welcome = docs/'welcome.html'; welcome.write_text('''<!doctype html><html lang="th"><meta charset="utf-8"><body style="font-family: -apple-system; font-size:15px"><h2>ภาษาไทยสำหรับ vivo Office Kit</h2><p>รุ่นทดลอง 0.2.0 สำหรับ Mac ชิป Apple และแอปจีน 7.0.6 ที่ checksum ตรงกัน</p><p>ไม่ต้องติดตั้ง Python หรือ Node.js โปรดติดตั้งแอป vivo จากผู้ผลิตและเปิดให้ผ่านก่อน หากเป็นต้นฉบับจีน ให้ปิดผ่านเมนูออกก่อนดำเนินการ</p><p>แพ็กเกจจะติดตั้งเครื่องมือ Vivo Thai Patch ใน Applications สำรอง app.asar จีนก่อนแก้ และตรวจ checksum ก่อน/หลัง มีเครื่องมือคืนภาษาจีนให้ในแอปเดียวกัน</p><p>ไม่รวมตัวแอป vivo ไม่เปลี่ยนข้อมูลผู้ใช้ ไม่ resign แอป ไม่ปิด Gatekeeper/SIP</p><p>แพ็กเกจนี้ยังไม่มี Developer ID และยังไม่ผ่าน notarization หาก macOS ปฏิเสธให้หยุดและรายงาน ไม่ปิดระบบป้องกัน</p></body></html>''')
conclusion = docs/'conclusion.html'; conclusion.write_text('''<!doctype html><html lang="th"><meta charset="utf-8"><body style="font-family: -apple-system; font-size:15px"><h2>เสร็จสิ้น</h2><p>เปิด vivo Office Kit ตามปกติ</p><p>สำรองที่สร้างใหม่อยู่ใน /Library/Application Support/VivoOfficeKitThaiPatch/backups/ เก็บไว้เพื่อย้อนกลับ ห้ามอัปโหลดสำรองขึ้น GitHub</p><p>ต้องการคืนภาษาจีน: ปิด Office Kit แล้วเปิด Vivo Thai Patch ใน Applications เลือก “คืนภาษาจีน” และเลือกโฟลเดอร์สำรอง</p><p>ถ้ามีแพตช์อิสระรุ่นที่รองรับอยู่แล้ว ตัวติดตั้งจะไม่เขียน app.asar หรือสร้างสำรองใหม่ ให้ใช้สำรองเดิมของคุณ</p><p>ยังมีข้อความบางส่วนที่เป็นจีน และยังไม่ทดสอบสำรอง/กู้คืนข้อมูลโทรศัพท์เต็มรูปแบบ</p></body></html>''')
(w/'distribution.xml').write_text('''<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
<title>ภาษาไทยสำหรับ vivo Office Kit — รุ่นทดลอง</title>
<options customize="never" require-scripts="true" hostArchitectures="arm64"/>
<domains enable_localSystem="true" enable_currentUserHome="false" enable_anywhere="false"/>
<volume-check><allowed-os-versions><os-version min="11.0"/></allowed-os-versions></volume-check>
<welcome file="welcome.html" mime-type="text/html"/>
<conclusion file="conclusion.html" mime-type="text/html"/>
<choices-outline><line choice="thai"/></choices-outline>
<choice id="thai" title="ภาษาไทยและเครื่องมือย้อนกลับ"><pkg-ref id="community.vivo.officekit.thai.installer"/></choice>
<pkg-ref id="community.vivo.officekit.thai.installer" version="0.2.0" auth="Root">component.pkg</pkg-ref>
</installer-gui-script>
''')
run('/usr/bin/productbuild','--distribution',w/'distribution.xml','--resources',docs,'--package-path',w,output)
output.with_suffix('.sha256.txt').write_text(hashlib.sha256(output.read_bytes()).hexdigest()+'  '+output.name+'\n')
print(output)
