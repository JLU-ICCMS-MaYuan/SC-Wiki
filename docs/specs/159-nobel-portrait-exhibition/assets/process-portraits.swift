import AppKit
import CoreImage

let sourceDirectory = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let outputDirectory = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
try FileManager.default.createDirectory(at: outputDirectory, withIntermediateDirectories: true)

let context = CIContext(options: [.useSoftwareRenderer: false])
let sources = try FileManager.default.contentsOfDirectory(at: sourceDirectory, includingPropertiesForKeys: nil)
  .filter { ["jpg", "jpeg", "png"].contains($0.pathExtension.lowercased()) }
  .sorted { $0.lastPathComponent < $1.lastPathComponent }

for sourceURL in sources {
  guard let source = CIImage(contentsOf: sourceURL) else { fatalError("无法读取：\(sourceURL.lastPathComponent)") }
  let width = source.extent.width
  let height = source.extent.height
  let targetRatio: CGFloat = 4.0 / 5.0
  let cropWidth = min(width, height * targetRatio)
  let cropHeight = cropWidth / targetRatio
  let crop = CGRect(x: source.extent.midX - cropWidth / 2, y: source.extent.midY - cropHeight / 2, width: cropWidth, height: cropHeight)
  let cropped = source.cropped(to: crop)

  let line = CIFilter(name: "CILineOverlay")!
  line.setValue(cropped, forKey: kCIInputImageKey)
  line.setValue(0.06, forKey: "inputNRNoiseLevel")
  line.setValue(0.72, forKey: "inputNRSharpness")
  line.setValue(0.9, forKey: "inputEdgeIntensity")
  line.setValue(0.2, forKey: "inputThreshold")
  line.setValue(15.0, forKey: "inputContrast")
  guard let outlined = line.outputImage else { fatalError("线稿处理失败：\(sourceURL.lastPathComponent)") }

  let gray = CIFilter(name: "CIColorControls")!
  gray.setValue(outlined, forKey: kCIInputImageKey)
  gray.setValue(0.0, forKey: kCIInputSaturationKey)
  guard let grayscale = gray.outputImage else { fatalError("灰度处理失败：\(sourceURL.lastPathComponent)") }
  let color = CIFilter(name: "CIColorMatrix")!
  color.setValue(grayscale, forKey: kCIInputImageKey)
  color.setValue(CIVector(x: 1.0, y: 0.0, z: 0.0, w: 0.0), forKey: "inputRVector")
  color.setValue(CIVector(x: 0.0, y: 0.88, z: 0.0, w: 0.0), forKey: "inputGVector")
  color.setValue(CIVector(x: 0.0, y: 0.0, z: 0.64, w: 0.0), forKey: "inputBVector")
  color.setValue(CIVector(x: 0.025, y: 0.015, z: 0.0, w: 0.0), forKey: "inputBiasVector")
  guard let toned = color.outputImage else { fatalError("着色失败：\(sourceURL.lastPathComponent)") }

  let sharpen = CIFilter(name: "CISharpenLuminance")!
  sharpen.setValue(toned, forKey: kCIInputImageKey)
  sharpen.setValue(0.18, forKey: "inputSharpness")
  let final = sharpen.outputImage ?? toned
  guard let cgImage = context.createCGImage(final, from: crop) else { fatalError("无法导出：\(sourceURL.lastPathComponent)") }
  let bitmap = NSBitmapImageRep(cgImage: cgImage)
  guard let data = bitmap.representation(using: .jpeg, properties: [.compressionFactor: 0.9]) else { fatalError("JPEG 编码失败") }
  let name = sourceURL.deletingPathExtension().lastPathComponent + "-comic.jpg"
  try data.write(to: outputDirectory.appendingPathComponent(name))
  print("已生成 \(name)")
}
