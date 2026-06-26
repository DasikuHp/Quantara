"""
Captura fixtures OCR CON COORDENADAS (Fase B). Requiere PaddleOCR instalado.
El usuario lo ejecuta UNA vez en su máquina; el resultado permite desarrollar y
medir offline la extracción de productos por geometría para los proveedores con
tablas interleaved (Coca-Cola, Makro, DDI), que el orden de línea no recupera.

Guarda `tests/fixtures/boxes/<doc>.json` = [{text, conf, box:[[x,y]*4]}].

Uso:  python scripts/capture_fixtures.py [carpeta_pdfs]
      (por defecto: quantara/data/albaranes)
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "tests", "fixtures", "boxes")


def main(pdf_dir):
    import numpy as np
    from quantara.ocr.preprocessor import pdf_to_image, resize_image
    from quantara.ocr.donut_model import get_ocr

    os.makedirs(OUT_DIR, exist_ok=True)
    ocr = get_ocr()
    pdfs = sorted(f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf"))
    for pdf in pdfs:
        path = os.path.join(pdf_dir, pdf)
        images = pdf_to_image(path)
        if not images:
            print(f"  [SKIP] {pdf}: sin imagen")
            continue
        img = resize_image(images[0])
        result = ocr.ocr(np.array(img), cls=False)
        lines = []
        if result and result[0]:
            for box, (text, conf) in ((ln[0], ln[1]) for ln in result[0]):
                lines.append({
                    "text": text, "conf": float(conf),
                    "box": [[float(x), float(y)] for x, y in box],
                })
        stem = os.path.splitext(pdf)[0]
        with open(os.path.join(OUT_DIR, f"{stem}.json"), "w", encoding="utf-8") as f:
            json.dump({"doc": pdf, "lines": lines}, f, ensure_ascii=False, indent=1)
        print(f"  {stem:32s} {len(lines):3d} cajas")
    print(f"\nFixtures con coordenadas en {OUT_DIR}")


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "quantara", "data", "albaranes")
    main(d)
