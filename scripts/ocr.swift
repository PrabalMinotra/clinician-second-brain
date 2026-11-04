import Foundation
import Vision
import AppKit
import PDFKit
let url = URL(fileURLWithPath: CommandLine.arguments[1])
var rows = [[String:Any]]()
func recognise(_ image: CGImage, page: Int) throws {
 let request = VNRecognizeTextRequest()
 request.recognitionLevel = .accurate
 request.usesLanguageCorrection = false
 request.recognitionLanguages = ["en-US"]
 try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
 for observation in request.results ?? [] {
  if let candidate=observation.topCandidates(1).first { rows.append(["text":candidate.string,"confidence":candidate.confidence,"page":page]) }
 }
}
do {
 if url.pathExtension.lowercased()=="pdf" {
  guard let pdf=PDFDocument(url:url),pdf.pageCount<=30,!pdf.isEncrypted else { exit(2) }
  for i in 0..<pdf.pageCount {
   guard let page=pdf.page(at:i) else { continue }
   let bounds=page.bounds(for:.mediaBox)
   let scale=2000/max(bounds.width,bounds.height)
   let thumbnail=page.thumbnail(of:NSSize(width:bounds.width*scale,height:bounds.height*scale),for:.mediaBox)
   if let cg=thumbnail.cgImage(forProposedRect:nil,context:nil,hints:nil) {try recognise(cg,page:i+1)}
  }
 } else {
  guard let image=NSImage(contentsOf:url),let cg=image.cgImage(forProposedRect:nil,context:nil,hints:nil) else {exit(2)}
  try recognise(cg,page:1)
 }
 let data=try JSONSerialization.data(withJSONObject:rows)
 print(String(data:data,encoding:.utf8)!)
} catch {fputs("OCR failed",stderr);exit(1)}
