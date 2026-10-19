const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const APP_DIR = "C:\\Program Files (x86)\\pcsuite";
const ASAR = path.join(APP_DIR, "resources", "app.asar");
const PACK_DIR = path.join(process.env.LOCALAPPDATA, "VivoOfficeKit-Thai");
const BACKUP = path.join(PACK_DIR, "app.asar.original");
const STAGED = path.join(PACK_DIR, "app.asar.patched");
const INI = path.join(process.env.APPDATA, "pcsuite", "config.ini");

const locks = [
  ['if(!n)return"zh_CN"', 'if(!n)return"th_TH"'],
  ['if(!l)return"zh_CN"', 'if(!l)return"th_TH"'],
  ['?o():"zh_CN"', '?o():"th_TH"'],
  ['?c():"zh_CN"', '?c():"th_TH"'],
  ['?"en_US":"zh_CN"', '?"en_US":"th_TH"'],
  ['setItem("currentLanguage","zh_CN")', 'setItem("currentLanguage","th_TH")'],
  ['setItem("vLang","vzh_rCN"),', 'setItem("vLang","vth"),+0||'],
  ['setItem("vLang","vth"),00||', 'setItem("vLang","vth"),+0||'],
];
for (const [from, to] of locks) {
  if (Buffer.from(from).length !== Buffer.from(to).length) {
    throw new Error("lock length mismatch: " + from);
  }
}

const manual = {
  日历: "ปฏิทิน",
  相册: "อัลบั้ม",
  录音机: "เครื่องบันทึกเสียง",
  日程: "กำหนดการ",
  更多云服务: "บริการคลาวด์เพิ่มเติม",
  无日程: "ไม่มีกำหนดการ",
  无录音: "ไม่มีไฟล์บันทึกเสียง",
  无文档: "ไม่มีเอกสาร",
  去日历查看: "ดูในปฏิทิน",
  导入电脑音频: "นำเข้าเสียงจากคอมพิวเตอร์",
  欢迎使用相册: "ยินดีต้อนรับสู่ อัลบั้ม",
  开启相册: "เปิดอัลบั้ม",
  原子笔记: "โน้ตของ Origin",
};

function readAsar(asarPath) {
  const fd = fs.openSync(asarPath, "r");
  const head = Buffer.alloc(16);
  fs.readSync(fd, head, 0, 16, 0);
  const headerSize = head.readUInt32LE(4);
  const jsonSize = head.readUInt32LE(12);
  const headerJsonBuf = Buffer.alloc(jsonSize);
  fs.readSync(fd, headerJsonBuf, 0, jsonSize, 16);
  const root = JSON.parse(headerJsonBuf.toString("utf8"));
  const dataStart = 8 + headerSize;
  const stat = fs.fstatSync(fd);
  const data = Buffer.alloc(stat.size - dataStart);
  fs.readSync(fd, data, 0, data.length, dataStart);
  fs.closeSync(fd);
  const files = [];
  function walk(obj, name) {
    if (!obj || typeof obj !== "object") return;
    if (obj.files) {
      for (const [k, v] of Object.entries(obj.files)) walk(v, name ? name + "/" + k : k);
    } else if ("offset" in obj) files.push({ name, meta: obj });
  }
  walk(root, "");
  files.sort((a, b) => Number(a.meta.offset) - Number(b.meta.offset));
  return { root, data, files };
}

function sliceFile(data, meta) {
  const off = Number(meta.offset);
  return data.subarray(off, off + meta.size);
}

function encodeHeader(obj) {
  const json = Buffer.from(JSON.stringify(obj));
  const jsonLen = json.length;
  const pad = (4 - ((4 + jsonLen) % 4)) % 4;
  const headerPickleSize = 8 + jsonLen + pad;
  const out = Buffer.alloc(8 + headerPickleSize);
  out.writeUInt32LE(4, 0);
  out.writeUInt32LE(headerPickleSize, 4);
  out.writeUInt32LE(headerPickleSize - 4, 8);
  out.writeUInt32LE(jsonLen, 12);
  json.copy(out, 16);
  return out;
}

function loadLocaleJs(data, files, name) {
  const file = files.find((f) => f.name === name);
  const text = sliceFile(data, file.meta).toString("utf8");
  const map = {};
  const re = /JSON\.parse\('((?:\\'|[^'])*)'\)/g;
  let m;
  while ((m = re.exec(text))) {
    const raw = m[1].replace(/\\'/g, "'").replace(/\\\\/g, "\\");
    try {
      Object.assign(map, JSON.parse(raw));
    } catch {}
  }
  return map;
}

function loadJson(data, files, name) {
  const file = files.find((f) => f.name === name);
  return JSON.parse(sliceFile(data, file.meta).toString("utf8"));
}

function buildDict(data, files) {
  const zh = loadLocaleJs(data, files, "dist/electron/locales-zh_CN.js");
  const th = loadLocaleJs(data, files, "dist/electron/locales-th_TH.js");
  Object.assign(zh, loadJson(data, files, "dist/electron/locales/zh_CN/framework.json"));
  Object.assign(th, loadJson(data, files, "dist/electron/locales/th_TH/framework.json"));
  const dict = new Map();
  const grouped = new Map();
  for (const key of Object.keys(zh)) {
    const z = zh[key];
    const t = th[key];
    if (typeof z !== "string" || typeof t !== "string" || !t.trim() || z === t) continue;
    if (!/[\u4e00-\u9fff]/.test(z)) continue;
    if (!grouped.has(z)) grouped.set(z, new Set());
    grouped.get(z).add(t);
  }
  for (const [z, set] of grouped) {
    if (set.size === 1) dict.set(z, [...set][0]);
  }
  for (const [z, t] of Object.entries(manual)) {
    if (!dict.has(z)) dict.set(z, t);
  }
  return dict;
}

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function shouldTranslate(name) {
  if (!name.startsWith("dist/electron/")) return false;
  if (name.includes("locales-") || name.includes("/locales/")) return false;
  if (name.includes("/static/")) return false;
  return name.endsWith(".js") || name.endsWith(".html");
}

function translateText(text, dict, quoted) {
  let count = 0;
  for (const [from, to] of locks) {
    if (!text.includes(from)) continue;
    const parts = text.split(from);
    count += parts.length - 1;
    text = parts.join(to);
  }
  quoted.lastIndex = 0;
  text = text.replace(quoted, (full, zh) => {
    const thai = dict.get(zh);
    if (!thai) return full;
    count++;
    return JSON.stringify(thai);
  });
  return { text, count };
}

function buildPatched(asarPath) {
  const { root, data, files } = readAsar(asarPath);
  const dict = buildDict(data, files);
  const phrases = [...dict.keys()].sort((a, b) => b.length - a.length);
  const quoted = new RegExp('"' + "(" + phrases.map(escapeRegExp).join("|") + ")" + '"', "g");
  const chunks = [];
  let offset = 0;
  let replacements = 0;
  for (const file of files) {
    let buf = Buffer.from(sliceFile(data, file.meta));
    if (shouldTranslate(file.name)) {
      const { text, count } = translateText(buf.toString("utf8"), dict, quoted);
      if (count) {
        buf = Buffer.from(text, "utf8");
        replacements += count;
      }
    }
    file.meta.offset = String(offset);
    file.meta.size = buf.length;
    chunks.push(buf);
    offset += buf.length;
  }
  return { buffer: Buffer.concat([encodeHeader(root), ...chunks]), replacements };
}

function updateIni() {
  if (!fs.existsSync(INI)) {
    console.log("ยังไม่พบ config.ini จะถูกตั้งเมื่อเปิดแอปครั้งถัดไป");
    return;
  }
  const text = fs.readFileSync(INI, "utf8");
  let next = text
    .replace(/^LanguageID=.*$/m, "LanguageID=1054")
    .replace(/^LanguageTag=.*$/m, "LanguageTag=th_TH");
  if (!/^LanguageID=/m.test(next)) next = next.replace("[PCSuite]", "[PCSuite]\r\nLanguageID=1054\r\nLanguageTag=th_TH");
  if (next !== text) fs.writeFileSync(INI, next);
  console.log("ตั้งค่าภาษาใน config.ini เป็นภาษาไทยแล้ว");
}

function copyElevated(from, to) {
  const cmd = `Copy-Item -LiteralPath '${from.replace(/'/g, "''")}' -Destination '${to.replace(/'/g, "''")}' -Force`;
  const child = spawnSync(
    "powershell.exe",
    ["-NoProfile", "-Command", "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-Command',\"" + cmd.replace(/"/g, '\\"') + "\""],
    { stdio: "inherit" }
  );
  return child.status === 0;
}

function install() {
  if (!fs.existsSync(ASAR)) {
    console.log("ไม่พบ vivo办公套件 ที่ " + ASAR);
    console.log("ติดตั้งโปรแกรมจาก vivo ก่อน แล้วรันตัวนี้ซ้ำ");
    process.exit(1);
  }
  fs.mkdirSync(PACK_DIR, { recursive: true });
  const installed = fs.readFileSync(ASAR);
  const already = installed.includes(Buffer.from('if(!n)return"th_TH"')) && installed.includes(Buffer.from('"ปฏิทิน"'));
  if (already) {
    updateIni();
    console.log("เครื่องนี้ติดตั้งแพ็กภาษาไทยไว้แล้ว");
    return;
  }
  console.log("กำลังสร้างไฟล์ภาษาไทยจากโปรแกรมที่ติดตั้งอยู่...");
  const { buffer, replacements } = buildPatched(ASAR);
  if (!replacements) {
    console.log("ไม่พบข้อความที่แก้ได้ เวอร์ชันของแอปอาจไม่ใช่ 7.0.6");
    process.exit(1);
  }
  fs.writeFileSync(STAGED, buffer);
  if (!fs.existsSync(BACKUP)) fs.copyFileSync(ASAR, BACKUP);
  console.log("ปิดแอปชั่วคราวเพื่อใส่ไฟล์ภาษา");
  spawnSync("taskkill", ["/IM", "pcsuite.exe", "/F"], { stdio: "ignore" });
  console.log("ถ้ามีหน้าต่างยืนยันสิทธิ์ผู้ดูแล ให้กด Yes");
  if (!copyElevated(STAGED, ASAR)) {
    console.log("คัดลอกไฟล์ไม่สำเร็จ");
    process.exit(1);
  }
  updateIni();
  spawnSync("powershell.exe", ["-NoProfile", "-Command", `Start-Process -FilePath '${path.join(APP_DIR, "pcsuite.exe")}' -WorkingDirectory '${APP_DIR}'`], { stdio: "ignore" });
  console.log("ติดตั้งภาษาไทยแล้ว แทนที่ข้อความ " + replacements + " จุด");
  console.log("สำเนาก่อนแก้เก็บไว้ที่ " + BACKUP);
}

function restore() {
  if (!fs.existsSync(BACKUP)) {
    console.log("ไม่พบสำเนาก่อนแก้ที่ " + BACKUP);
    process.exit(1);
  }
  spawnSync("taskkill", ["/IM", "pcsuite.exe", "/F"], { stdio: "ignore" });
  console.log("ถ้ามีหน้าต่างยืนยันสิทธิ์ผู้ดูแล ให้กด Yes");
  if (!copyElevated(BACKUP, ASAR)) process.exit(1);
  if (fs.existsSync(INI)) {
    const text = fs.readFileSync(INI, "utf8");
    fs.writeFileSync(
      INI,
      text.replace(/^LanguageID=.*$/m, "LanguageID=2052").replace(/^LanguageTag=.*$/m, "LanguageTag=zh_CN")
    );
  }
  console.log("คืนค่าภาษาจีนเดิมแล้ว");
}

const argv = process.argv.slice(2);
if (argv[0] === "--input") {
  const input = argv[1];
  const output = argv[3];
  const { buffer, replacements } = buildPatched(input);
  fs.writeFileSync(output, buffer);
  console.log("replacements", replacements, "bytes", buffer.length);
} else if (argv[0] === "restore") {
  restore();
} else {
  install();
}
