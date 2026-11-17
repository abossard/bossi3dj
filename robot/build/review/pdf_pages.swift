// Read a PDF without poppler: print its text per page and render each page to a JPEG.
//
//   swift robot/build/review/pdf_pages.swift FILE.pdf OUT_DIR [WIDTH]
//
// Writes OUT_DIR/text.txt (pages separated by "=== page N ===") and OUT_DIR/page_NN.jpg (WIDTH px wide, default 900).
// Used for the Geo-Scatter biome pack manuals in robot/assets/.
import AppKit
import Foundation
import PDFKit

let args = CommandLine.arguments
guard args.count >= 3, let doc = PDFDocument(url: URL(fileURLWithPath: args[1])) else {
    FileHandle.standardError.write("usage: pdf_pages.swift FILE.pdf OUT_DIR [WIDTH]\n".data(using: .utf8)!)
    exit(1)
}
let out = URL(fileURLWithPath: args[2])
let width = args.count > 3 ? CGFloat(Double(args[3]) ?? 900) : 900
try FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
var text = ""
for i in 0..<doc.pageCount {
    guard let page = doc.page(at: i) else { continue }
    text += "=== page \(i + 1) ===\n" + (page.string ?? "") + "\n"
    let box = page.bounds(for: .mediaBox)
    let size = NSSize(width: width, height: width * box.height / box.width)
    let img = page.thumbnail(of: size, for: .mediaBox)
    if let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
       let jpg = rep.representation(using: .jpeg, properties: [.compressionFactor: 0.82]) {
        try jpg.write(to: out.appendingPathComponent(String(format: "page_%02d.jpg", i + 1)))
    }
}
try text.write(to: out.appendingPathComponent("text.txt"), atomically: true, encoding: .utf8)
print("\(args[1]): \(doc.pageCount) pages")
