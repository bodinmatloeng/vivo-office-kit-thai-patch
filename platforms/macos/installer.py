#!/usr/bin/env python3
"""Independent, standard-library-only, exact-base UI patch installer."""
import argparse
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
BLOCK = 4 * 1024 * 1024


class PatchError(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(BLOCK), b''):
            h.update(b)
    return h.hexdigest()


def read_index(f):
    prefix = f.read(16)
    if len(prefix) != 16:
        raise PatchError('ส่วนหัว ASAR ไม่ครบ')
    a, b, c, d = struct.unpack('<4I', prefix)
    if a != 4 or b != c + 4 or c < d + 4 or b > 64 * 1024 * 1024:
        raise PatchError('รูปแบบส่วนหัว ASAR ไม่รองรับ')
    return json.loads(f.read(d)), 8 + b


def leaves(tree, prefix=''):
    for key, node in tree.get('files', {}).items():
        name = prefix + '/' + key if prefix else key
        if 'files' in node:
            yield from leaves(node, name)
        else:
            yield name, node


def member(f, base, node):
    if node.get('unpacked') or 'offset' not in node:
        raise PatchError('รายการนี้ไม่ได้อยู่ใน archive')
    f.seek(base + int(node['offset']))
    data = f.read(node['size'])
    if len(data) != node['size']:
        raise PatchError('ข้อมูล ASAR ไม่ครบ')
    return data


def translate(data, spec):
    if digest(data) != spec['source_sha256']:
        raise PatchError('checksum ไฟล์ต้นฉบับไม่ตรง')
    last = 0
    for p in spec['patches']:
        start, end = p['start'], p['end']
        if not (last <= start < end <= len(data)):
            raise PatchError('ตำแหน่งแพตช์ผิดหรือซ้อนกัน')
        if digest(data[start:end]) != p['source_sha256']:
            raise PatchError('checksum ตำแหน่งข้อความไม่ตรง')
        last = end
    for p in reversed(spec['patches']):
        data = data[:p['start']] + p['replacement'].encode('utf-8') + data[p['end']:]
    if digest(data) != spec['patched_sha256']:
        raise PatchError('checksum ผลแปลไม่ตรง')
    return data


def build(source, output, manifest):
    if file_hash(source) != manifest['source_sha256']:
        raise PatchError('รองรับเฉพาะแอปจีนต้นฉบับที่มี checksum ตรงกัน ห้ามใช้กับ V1–V5 หรือแพตช์อังกฤษ')
    with Path(source).open('rb') as src:
        original, base = read_index(src)
        tree = copy.deepcopy(original)
        nodes = dict(leaves(tree))
        changed = {}
        offset = Path(source).stat().st_size - base
        for name, spec in sorted(manifest['files'].items()):
            data = translate(member(src, base, nodes[name]), spec)
            changed[name] = data
            nodes[name].update(size=len(data), offset=str(offset), integrity={
                'algorithm': 'SHA256', 'hash': digest(data), 'blockSize': BLOCK,
                'blocks': [digest(data[i:i + BLOCK]) for i in range(0, len(data), BLOCK)]})
            offset += len(data)
        raw = json.dumps(tree, ensure_ascii=False, separators=(',', ':')).encode()
        padded = raw + b'\0' * (-len(raw) % 4)
        with Path(output).open('wb') as dst:
            dst.write(struct.pack('<4I', 4, len(padded) + 8, len(padded) + 4, len(raw)))
            dst.write(padded)
            src.seek(base)
            shutil.copyfileobj(src, dst, BLOCK)
            for name in sorted(changed):
                dst.write(changed[name])
            dst.flush()
            os.fsync(dst.fileno())
    verify_archive(source, output, manifest)
    result = file_hash(output)
    expected = manifest.get('patched_sha256')
    if expected and result != expected:
        raise PatchError('checksum archive ที่สร้างไม่ตรงรุ่นแพตช์')
    return result


def verify_archive(source, patched, manifest):
    with Path(source).open('rb') as a, Path(patched).open('rb') as b:
        old, ab = read_index(a)
        new, bb = read_index(b)
        on, nn = dict(leaves(old)), dict(leaves(new))
        if on.keys() != nn.keys():
            raise PatchError('รายชื่อสมาชิก ASAR เปลี่ยน')
        limit = Path(patched).stat().st_size - bb
        for name, node in on.items():
            n = nn[name]
            if name not in manifest['files'] and node != n:
                raise PatchError('metadata นอกขอบเขตเปลี่ยน: ' + name)
            if node.get('unpacked') or 'offset' not in node:
                continue
            if int(n['offset']) < 0 or int(n['offset']) + n['size'] > limit:
                raise PatchError('ตำแหน่งสมาชิกเกิน archive')
            actual = member(b, bb, n)
            if name in manifest['files']:
                expected = translate(member(a, ab, node), manifest['files'][name])
                integrity = n['integrity']
                if integrity['hash'] != digest(actual) or integrity['blocks'] != [digest(actual[i:i + BLOCK]) for i in range(0, len(actual), BLOCK)]:
                    raise PatchError('integrity ไม่ตรง: ' + name)
            else:
                expected = member(a, ab, node)
            if actual != expected:
                raise PatchError('เนื้อหาสมาชิกไม่ตรง: ' + name)
        return len(on)


def safe_path(path):
    p = Path(path).expanduser().absolute()
    for parent in [p, *p.parents]:
        if parent.is_symlink():
            raise PatchError('ไม่รองรับ path ที่มี symbolic link: ' + str(parent))
    return p


def ensure_stopped(app):
    if app is None:
        return
    with (app / 'Contents/Info.plist').open('rb') as f:
        executable = plistlib.load(f)['CFBundleExecutable']
    executable_path = str(app / 'Contents/MacOS' / executable)
    try:
        result = subprocess.run(['/bin/ps', '-axo', 'comm='], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        raise PatchError('ตรวจสถานะโปรเซสไม่ได้ ยังไม่ติดตั้งหรือย้อนกลับ') from e
    if any(line.strip() == executable_path for line in result.stdout.splitlines()):
        raise PatchError('โปรดปิด vivo Office Kit ตามปกติก่อนติดตั้งหรือย้อนกลับ')


def atomic_copy(source, target, expected_current, app=None):
    fd, temp_name = tempfile.mkstemp(prefix='.vivo-thai-', dir=target.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        shutil.copy2(source, temp)
        shutil.copystat(target, temp)
        with temp.open('rb') as f:
            os.fsync(f.fileno())
        if file_hash(temp) != file_hash(source):
            raise PatchError('ตรวจไฟล์ก่อนแทนที่ไม่ผ่าน')
        ensure_stopped(app)
        if file_hash(target) != expected_current:
            raise PatchError('แอปเปลี่ยนระหว่างทำงาน จึงยกเลิกการแทนที่')
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def load_manifest():
    m = json.loads((HERE / 'translations.json').read_text())
    if m.get('schema') != 1:
        raise PatchError('manifest ไม่รองรับ')
    return m


def main(argv=None):
    parser = argparse.ArgumentParser(description='แพตช์ภาษาไทยอิสระสำหรับ vivo Office Kit จีน — macOS รุ่นทดลอง')
    parser.add_argument('action', choices=['check', 'install', 'revert'])
    parser.add_argument('--app', default='/Applications/pcsuite.app')
    parser.add_argument('--archive', help='ใช้ archive สำเนาสำหรับทดสอบ; ไม่ตรวจ bundle version')
    parser.add_argument('--backup-root', default='~/Library/Application Support/vivo-office-kit-thai-patch/backups')
    parser.add_argument('--backup', help='โฟลเดอร์สำรองที่ต้องการคืน ใช้คู่กับ revert')
    args = parser.parse_args(argv)
    m = load_manifest()
    app = None if args.archive else safe_path(args.app)
    target = safe_path(args.archive) if args.archive else safe_path(app / 'Contents/Resources/app.asar')
    if not target.is_file():
        raise PatchError('ไม่พบ app.asar')
    if app is not None:
        with (app / 'Contents/Info.plist').open('rb') as f:
            info = plistlib.load(f)
        if info.get('CFBundleShortVersionString') != m['supported_app_version']:
            raise PatchError('รุ่นแอปไม่ตรงกับรุ่นที่รองรับ')
    current = file_hash(target)
    if args.action in ['check', 'install']:
        if current == m['patched_sha256']:
            print('ติดตั้งแพตช์รุ่นนี้แล้ว ไม่เขียนไฟล์หรือสร้างสำรองเพิ่ม')
            return 0
        if current != m['source_sha256']:
            raise PatchError('แอปไม่ใช่ต้นฉบับจีนที่รองรับ ไม่แก้ไขไฟล์')
        if args.action == 'check':
            with target.open('rb') as f:
                tree, base = read_index(f)
                nodes = dict(leaves(tree))
                for name, spec in m['files'].items():
                    translate(member(f, base, nodes[name]), spec)
            print('ตรวจผ่าน: ฐานจีนตรง checksum และตำแหน่งคำแปลครบ ยังไม่แก้ไฟล์')
            return 0
        ensure_stopped(app)
        backup_root = safe_path(args.backup_root)
        if app and (backup_root == app or app in backup_root.parents):
            raise PatchError('ห้ามเก็บสำรองในตัวแอป')
        backup_root.mkdir(parents=True, exist_ok=True)
        backup = Path(tempfile.mkdtemp(prefix='stock-7.0.6-', dir=backup_root))
        original = backup / 'app.asar'
        shutil.copy2(target, original)
        if file_hash(original) != m['source_sha256']:
            raise PatchError('สำรอง checksum ไม่ผ่าน ไม่ติดตั้ง')
        receipt = {'schema': 1, 'target': str(target), 'source_sha256': current,
                   'patched_sha256': m['patched_sha256'], 'version': m['version'],
                   'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        (backup / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
        with tempfile.TemporaryDirectory(prefix='vivo-thai-build-', dir=backup_root) as temp:
            built = Path(temp) / 'app.asar'
            build(original, built, m)
            atomic_copy(built, target, current, app)
        print('ติดตั้งสำเร็จ ตรวจ SHA-256 แล้ว\nสำรอง: ' + str(backup))
        return 0
    if not args.backup:
        raise PatchError('revert ต้องระบุ --backup โฟลเดอร์สำรอง')
    backup = safe_path(args.backup)
    receipt = json.loads((backup / 'receipt.json').read_text())
    original = safe_path(backup / 'app.asar')
    if receipt.get('target') != str(target) or receipt.get('source_sha256') != m['source_sha256'] or receipt.get('patched_sha256') != m['patched_sha256']:
        raise PatchError('ใบสำรองไม่ตรงแอปหรือรุ่นแพตช์')
    if file_hash(original) != m['source_sha256']:
        raise PatchError('สำรองเสียหาย ไม่ย้อนกลับ')
    if current == m['source_sha256']:
        print('คืนต้นฉบับแล้ว ไม่เขียนซ้ำ')
        return 0
    if current != m['patched_sha256']:
        raise PatchError('แอปเปลี่ยนหลังติดตั้ง ไม่เขียนทับไฟล์ที่ไม่รู้จัก')
    ensure_stopped(app)
    atomic_copy(original, target, current, app)
    print('ย้อนกลับสู่แอปจีนต้นฉบับสำเร็จ ตรวจ SHA-256 แล้ว')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (PatchError, OSError, ValueError, KeyError) as e:
        print('หยุด: ' + str(e), file=sys.stderr)
        if isinstance(e, PermissionError):
            print('ไม่มีสิทธิ์เขียนปลายทาง ไม่ขอ sudo หรือเปลี่ยนสิทธิ์อัตโนมัติ', file=sys.stderr)
        sys.exit(1)
