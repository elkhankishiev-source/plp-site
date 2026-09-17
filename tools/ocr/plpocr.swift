// Распознавание текста на картинке средствами самой macOS (Vision).
//
// Эльнур 17.09.2026: «ты уже как-то читал и доставал все детали из контрактов —
// надо это сделать уже серьёзнее и создать сильный инструмент под это».
//
// Повод: 17 подписанных договоров клиентов лежат сканами — в PDF ноль текста,
// по картинке на страницу. Разбор читал их как «страницы полностью белые»,
// и данные покупки в карточки не попадали.
//
// Ставить ничего не нужно: Vision входит в систему, распознаёт русский и
// английский, держит таблицы и мелкий шрифт договоров.
//
// Сборка:  swiftc -O -o tools/ocr/plpocr tools/ocr/plpocr.swift
// Запуск:  tools/ocr/plpocr страница1.png страница2.png …

import Foundation
import Vision
import AppKit

func recognize(_ path: String) -> String {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        FileHandle.standardError.write("не открылось: \(path)\n".data(using: .utf8)!)
        return ""
    }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = true
    // договоры у нас двуязычные: тайская сторона печатает по-английски,
    // клиентские — по-русски
    req.recognitionLanguages = ["ru-RU", "en-US"]
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do { try handler.perform([req]) } catch {
        FileHandle.standardError.write("не распозналось: \(path)\n".data(using: .utf8)!)
        return ""
    }
    guard let obs = req.results else { return "" }
    // строки идём сверху вниз, слева направо — иначе таблица платежей
    // рассыпается и график читается не в том порядке
    let lines = obs.compactMap { o -> (CGFloat, CGFloat, String)? in
        guard let t = o.topCandidates(1).first?.string else { return nil }
        return (o.boundingBox.origin.y, o.boundingBox.origin.x, t)
    }.sorted { a, b in
        if abs(a.0 - b.0) > 0.008 { return a.0 > b.0 }
        return a.1 < b.1
    }
    var out: [String] = []
    var lastY: CGFloat = -1
    for (y, _, text) in lines {
        if lastY >= 0 && abs(lastY - y) <= 0.008 {
            out[out.count - 1] += "  " + text          // та же строка таблицы
        } else {
            out.append(text)
        }
        lastY = y
    }
    return out.joined(separator: "\n")
}

let files = Array(CommandLine.arguments.dropFirst())
if files.isEmpty {
    print("укажите файлы картинок")
    exit(2)
}
for f in files {
    print("<<<СТРАНИЦА \(f)>>>")
    print(recognize(f))
}
