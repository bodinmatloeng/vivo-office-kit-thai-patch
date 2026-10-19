using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;

class FileEnt {
  public string Name;
  public Dictionary<string, object> Meta;
  public int Order;
}

class PatchThai {
  static readonly string AppDir = @"C:\Program Files (x86)\pcsuite";
  static readonly string AsarPath = Path.Combine(AppDir, "resources", "app.asar");
  static readonly string PackDir = Path.Combine(Environment.GetEnvironmentVariable("LOCALAPPDATA"), "VivoOfficeKit-Thai");
  static readonly string Backup = Path.Combine(PackDir, "app.asar.original");
  static readonly string Staged = Path.Combine(PackDir, "app.asar.patched");
  static readonly string IniPath = Path.Combine(Environment.GetEnvironmentVariable("APPDATA"), "pcsuite", "config.ini");
  static readonly Encoding Utf8 = new UTF8Encoding(false);
  static readonly JavaScriptSerializer Json = CreateJson();

  static readonly string[][] Locks = new string[][] {
    new[] { "if(!n)return\"zh_CN\"", "if(!n)return\"th_TH\"" },
    new[] { "if(!l)return\"zh_CN\"", "if(!l)return\"th_TH\"" },
    new[] { "?o():\"zh_CN\"", "?o():\"th_TH\"" },
    new[] { "?c():\"zh_CN\"", "?c():\"th_TH\"" },
    new[] { "?\"en_US\":\"zh_CN\"", "?\"en_US\":\"th_TH\"" },
    new[] { "setItem(\"currentLanguage\",\"zh_CN\")", "setItem(\"currentLanguage\",\"th_TH\")" },
    new[] { "setItem(\"vLang\",\"vzh_rCN\"),", "setItem(\"vLang\",\"vth\"),+0||" },
    new[] { "setItem(\"vLang\",\"vth\"),00||", "setItem(\"vLang\",\"vth\"),+0||" }
  };

  static readonly Dictionary<string, string> Manual = new Dictionary<string, string> {
    { "日历", "ปฏิทิน" },
    { "相册", "อัลบั้ม" },
    { "录音机", "เครื่องบันทึกเสียง" },
    { "日程", "กำหนดการ" },
    { "更多云服务", "บริการคลาวด์เพิ่มเติม" },
    { "无日程", "ไม่มีกำหนดการ" },
    { "无录音", "ไม่มีไฟล์บันทึกเสียง" },
    { "无文档", "ไม่มีเอกสาร" },
    { "去日历查看", "ดูในปฏิทิน" },
    { "导入电脑音频", "นำเข้าเสียงจากคอมพิวเตอร์" },
    { "欢迎使用相册", "ยินดีต้อนรับสู่ อัลบั้ม" },
    { "开启相册", "เปิดอัลบั้ม" },
    { "原子笔记", "โน้ตของ Origin" }
  };

  static JavaScriptSerializer CreateJson() {
    var ser = new JavaScriptSerializer();
    ser.MaxJsonLength = int.MaxValue;
    ser.RecursionLimit = 1024;
    return ser;
  }

  static void Main(string[] args) {
    Console.OutputEncoding = Encoding.UTF8;
    foreach (var pair in Locks) {
      if (Utf8.GetByteCount(pair[0]) != Utf8.GetByteCount(pair[1]))
        throw new Exception("lock length mismatch");
    }
    if (args.Length >= 4 && args[0] == "--input") {
      var built = BuildPatched(args[1]);
      File.WriteAllBytes(args[3], built.Bytes);
      Console.WriteLine("replacements " + built.Count + " bytes " + built.Bytes.Length);
    } else if (args.Length >= 1 && args[0] == "restore") {
      Restore();
    } else {
      Install();
    }
  }

  static Dictionary<string, object> AsDict(object node) {
    return node as Dictionary<string, object>;
  }

  static void Walk(object node, string name, List<FileEnt> files) {
    var dict = AsDict(node);
    if (dict == null) return;
    object filesObj;
    if (dict.TryGetValue("files", out filesObj)) {
      var children = AsDict(filesObj);
      if (children == null) return;
      foreach (var kv in children) {
        string child = name.Length == 0 ? kv.Key : name + "/" + kv.Key;
        Walk(kv.Value, child, files);
      }
    } else if (dict.ContainsKey("offset")) {
      files.Add(new FileEnt { Name = name, Meta = dict, Order = files.Count });
    }
  }

  class AsarFile {
    public Dictionary<string, object> Root;
    public byte[] Data;
    public List<FileEnt> Files;
  }

  static AsarFile ReadAsar(string path) {
    byte[] all = File.ReadAllBytes(path);
    uint headerSize = BitConverter.ToUInt32(all, 4);
    int jsonSize = BitConverter.ToInt32(all, 12);
    string headerJson = Utf8.GetString(all, 16, jsonSize);
    var root = AsDict(Json.DeserializeObject(headerJson));
    int dataStart = 8 + (int)headerSize;
    byte[] data = new byte[all.Length - dataStart];
    Buffer.BlockCopy(all, dataStart, data, 0, data.Length);
    var files = new List<FileEnt>();
    Walk(root, "", files);
    files.Sort((a, b) => {
      int cmp = long.Parse(a.Meta["offset"].ToString()).CompareTo(long.Parse(b.Meta["offset"].ToString()));
      return cmp != 0 ? cmp : a.Order.CompareTo(b.Order);
    });
    return new AsarFile { Root = root, Data = data, Files = files };
  }

  static byte[] Slice(byte[] data, Dictionary<string, object> meta) {
    int off = int.Parse(meta["offset"].ToString());
    int size = Convert.ToInt32(meta["size"]);
    byte[] buf = new byte[size];
    Buffer.BlockCopy(data, off, buf, 0, size);
    return buf;
  }

  static byte[] EncodeHeader(object root) {
    byte[] json = Utf8.GetBytes(Json.Serialize(root));
    int jsonLen = json.Length;
    int pad = (4 - ((4 + jsonLen) % 4)) % 4;
    int headerPickleSize = 8 + jsonLen + pad;
    byte[] output = new byte[8 + headerPickleSize];
    Buffer.BlockCopy(BitConverter.GetBytes(4), 0, output, 0, 4);
    Buffer.BlockCopy(BitConverter.GetBytes(headerPickleSize), 0, output, 4, 4);
    Buffer.BlockCopy(BitConverter.GetBytes(headerPickleSize - 4), 0, output, 8, 4);
    Buffer.BlockCopy(BitConverter.GetBytes(jsonLen), 0, output, 12, 4);
    Buffer.BlockCopy(json, 0, output, 16, jsonLen);
    return output;
  }

  static Dictionary<string, string> LoadLocaleJs(byte[] data, List<FileEnt> files, string name) {
    FileEnt file = files.Find(f => f.Name == name);
    string text = Utf8.GetString(Slice(data, file.Meta));
    var map = new Dictionary<string, string>();
    var re = new System.Text.RegularExpressions.Regex(@"JSON\.parse\('((?:\\'|[^'])*)'\)");
    foreach (System.Text.RegularExpressions.Match m in re.Matches(text)) {
      string raw = m.Groups[1].Value.Replace("\\'", "'").Replace("\\\\", "\\");
      try {
        var parsed = AsDict(Json.DeserializeObject(raw));
        if (parsed == null) continue;
        foreach (var kv in parsed) {
          if (kv.Value is string) map[kv.Key] = (string)kv.Value;
        }
      } catch {}
    }
    return map;
  }

  static Dictionary<string, string> LoadJson(byte[] data, List<FileEnt> files, string name) {
    FileEnt file = files.Find(f => f.Name == name);
    var parsed = AsDict(Json.DeserializeObject(Utf8.GetString(Slice(data, file.Meta))));
    var map = new Dictionary<string, string>();
    foreach (var kv in parsed) {
      if (kv.Value is string) map[kv.Key] = (string)kv.Value;
    }
    return map;
  }

  static bool HasHan(string text) {
    foreach (char c in text) if (c >= 0x4e00 && c <= 0x9fff) return true;
    return false;
  }

  static Dictionary<string, string> BuildDict(byte[] data, List<FileEnt> files) {
    var zh = LoadLocaleJs(data, files, "dist/electron/locales-zh_CN.js");
    var th = LoadLocaleJs(data, files, "dist/electron/locales-th_TH.js");
    foreach (var kv in LoadJson(data, files, "dist/electron/locales/zh_CN/framework.json")) zh[kv.Key] = kv.Value;
    foreach (var kv in LoadJson(data, files, "dist/electron/locales/th_TH/framework.json")) th[kv.Key] = kv.Value;
    var grouped = new Dictionary<string, HashSet<string>>();
    foreach (var kv in zh) {
      string t;
      if (!th.TryGetValue(kv.Key, out t)) continue;
      if (string.IsNullOrEmpty(t) || t.Trim().Length == 0 || kv.Value == t) continue;
      if (!HasHan(kv.Value)) continue;
      HashSet<string> set;
      if (!grouped.TryGetValue(kv.Value, out set)) {
        set = new HashSet<string>();
        grouped[kv.Value] = set;
      }
      set.Add(t);
    }
    var dict = new Dictionary<string, string>();
    foreach (var kv in grouped) if (kv.Value.Count == 1) foreach (var only in kv.Value) dict[kv.Key] = only;
    foreach (var kv in Manual) if (!dict.ContainsKey(kv.Key)) dict[kv.Key] = kv.Value;
    return dict;
  }

  static bool ShouldTranslate(string name) {
    if (!name.StartsWith("dist/electron/")) return false;
    if (name.Contains("locales-") || name.Contains("/locales/") || name.Contains("/static/")) return false;
    return name.EndsWith(".js") || name.EndsWith(".html");
  }

  static string QuoteJson(string value) {
    var sb = new StringBuilder(value.Length + 2);
    sb.Append('"');
    foreach (char c in value) {
      switch (c) {
        case '"': sb.Append("\\\""); break;
        case '\\': sb.Append("\\\\"); break;
        case '\b': sb.Append("\\b"); break;
        case '\f': sb.Append("\\f"); break;
        case '\n': sb.Append("\\n"); break;
        case '\r': sb.Append("\\r"); break;
        case '\t': sb.Append("\\t"); break;
        default:
          if (c < ' ' || c == '\u2028' || c == '\u2029') sb.Append("\\u").Append(((int)c).ToString("x4"));
          else sb.Append(c);
          break;
      }
    }
    sb.Append('"');
    return sb.ToString();
  }

  static string Translate(string text, Dictionary<string, string> dict, List<string> quotedPhrases, ref int count) {
    foreach (var pair in Locks) {
      int found = 0;
      int at = 0;
      while ((at = text.IndexOf(pair[0], at)) >= 0) { found++; at += pair[0].Length; }
      if (found > 0) { count += found; text = text.Replace(pair[0], pair[1]); }
    }
    foreach (var phrase in quotedPhrases) {
      string needle = "\"" + phrase + "\"";
      string thai;
      if (!dict.TryGetValue(phrase, out thai)) continue;
      string repl = QuoteJson(thai);
      int at = 0;
      while ((at = text.IndexOf(needle, at)) >= 0) {
        count++;
        text = text.Substring(0, at) + repl + text.Substring(at + needle.Length);
        at += repl.Length;
      }
    }
    var sb = new StringBuilder(text.Length + 4096);
    int i = 0;
    while (i < text.Length) {
      int q = text.IndexOf('"', i);
      if (q < 0) { sb.Append(text, i, text.Length - i); break; }
      int q2 = text.IndexOf('"', q + 1);
      if (q2 < 0) { sb.Append(text, i, text.Length - i); break; }
      string thai;
      if (dict.TryGetValue(text.Substring(q + 1, q2 - q - 1), out thai)) {
        sb.Append(text, i, q - i);
        sb.Append(QuoteJson(thai));
        count++;
        i = q2 + 1;
      } else {
        sb.Append(text, i, q - i + 1);
        i = q + 1;
      }
    }
    return sb.ToString();
  }

  class Built { public byte[] Bytes; public int Count; }

  static Built BuildPatched(string path) {
    var asar = ReadAsar(path);
    var dict = BuildDict(asar.Data, asar.Files);
    var quotedPhrases = new List<string>();
    foreach (var key in dict.Keys) if (key.IndexOf('"') >= 0) quotedPhrases.Add(key);
    quotedPhrases.Sort((a, b) => b.Length.CompareTo(a.Length));
    var chunks = new List<byte[]>();
    long offset = 0;
    int count = 0;
    foreach (var file in asar.Files) {
      byte[] buf = Slice(asar.Data, file.Meta);
      if (ShouldTranslate(file.Name)) {
        int before = count;
        string text = Translate(Utf8.GetString(buf), dict, quotedPhrases, ref count);
        if (count != before) buf = Utf8.GetBytes(text);
      }
      file.Meta["offset"] = offset.ToString();
      file.Meta["size"] = buf.Length;
      chunks.Add(buf);
      offset += buf.Length;
    }
    byte[] header = EncodeHeader(asar.Root);
    using (var ms = new MemoryStream()) {
      ms.Write(header, 0, header.Length);
      foreach (var chunk in chunks) ms.Write(chunk, 0, chunk.Length);
      return new Built { Bytes = ms.ToArray(), Count = count };
    }
  }

  static bool ContainsAscii(byte[] data, string needle) {
    return Encoding.GetEncoding(28591).GetString(data).Contains(needle);
  }

  static void UpdateIni(bool thai) {
    if (!File.Exists(IniPath)) {
      Console.WriteLine("ยังไม่พบ config.ini จะถูกตั้งเมื่อเปิดแอปครั้งถัดไป");
      return;
    }
    string text = File.ReadAllText(IniPath, Utf8);
    string id = thai ? "1054" : "2052";
    string tag = thai ? "th_TH" : "zh_CN";
    string next = System.Text.RegularExpressions.Regex.Replace(text, "(?m)^LanguageID=.*$", "LanguageID=" + id);
    next = System.Text.RegularExpressions.Regex.Replace(next, "(?m)^LanguageTag=.*$", "LanguageTag=" + tag);
    if (thai && !System.Text.RegularExpressions.Regex.IsMatch(next, "(?m)^LanguageID="))
      next = next.Replace("[PCSuite]", "[PCSuite]\r\nLanguageID=1054\r\nLanguageTag=th_TH");
    if (next != text) File.WriteAllText(IniPath, next, Utf8);
    Console.WriteLine(thai ? "ตั้งค่าภาษาใน config.ini เป็นภาษาไทยแล้ว" : "คืนค่าภาษาจีนเดิมแล้ว");
  }

  static bool CopyElevated(string from, string to) {
    string cmd = "Copy-Item -LiteralPath '" + from.Replace("'", "''") + "' -Destination '" + to.Replace("'", "''") + "' -Force";
    var psi = new ProcessStartInfo("powershell.exe", "-NoProfile -Command \"" + cmd.Replace("\"", "\\\"") + "\"");
    psi.Verb = "runas";
    psi.UseShellExecute = true;
    var proc = Process.Start(psi);
    proc.WaitForExit();
    return proc.ExitCode == 0;
  }

  static void Install() {
    if (!File.Exists(AsarPath)) {
      Console.WriteLine("ไม่พบ vivo办公套件 ที่ " + AsarPath);
      Console.WriteLine("ติดตั้งโปรแกรมจาก vivo ก่อน แล้วรันตัวนี้ซ้ำ");
      Environment.Exit(1);
    }
    Directory.CreateDirectory(PackDir);
    byte[] installed = File.ReadAllBytes(AsarPath);
    if (ContainsAscii(installed, "if(!n)return\"th_TH\"") && ContainsAscii(installed, "\"ปฏิทิน\"")) {
      UpdateIni(true);
      Console.WriteLine("เครื่องนี้ติดตั้งแพ็กภาษาไทยไว้แล้ว");
      return;
    }
    Console.WriteLine("กำลังสร้างไฟล์ภาษาไทยจากโปรแกรมที่ติดตั้งอยู่...");
    var built = BuildPatched(AsarPath);
    if (built.Count == 0) {
      Console.WriteLine("ไม่พบข้อความที่แก้ได้ เวอร์ชันของแอปอาจไม่ใช่ 7.0.6");
      Environment.Exit(1);
    }
    File.WriteAllBytes(Staged, built.Bytes);
    if (!File.Exists(Backup)) File.Copy(AsarPath, Backup);
    Console.WriteLine("ปิดแอปชั่วคราวเพื่อใส่ไฟล์ภาษา");
    Process.Start(new ProcessStartInfo("taskkill.exe", "/IM pcsuite.exe /F") { CreateNoWindow = true, UseShellExecute = false }).WaitForExit();
    Console.WriteLine("ถ้ามีหน้าต่างยืนยันสิทธิ์ผู้ดูแล ให้กด Yes");
    if (!CopyElevated(Staged, AsarPath)) {
      Console.WriteLine("คัดลอกไฟล์ไม่สำเร็จ");
      Environment.Exit(1);
    }
    UpdateIni(true);
    Process.Start(new ProcessStartInfo(Path.Combine(AppDir, "pcsuite.exe")) { WorkingDirectory = AppDir, UseShellExecute = true });
    Console.WriteLine("ติดตั้งภาษาไทยแล้ว แทนที่ข้อความ " + built.Count + " จุด");
    Console.WriteLine("สำเนาก่อนแก้เก็บไว้ที่ " + Backup);
  }

  static void Restore() {
    if (!File.Exists(Backup)) {
      Console.WriteLine("ไม่พบสำเนาก่อนแก้ที่ " + Backup);
      Environment.Exit(1);
    }
    Process.Start(new ProcessStartInfo("taskkill.exe", "/IM pcsuite.exe /F") { CreateNoWindow = true, UseShellExecute = false }).WaitForExit();
    Console.WriteLine("ถ้ามีหน้าต่างยืนยันสิทธิ์ผู้ดูแล ให้กด Yes");
    if (!CopyElevated(Backup, AsarPath)) Environment.Exit(1);
    UpdateIni(false);
  }
}
