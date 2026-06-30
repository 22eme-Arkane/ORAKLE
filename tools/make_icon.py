"""Génère resources/logo.png (détouré, coins transparents) + resources/logo.ico.

Usage :
    python tools/make_icon.py <image_source> [resources_dir]

- Recadre sur le médaillon (boîte englobante des pixels non blancs).
- Applique un masque circulaire (coins transparents) avec un léger lissage.
- Écrit logo.png (512x512) et logo.ico multi-tailles (16..256), sans Pillow
  (PyQt6 + numpy uniquement). L'ICO embarque des PNG (format supporté Vista+).
"""
from __future__ import annotations

import os
import struct
import sys

import numpy as np
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PyQt6.QtGui import QGuiApplication, QImage

_ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _qimage_to_rgba(img: QImage) -> np.ndarray:
    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
    h, w, bpl = img.height(), img.width(), img.bytesPerLine()
    ptr = img.bits()
    ptr.setsize(img.sizeInBytes())
    buf = np.frombuffer(ptr, np.uint8, count=h * bpl).reshape(h, bpl)
    return buf[:, : w * 4].reshape(h, w, 4).copy()


def _rgba_to_qimage(arr: np.ndarray) -> QImage:
    h, w = arr.shape[:2]
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    qimg = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    return qimg.copy()  # détache de la mémoire numpy


def _png_bytes(img: QImage, size: int) -> bytes:
    scaled = img.scaled(
        size, size,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    scaled.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def _write_ico(img: QImage, path: str, sizes=_ICO_SIZES) -> None:
    entries = [(s, _png_bytes(img, s)) for s in sizes]
    offset = 6 + 16 * len(entries)
    header = struct.pack("<HHH", 0, 1, len(entries))
    dir_entries = b""
    data = b""
    for s, png in entries:
        b = 0 if s >= 256 else s
        dir_entries += struct.pack(
            "<BBBBHHII", b, b, 0, 0, 1, 32, len(png), offset
        )
        data += png
        offset += len(png)
    with open(path, "wb") as f:
        f.write(header + dir_entries + data)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: make_icon.py <source> [resources_dir]")
        return 2
    src = sys.argv[1]
    res_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources"
    )
    os.makedirs(res_dir, exist_ok=True)

    _app = QGuiApplication(sys.argv[:1])  # requis pour les ops d'image
    src_img = QImage(src)
    if src_img.isNull():
        print(f"image illisible : {src}")
        return 1

    arr = _qimage_to_rgba(src_img)
    h, w = arr.shape[:2]

    # Boîte englobante des pixels non blancs (le médaillon).
    nonwhite = (arr[:, :, :3] < 240).any(axis=2)
    ys, xs = np.where(nonwhite)
    if len(xs) == 0:
        print("image entièrement blanche ?")
        return 1
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    side = max(x1 - x0 + 1, y1 - y0 + 1)
    half = side // 2
    sx0, sy0 = max(0, cx - half), max(0, cy - half)
    side = min(side, w - sx0, h - sy0)

    crop = src_img.copy(sx0, sy0, side, side).scaled(
        512, 512,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    rgba = _qimage_to_rgba(crop).astype(np.float32)
    H = W = 512

    # Masque circulaire (coins transparents) avec lissage 1 px.
    yy, xx = np.ogrid[:H, :W]
    center = W / 2.0
    dist = np.sqrt((xx - center + 0.5) ** 2 + (yy - center + 0.5) ** 2)
    radius = W / 2.0 - 1.0
    edge = np.clip(radius - dist + 1.0, 0.0, 1.0)
    rgba[:, :, 3] = rgba[:, :, 3] * edge
    out = _rgba_to_qimage(rgba.astype(np.uint8))

    png_path = os.path.join(res_dir, "logo.png")
    ico_path = os.path.join(res_dir, "logo.ico")
    out.save(png_path, "PNG")
    _write_ico(out, ico_path)
    print(f"écrit : {png_path}")
    print(f"écrit : {ico_path} ({', '.join(str(s) for s in _ICO_SIZES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
