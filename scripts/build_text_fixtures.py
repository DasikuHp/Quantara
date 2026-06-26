"""
Genera fixtures de texto OCR a partir del volcado `ocr_raw_output.txt`.

El volcado (UTF-16) contiene, por documento, las líneas que devolvió PaddleOCR
con el formato:  `    [NN] (conf) texto`.
Este script las extrae y las guarda como JSON por documento en
`tests/fixtures/text/<doc>.json`, para poder evaluar el parser sin Paddle.

Uso:  python scripts/build_text_fixtures.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMP = os.path.join(ROOT, "ocr_raw_output.txt")
OUT_DIR = os.path.join(ROOT, "tests", "fixtures", "text")

LINE_RE = re.compile(r'\[(\d{2,3})\]\s*\(([\d.]+)\)\s*(.*\S)')


def read_dump():
    with open(DUMP, "r", encoding="utf-16") as f:
        return f.read()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    raw = read_dump()
    # Separar por documento.
    bloques = re.split(r'ARCHIVO:\s*(\S+\.pdf)', raw)
    # bloques = ['', nombre1, contenido1, nombre2, contenido2, ...]
    docs = list(zip(bloques[1::2], bloques[2::2]))
    total = 0
    for nombre, contenido in docs:
        lines = []
        for m in LINE_RE.finditer(contenido):
            conf = float(m.group(2))
            text = m.group(3).strip()
            lines.append({"text": text, "conf": conf})
        stem = os.path.splitext(nombre)[0]
        out = os.path.join(OUT_DIR, f"{stem}.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"doc": nombre, "lines": lines}, f,
                      ensure_ascii=False, indent=1)
        total += 1
        print(f"  {stem:32s} {len(lines):3d} líneas")
    print(f"\n{total} fixtures escritas en {OUT_DIR}")


if __name__ == "__main__":
    main()
