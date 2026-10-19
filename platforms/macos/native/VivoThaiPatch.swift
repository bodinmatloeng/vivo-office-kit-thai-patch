import Foundation
import AppKit
import CryptoKit
import Darwin

struct PatchFailure: Error, CustomStringConvertible {
    let description: String
    init(_ text: String) { description = text }
}
let fm = FileManager.default
let blockSize = 4 * 1024 * 1024
func hash(_ data: Data) -> String { SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() }
func fileHash(_ path: URL) throws -> String {
    let f = try FileHandle(forReadingFrom: path); defer { try? f.close() }
    var h = SHA256()
    while let d = try f.read(upToCount: blockSize), !d.isEmpty { h.update(data: d) }
    return h.finalize().map { String(format: "%02x", $0) }.joined()
}
func object(_ value: Any?) throws -> [String: Any] {
    guard let x = value as? [String: Any] else { throw PatchFailure("รูปแบบข้อมูลไม่ถูกต้อง") }; return x
}
func text(_ value: Any?) throws -> String {
    guard let x = value as? String else { throw PatchFailure("ข้อมูลข้อความไม่ครบ") }; return x
}
func integer(_ value: Any?) throws -> Int {
    guard let x = value as? NSNumber else { throw PatchFailure("ข้อมูลตัวเลขไม่ครบ") }; return x.intValue
}
func json(_ value: Any) throws -> Data { try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys, .withoutEscapingSlashes]) }
func safeURL(_ path: String) throws -> URL {
    let expanded = (path as NSString).expandingTildeInPath
    guard !expanded.split(separator: "/").contains("..") else { throw PatchFailure("ไม่รองรับ path ที่มี ..") }
    let u = URL(fileURLWithPath: expanded)
    var part = u
    while part.path != "/" {
        if let attrs = try? fm.attributesOfItem(atPath: part.path), attrs[.type] as? FileAttributeType == .typeSymbolicLink {
            throw PatchFailure("ไม่รองรับ path ที่มี symbolic link: \(part.path)")
        }
        part.deleteLastPathComponent()
    }
    return u
}
func readExactly(_ handle: FileHandle, count: Int) throws -> Data {
    var result = Data(); result.reserveCapacity(count)
    while result.count < count {
        guard let part = try handle.read(upToCount: count-result.count), !part.isEmpty else { throw PatchFailure("ข้อมูลสมาชิกไม่ครบ") }
        result.append(part)
    }
    return result
}
struct Archive {
    let handle: FileHandle
    let tree: [String: Any]
    let base: UInt64
    let size: UInt64
    init(_ url: URL) throws {
        handle = try FileHandle(forReadingFrom: url)
        size = UInt64(try integer(fm.attributesOfItem(atPath: url.path)[.size]))
        guard let d = try handle.read(upToCount: 16), d.count == 16 else { throw PatchFailure("ส่วนหัว ASAR ไม่ครบ") }
        func word(_ offset: Int) -> UInt32 { (0..<4).reduce(0) { $0 | (UInt32(d[offset+$1]) << UInt32(8*$1)) } }
        let a = word(0), b = word(4), c = word(8), length = word(12)
        guard a == 4, b >= 8, b <= 64*1024*1024, b == c+4, c >= 4, length <= c-4,
              let raw = try handle.read(upToCount: Int(length)), raw.count == Int(length) else { throw PatchFailure("ส่วนหัว ASAR ไม่รองรับ") }
        tree = try object(JSONSerialization.jsonObject(with: raw)); base = UInt64(b)+8
        guard base <= size else { throw PatchFailure("ข้อมูล ASAR ไม่ครบ") }
    }
    func read(_ node: [String: Any]) throws -> Data {
        guard node["unpacked"] as? Bool != true, let offset = UInt64(try text(node["offset"])) else { throw PatchFailure("สมาชิกไม่ได้อยู่ใน archive") }
        let count = try integer(node["size"])
        guard count >= 0, offset <= size-base, UInt64(count) <= size-base-offset else { throw PatchFailure("ตำแหน่งสมาชิกเกิน archive") }
        try handle.seek(toOffset: base+offset)
        return try readExactly(handle, count: count)
    }
}
func leaves(_ tree: [String: Any], prefix: String = "") throws -> [String: [String: Any]] {
    let files = try object(tree["files"]); var result: [String: [String: Any]] = [:]
    for (key, value) in files {
        let node = try object(value), path = prefix.isEmpty ? key : prefix+"/"+key
        if node["files"] != nil { result.merge(try leaves(node, prefix: path)) { _, b in b } }
        else { result[path] = node }
    }
    return result
}
func replacingNode(_ tree: [String: Any], path: ArraySlice<String>, node: [String: Any]) throws -> [String: Any] {
    guard let first = path.first else { return node }
    var result = tree, files = try object(tree["files"])
    files[first] = try replacingNode(object(files[first]), path: path.dropFirst(), node: node)
    result["files"] = files; return result
}
func translated(_ input: Data, spec: [String: Any]) throws -> Data {
    guard hash(input) == (try text(spec["source_sha256"])) else { throw PatchFailure("checksum สมาชิกต้นฉบับไม่ตรง") }
    guard let patches = spec["patches"] as? [[String: Any]] else { throw PatchFailure("ไม่มีข้อมูลคำแปล") }
    var last = 0
    for p in patches {
        let start = try integer(p["start"]), end = try integer(p["end"])
        guard last <= start, start < end, end <= input.count,
              hash(input.subdata(in: start..<end)) == (try text(p["source_sha256"])) else { throw PatchFailure("ตำแหน่งข้อความหรือ checksum ไม่ตรง") }; last = end
    }
    var result = input
    for p in patches.reversed() {
        result.replaceSubrange(try integer(p["start"])..<integer(p["end"]), with: Data(try text(p["replacement"]).utf8))
    }
    guard hash(result) == (try text(spec["patched_sha256"])) else { throw PatchFailure("checksum คำแปลไม่ตรง") }; return result
}
func verify(_ source: URL, output: URL, manifest: [String: Any]) throws -> Int {
    let a = try Archive(source), b = try Archive(output)
    defer { try? a.handle.close(); try? b.handle.close() }
    let old = try leaves(a.tree), new = try leaves(b.tree), specs = try object(manifest["files"])
    guard Set(old.keys) == Set(new.keys) else { throw PatchFailure("รายชื่อสมาชิก ASAR เปลี่ยน") }
    for name in old.keys.sorted() {
        let before = old[name]!, after = new[name]!
        if specs[name] == nil, !NSDictionary(dictionary: before).isEqual(to: after) { throw PatchFailure("metadata นอกขอบเขตเปลี่ยน") }
        if before["unpacked"] as? Bool == true || before["offset"] == nil { continue }
        let expected = try specs[name] == nil ? a.read(before) : translated(a.read(before), spec: object(specs[name]))
        let actual = try b.read(after)
        guard actual == expected else { throw PatchFailure("ข้อมูลสมาชิกไม่ตรง: "+name) }
        if specs[name] != nil {
            let integrity = try object(after["integrity"])
            let blocks = stride(from: 0, to: actual.count, by: blockSize).map { hash(actual.subdata(in: $0..<min($0+blockSize, actual.count))) }
            guard try text(integrity["hash"]) == hash(actual), integrity["blocks"] as? [String] == blocks else { throw PatchFailure("integrity สมาชิกไม่ตรง") }
        }
    }
    return old.count
}
func build(_ source: URL, output: URL, manifest: [String: Any]) throws -> String {
    guard try fileHash(source) == text(manifest["source_sha256"]) else { throw PatchFailure("ไม่ใช่แอปจีนต้นฉบับที่รองรับ") }
    let archive = try Archive(source); defer { try? archive.handle.close() }
    let nodes = try leaves(archive.tree), specs = try object(manifest["files"])
    var tree = archive.tree, changed: [String: Data] = [:], offset = archive.size-archive.base
    for name in specs.keys.sorted() {
        guard var node = nodes[name] else { throw PatchFailure("ไม่มีสมาชิกที่ต้องแปล") }
        let data = try translated(archive.read(node), spec: object(specs[name])); changed[name] = data
        node["offset"] = String(offset); node["size"] = data.count
        node["integrity"] = ["algorithm":"SHA256", "hash":hash(data), "blockSize":blockSize,
                             "blocks":stride(from: 0, to: data.count, by: blockSize).map { hash(data.subdata(in: $0..<min($0+blockSize, data.count))) }]
        tree = try replacingNode(tree, path: name.components(separatedBy: "/")[...], node: node); offset += UInt64(data.count)
    }
    let raw = try json(tree), paddedCount = (raw.count+3)/4*4
    var head = Data()
    for word in [4, paddedCount+8, paddedCount+4, raw.count] {
        var number = UInt32(word).littleEndian; withUnsafeBytes(of: &number) { head.append(contentsOf: $0) }
    }
    head.append(raw); head.append(Data(repeating: 0, count: paddedCount-raw.count))
    guard fm.createFile(atPath: output.path, contents: nil) else { throw PatchFailure("สร้างไฟล์ชั่วคราวไม่ได้") }
    let out = try FileHandle(forWritingTo: output)
    do {
        try out.write(contentsOf: head); try archive.handle.seek(toOffset: archive.base)
        while let chunk = try archive.handle.read(upToCount: blockSize), !chunk.isEmpty { try out.write(contentsOf: chunk) }
        for name in changed.keys.sorted() { try out.write(contentsOf: changed[name]!) }
        try out.synchronize(); try out.close()
    } catch { try? out.close(); throw error }
    _ = try verify(source, output: output, manifest: manifest)
    let result = try fileHash(output)
    if let expected = manifest["native_patched_sha256"] as? String, result != expected { throw PatchFailure("checksum archive ใหม่ไม่ตรง") }
    return result
}
func ensureStopped(_ app: URL?) throws {
    guard let app = app else { return }
    let info = try object(PropertyListSerialization.propertyList(from: Data(contentsOf: app.appendingPathComponent("Contents/Info.plist")), format: nil))
    let executable = app.appendingPathComponent("Contents/MacOS/"+(try text(info["CFBundleExecutable"]))).path
    let task = Process(), pipe = Pipe(); task.executableURL = URL(fileURLWithPath: "/bin/ps"); task.arguments = ["-axo", "comm="]; task.standardOutput = pipe
    try task.run(); let data = pipe.fileHandleForReading.readDataToEndOfFile(); task.waitUntilExit()
    guard task.terminationStatus == 0 else { throw PatchFailure("ตรวจโปรเซสไม่ได้") }
    if String(decoding: data, as: UTF8.self).components(separatedBy: "\n").contains(where: { $0.trimmingCharacters(in: .whitespaces) == executable }) {
        throw PatchFailure("โปรดปิด vivo Office Kit ผ่านเมนูออก ก่อนติดตั้งหรือย้อนกลับ")
    }
}
func atomicCopy(_ source: URL, target: URL, expected: String, app: URL?) throws {
    let staged = target.deletingLastPathComponent().appendingPathComponent(".vivo-thai-"+UUID().uuidString)
    defer { try? fm.removeItem(at: staged) }
    try fm.copyItem(at: source, to: staged)
    let attrs = try fm.attributesOfItem(atPath: target.path)
    var preserved: [FileAttributeKey: Any] = [:]
    if let mode = attrs[.posixPermissions] { preserved[.posixPermissions] = mode }
    if geteuid() == 0 {
        preserved[.ownerAccountID] = attrs[.ownerAccountID]
        preserved[.groupOwnerAccountID] = attrs[.groupOwnerAccountID]
    }
    try fm.setAttributes(preserved, ofItemAtPath: staged.path)
    guard try fileHash(staged) == fileHash(source) else { throw PatchFailure("ไฟล์ก่อนแทนที่ตรวจไม่ผ่าน") }
    let handle = try FileHandle(forWritingTo: staged); try handle.synchronize(); try handle.close()
    try ensureStopped(app)
    guard try fileHash(target) == expected else { throw PatchFailure("แอปเปลี่ยนระหว่างทำงาน จึงไม่เขียนทับ") }
    guard rename(staged.path, target.path) == 0 else { throw PatchFailure("แทนที่ไฟล์ไม่ได้: "+String(cString: strerror(errno))) }
    guard try fileHash(target) == fileHash(source) else { throw PatchFailure("checksum หลังติดตั้งไม่ตรง") }
}
func command(_ args: [String]) throws -> String {
    guard let action = args.first else { throw PatchFailure("ไม่มีคำสั่ง") }
    var options: [String: String] = [:], n = 1
    while n < args.count { guard n+1 < args.count else { throw PatchFailure("ตัวเลือกไม่ครบ") }; options[args[n]] = args[n+1]; n += 2 }
    let resourcePath = Bundle.main.resourceURL?.appendingPathComponent("translations.json").path ?? "translations.json"
    let resolvedResource = realpath(resourcePath, nil)
    let defaultManifest = resolvedResource.map { String(cString: $0) } ?? resourcePath
    if let resolvedResource = resolvedResource { free(resolvedResource) }
    let manifest = try object(JSONSerialization.jsonObject(with: Data(contentsOf: safeURL(options["--manifest"] ?? defaultManifest))))
    guard try integer(manifest["schema"]) == 1 else { throw PatchFailure("manifest ไม่รองรับ") }
    let app = try options["--archive"] == nil ? safeURL(options["--app"] ?? "/Applications/pcsuite.app") : nil
    let target = try options["--archive"].map { try safeURL($0) } ?? app!.appendingPathComponent("Contents/Resources/app.asar")
    _ = try safeURL(target.path)
    if let app = app {
        let info = try object(PropertyListSerialization.propertyList(from: Data(contentsOf: app.appendingPathComponent("Contents/Info.plist")), format: nil))
        guard try text(info["CFBundleShortVersionString"]) == text(manifest["supported_app_version"]) else { throw PatchFailure("รุ่นแอปไม่รองรับ") }
    }
    let current = try fileHash(target), original = try text(manifest["source_sha256"])
    let supported = [manifest["patched_sha256"] as? String, manifest["native_patched_sha256"] as? String].compactMap { $0 }
    if action == "build" {
        guard let output = options["--output"] else { throw PatchFailure("ต้องระบุ --output") }
        let out = try safeURL(output)
        guard !fm.fileExists(atPath: out.path) else { throw PatchFailure("ไม่เขียนทับไฟล์ build ที่มีอยู่") }
        return try build(target, output: out, manifest: manifest)
    }
    if ["check", "preflight", "install"].contains(action) {
        if supported.contains(current) { return "ติดตั้งภาษาไทยแล้ว ไม่เขียนไฟล์หรือสร้างสำรองเพิ่ม" }
        guard current == original else { throw PatchFailure("รองรับเฉพาะต้นฉบับจีน checksum ตรงกัน หรือแพตช์อิสระรุ่นที่ระบุ ไม่แก้ไฟล์ที่ไม่รู้จัก") }
        if action == "check" || action == "preflight" {
            let a = try Archive(target); defer { try? a.handle.close() }; let nodes = try leaves(a.tree), specs = try object(manifest["files"])
            for name in specs.keys { guard let node = nodes[name] else { throw PatchFailure("สมาชิกไม่ครบ") }; _ = try translated(a.read(node), spec: object(specs[name])) }
            if action == "preflight" { try ensureStopped(app) }
            return "ตรวจผ่าน: แอปจีนตรงรุ่นและ checksum ยังไม่แก้ไขไฟล์"
        }
        try ensureStopped(app)
        guard manifest["native_patched_sha256"] != nil else { throw PatchFailure("manifest ยังไม่พร้อมติดตั้ง") }
        let root = try safeURL(options["--backup-root"] ?? "/Library/Application Support/VivoOfficeKitThaiPatch/backups")
        if let app = app, root.path == app.path || root.path.hasPrefix(app.path+"/") { throw PatchFailure("ห้ามเก็บสำรองในตัวแอป") }
        try fm.createDirectory(at: root, withIntermediateDirectories: true)
        let backup = root.appendingPathComponent("stock-7.0.6-"+UUID().uuidString)
        try fm.createDirectory(at: backup, withIntermediateDirectories: false)
        let saved = backup.appendingPathComponent("app.asar"); try fm.copyItem(at: target, to: saved)
        guard try fileHash(saved) == original else { throw PatchFailure("ตรวจสำรองไม่ผ่าน") }
        let receipt: [String: Any] = ["schema":1, "target":target.path, "source_sha256":original,
                                    "patched_sha256":try text(manifest["native_patched_sha256"]), "version":manifest["native_version"] ?? "0.2.0-preview"]
        try json(receipt).write(to: backup.appendingPathComponent("receipt.json"), options: .atomic)
        let staged = backup.appendingPathComponent("staged.asar"); defer { try? fm.removeItem(at: staged) }
        _ = try build(saved, output: staged, manifest: manifest)
        try atomicCopy(staged, target: target, expected: current, app: app)
        return "ติดตั้งสำเร็จและตรวจ SHA-256 แล้ว\nสำรอง: "+backup.path
    }
    guard action == "revert", let folder = options["--backup"] else { throw PatchFailure("คำสั่งไม่รองรับ หรือยังไม่เลือกสำรอง") }
    let backup = try safeURL(folder), saved = try safeURL(backup.appendingPathComponent("app.asar").path)
    let receipt = try object(JSONSerialization.jsonObject(with: Data(contentsOf: backup.appendingPathComponent("receipt.json"))))
    guard try text(receipt["target"]) == target.path, try text(receipt["source_sha256"]) == original,
          supported.contains(try text(receipt["patched_sha256"])), try fileHash(saved) == original else { throw PatchFailure("สำรองหรือใบสำรองไม่ตรง") }
    if current == original { return "คืนต้นฉบับจีนแล้ว ไม่เขียนซ้ำ" }
    guard current == (try text(receipt["patched_sha256"])) else { throw PatchFailure("แอปเปลี่ยนหลังติดตั้ง ไม่เขียนทับ") }
    try atomicCopy(saved, target: target, expected: current, app: app)
    return "ย้อนกลับเป็นต้นฉบับจีนและตรวจ SHA-256 แล้ว"
}
func shellQuote(_ s: String) -> String { "'"+s.replacingOccurrences(of: "'", with: "'\\''")+"'" }
func appleString(_ s: String) -> String { "\""+s.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")+"\"" }
func gui() {
    let application = NSApplication.shared; application.setActivationPolicy(.regular); application.activate(ignoringOtherApps: true)
    while true {
        let alert = NSAlert(); alert.messageText = "ภาษาไทยสำหรับ vivo Office Kit"
        alert.informativeText = "รุ่นทดลองสำหรับแอปจีน 7.0.6 บน Mac Apple Silicon\nปิด Office Kit ผ่านเมนูออกก่อนติดตั้งหรือย้อนกลับ\nไม่ต้องติดตั้ง Python หรือ Node.js"
        alert.addButton(withTitle: "ตรวจและติดตั้ง"); alert.addButton(withTitle: "คืนภาษาจีน"); alert.addButton(withTitle: "ปิด")
        let choice = alert.runModal(); if choice == .alertThirdButtonReturn { return }
        do {
            var args = ["install"]
            if choice == .alertFirstButtonReturn {
                let status = try command(["preflight"])
                if status.hasPrefix("ติดตั้งภาษาไทยแล้ว") {
                    let done = NSAlert(); done.messageText = "ไม่ต้องติดตั้งซ้ำ"; done.informativeText = status; done.runModal(); continue
                }
            }
            if choice == .alertSecondButtonReturn {
                let panel = NSOpenPanel(); panel.canChooseFiles = false; panel.canChooseDirectories = true; panel.allowsMultipleSelection = false
                panel.message = "เลือกโฟลเดอร์สำรองที่มี app.asar และ receipt.json"; panel.directoryURL = URL(fileURLWithPath: "/Library/Application Support/VivoOfficeKitThaiPatch/backups")
                guard panel.runModal() == .OK, let url = panel.url else { continue }; args = ["revert", "--backup", url.path]
            }
            guard let exe = Bundle.main.executableURL else { throw PatchFailure("ไม่พบโปรแกรมติดตั้ง") }
            let cmd = ([exe.path]+args).map(shellQuote).joined(separator: " ")
            let script = NSAppleScript(source: "do shell script "+appleString(cmd)+" with administrator privileges")
            var error: NSDictionary?; let result = script?.executeAndReturnError(&error)
            if let error = error { throw PatchFailure(error[NSAppleScript.errorMessage] as? String ?? "ยกเลิกหรือดำเนินการไม่ได้") }
            let success = NSAlert(); success.messageText = "ผลการดำเนินการ"; success.informativeText = result?.stringValue ?? "เสร็จแล้ว"; success.runModal()
        } catch {
            let failure = NSAlert(); failure.alertStyle = .warning; failure.messageText = "ยังไม่ดำเนินการสำเร็จ"; failure.informativeText = String(describing: error); failure.runModal()
        }
    }
}
final class InstallerDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        DispatchQueue.main.async { gui(); NSApp.terminate(nil) }
    }
}
if CommandLine.arguments.count == 1 {
    let application = NSApplication.shared
    let delegate = InstallerDelegate()
    application.delegate = delegate
    application.setActivationPolicy(.regular)
    let bar = NSMenu(), item = NSMenuItem(), menu = NSMenu()
    menu.addItem(withTitle: "ปิดตัวติดตั้ง", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
    item.submenu = menu; bar.addItem(item); application.mainMenu = bar
    application.run()
    withExtendedLifetime(delegate) {}
}
else {
    do { print(try command(Array(CommandLine.arguments.dropFirst()))) }
    catch { fputs("หยุด: \(error)\n", stderr); exit(1) }
}
