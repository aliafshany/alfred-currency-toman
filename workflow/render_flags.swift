// Render "CODE<TAB>emoji" lines to CODE.png icons with the system emoji font.
// Usage: swift render_flags.swift <listing.txt> <output dir>
import AppKit

let args = CommandLine.arguments
guard args.count == 3, let listing = try? String(contentsOfFile: args[1], encoding: .utf8) else {
    FileHandle.standardError.write("usage: render_flags.swift <listing> <outdir>\n".data(using: .utf8)!)
    exit(1)
}
let outDir = URL(fileURLWithPath: args[2], isDirectory: true)
let size: CGFloat = 128
let font = NSFont(name: "Apple Color Emoji", size: size * 0.8) ?? NSFont.systemFont(ofSize: size * 0.8)
let style = NSMutableParagraphStyle()
style.alignment = .center
let attrs: [NSAttributedString.Key: Any] = [.font: font, .paragraphStyle: style]

for line in listing.split(separator: "\n") {
    let parts = line.split(separator: "\t", maxSplits: 1)
    guard parts.count == 2 else { continue }
    let text = NSAttributedString(string: String(parts[1]), attributes: attrs)
    guard let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(size), pixelsHigh: Int(size),
                                     bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                                     colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { continue }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    let bounds = text.boundingRect(with: NSSize(width: size, height: size), options: .usesLineFragmentOrigin)
    text.draw(in: NSRect(x: 0, y: (size - bounds.height) / 2, width: size, height: bounds.height))
    NSGraphicsContext.restoreGraphicsState()
    if let png = rep.representation(using: .png, properties: [:]) {
        try? png.write(to: outDir.appendingPathComponent("\(parts[0]).png"))
    }
}
