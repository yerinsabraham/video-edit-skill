// Local face detection and person segmentation with Apple's Vision framework.
//
//   vision-helper faces <video> [samples]        -> JSON face boxes on stdout
//   vision-helper mask <video> <out.mov> [fast|balanced|accurate] [start] [duration]
//
// Face boxes are normalised, origin top-left: {"t":1.2,"x":0.38,"y":0.21,"w":0.24,"h":0.17}.
// The mask is a white-on-black H.264 video at the source size and frame rate:
// white where a person is, ready for ffmpeg alphamerge.

import AVFoundation
import CoreImage
import Foundation
import Vision

func fail(_ message: String) -> Never {
    FileHandle.standardError.write((message + "\n").data(using: .utf8)!)
    exit(1)
}

func orientedSize(_ track: AVAssetTrack) -> CGSize {
    let size = track.naturalSize.applying(track.preferredTransform)
    return CGSize(width: abs(size.width), height: abs(size.height))
}

func faces(path: String, samples: Int) {
    let asset = AVURLAsset(url: URL(fileURLWithPath: path))
    let duration = CMTimeGetSeconds(asset.duration)
    let generator = AVAssetImageGenerator(asset: asset)
    generator.appliesPreferredTrackTransform = true
    generator.requestedTimeToleranceBefore = CMTime(seconds: 0.2, preferredTimescale: 600)
    generator.requestedTimeToleranceAfter = CMTime(seconds: 0.2, preferredTimescale: 600)
    var rows: [String] = []
    let count = max(1, samples)
    for i in 0..<count {
        let t = duration * (Double(i) + 0.5) / Double(count)
        guard let image = try? generator.copyCGImage(at: CMTime(seconds: t, preferredTimescale: 600), actualTime: nil) else { continue }
        let request = VNDetectFaceRectanglesRequest()
        try? VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
        let found = (request.results ?? []).sorted { $0.boundingBox.width * $0.boundingBox.height > $1.boundingBox.width * $1.boundingBox.height }
        if let face = found.first {
            let b = face.boundingBox
            rows.append(String(format: "{\"t\":%.2f,\"x\":%.4f,\"y\":%.4f,\"w\":%.4f,\"h\":%.4f}", t, b.minX, 1 - b.maxY, b.width, b.height))
        }
    }
    print("[" + rows.joined(separator: ",") + "]")
}

func mask(path: String, out: String, quality: String, start: Double, length: Double) {
    let asset = AVURLAsset(url: URL(fileURLWithPath: path))
    guard let track = asset.tracks(withMediaType: .video).first else { fail("no video track") }
    let size = orientedSize(track)
    let fps = track.nominalFrameRate > 0 ? track.nominalFrameRate : 30
    let total = CMTimeGetSeconds(asset.duration)
    let span = length > 0 ? min(length, total - start) : total - start

    guard let reader = try? AVAssetReader(asset: asset) else { fail("cannot read \(path)") }
    reader.timeRange = CMTimeRange(start: CMTime(seconds: start, preferredTimescale: 600), duration: CMTime(seconds: span, preferredTimescale: 600))
    let output = AVAssetReaderTrackOutput(track: track, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
    output.alwaysCopiesSampleData = false
    reader.add(output)

    let url = URL(fileURLWithPath: out)
    try? FileManager.default.removeItem(at: url)
    guard let writer = try? AVAssetWriter(outputURL: url, fileType: .mov) else { fail("cannot write \(out)") }
    let input = AVAssetWriterInput(mediaType: .video, outputSettings: [
        AVVideoCodecKey: AVVideoCodecType.h264,
        AVVideoWidthKey: Int(size.width),
        AVVideoHeightKey: Int(size.height),
        AVVideoCompressionPropertiesKey: [AVVideoAverageBitRateKey: 8_000_000],
    ])
    input.expectsMediaDataInRealTime = false
    let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
        kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
        kCVPixelBufferWidthKey as String: Int(size.width),
        kCVPixelBufferHeightKey as String: Int(size.height),
    ])
    writer.add(input)
    reader.startReading()
    writer.startWriting()
    writer.startSession(atSourceTime: .zero)

    let request = VNGeneratePersonSegmentationRequest()
    request.qualityLevel = quality == "fast" ? .fast : (quality == "accurate" ? .accurate : .balanced)
    request.outputPixelFormat = kCVPixelFormatType_OneComponent8
    let context = CIContext()
    let transform = track.preferredTransform
    var frame: Int64 = 0

    while let sample = output.copyNextSampleBuffer() {
        guard let pixels = CMSampleBufferGetImageBuffer(sample) else { continue }
        var source = CIImage(cvPixelBuffer: pixels)
        if !transform.isIdentity {
            source = source.transformed(by: transform)
            source = source.transformed(by: CGAffineTransform(translationX: -source.extent.minX, y: -source.extent.minY))
        }
        let handler = VNImageRequestHandler(ciImage: source, options: [:])
        try? handler.perform([request])
        var maskImage = CIImage(color: .black).cropped(to: CGRect(origin: .zero, size: size))
        if let result = request.results?.first?.pixelBuffer {
            let raw = CIImage(cvPixelBuffer: result)
            let sx = size.width / raw.extent.width, sy = size.height / raw.extent.height
            maskImage = raw.transformed(by: CGAffineTransform(scaleX: sx, y: sy))
        }
        while !input.isReadyForMoreMediaData { usleep(2000) }
        guard let pool = adaptor.pixelBufferPool else { fail("no pixel buffer pool") }
        var buffer: CVPixelBuffer?
        CVPixelBufferPoolCreatePixelBuffer(nil, pool, &buffer)
        guard let target = buffer else { continue }
        context.render(maskImage, to: target)
        adaptor.append(target, withPresentationTime: CMTime(value: frame, timescale: CMTimeScale(fps.rounded())))
        frame += 1
    }
    input.markAsFinished()
    let done = DispatchSemaphore(value: 0)
    writer.finishWriting { done.signal() }
    done.wait()
    if writer.status != .completed { fail("mask write failed: \(String(describing: writer.error))") }
    print("{\"frames\":\(frame),\"width\":\(Int(size.width)),\"height\":\(Int(size.height))}")
}

let args = CommandLine.arguments
guard args.count >= 3 else { fail("usage: vision-helper faces <video> [samples] | mask <video> <out.mov> [quality] [start] [duration]") }
switch args[1] {
case "faces":
    faces(path: args[2], samples: args.count > 3 ? Int(args[3]) ?? 12 : 12)
case "mask":
    guard args.count >= 4 else { fail("mask needs <video> <out.mov>") }
    mask(path: args[2], out: args[3], quality: args.count > 4 ? args[4] : "balanced",
         start: args.count > 5 ? Double(args[5]) ?? 0 : 0, length: args.count > 6 ? Double(args[6]) ?? 0 : 0)
default:
    fail("unknown command \(args[1])")
}
