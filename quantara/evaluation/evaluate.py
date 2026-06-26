"""
Harness de evaluación offline del reconocimiento de albaranes.

Alimenta las fixtures de texto (`tests/fixtures/text/*.json`, derivadas del
volcado OCR real) al parser de `DonutExtractor` SIN cargar PaddleOCR, y compara
el resultado contra `tests/ground_truth.json`. Imprime precisión por campo, por
documento y global, además del gap de líneas de producto.

Uso:  python -m quantara.evaluation.evaluate
"""
import json
import os

from quantara.ocr.donut_model import DonutExtractor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXT = os.path.join(ROOT, "tests", "fixtures", "text")
GT = os.path.join(ROOT, "tests", "ground_truth.json")

CAMPOS_CAB = ["numero_albaran", "fecha", "base_imponible", "iva_total", "total"]
NUM = {"base_imponible", "iva_total", "total"}


def _norm(v):
    if v is None:
        return None
    return str(v).strip()


def _igual(campo, esperado, obtenido):
    if esperado is None:
        return None  # no se evalúa (delivery note / no verificado)
    if campo in NUM:
        try:
            return abs(float(esperado) - float(obtenido)) < 0.02
        except (TypeError, ValueError):
            return False
    return _norm(esperado) == _norm(obtenido)


def evaluar():
    gt = json.load(open(GT, encoding="utf-8"))
    parser = DonutExtractor.__new__(DonutExtractor)  # sin __init__: no carga modelo

    aciertos = {c: 0 for c in CAMPOS_CAB}
    evaluables = {c: 0 for c in CAMPOS_CAB}
    prod_ok = prod_docs = 0
    filas = []

    for stem, esperado in gt.items():
        if stem.startswith("_"):
            continue
        fx = os.path.join(FIXT, f"{stem}.json")
        if not os.path.exists(fx):
            print(f"  [SKIP] sin fixture: {stem}")
            continue
        texts = [l["text"] for l in json.load(open(fx, encoding="utf-8"))["lines"]]
        r = parser.parse_from_texts(texts)

        marcas = []
        for c in CAMPOS_CAB:
            ok = _igual(c, esperado.get(c), r.get(c))
            if ok is None:
                marcas.append("·")
                continue
            evaluables[c] += 1
            if ok:
                aciertos[c] += 1
                marcas.append("✓")
            else:
                marcas.append("✗")

        # Productos: extraídos vs esperados (solo si hay conteo verificado)
        n_ext = len(r.get("productos") or [])
        n_esp = esperado.get("productos_esperados")
        if n_esp is not None:
            prod_docs += 1
            if n_ext == n_esp:
                prod_ok += 1
            pcell = f"{n_ext}/{n_esp}"
        else:
            pcell = f"{n_ext}/?"

        filas.append((stem, marcas, pcell))

    # ── Informe ──────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print(f"{'DOCUMENTO':32s} " + " ".join(f"{c[:4]:>4s}" for c in CAMPOS_CAB) + "  prod")
    print("-" * 78)
    for stem, marcas, pcell in filas:
        print(f"{stem:32s} " + " ".join(f"{m:>4s}" for m in marcas) + f"  {pcell:>6s}")
    print("-" * 78)
    print("PRECISIÓN POR CAMPO (cabecera):")
    total_ok = total_ev = 0
    for c in CAMPOS_CAB:
        ev = evaluables[c]
        ok = aciertos[c]
        total_ok += ok
        total_ev += ev
        pct = (100 * ok / ev) if ev else 0
        print(f"  {c:18s} {ok:2d}/{ev:2d}  ({pct:5.1f}%)")
    cab_pct = (100 * total_ok / total_ev) if total_ev else 0
    print(f"\n  CABECERA GLOBAL     {total_ok:2d}/{total_ev:2d}  ({cab_pct:5.1f}%)")
    prod_pct = (100 * prod_ok / prod_docs) if prod_docs else 0
    print(f"  PRODUCTOS (conteo)  {prod_ok:2d}/{prod_docs:2d}  ({prod_pct:5.1f}%)  "
          f"docs con conteo exacto de líneas")
    print("=" * 78)
    return cab_pct, prod_pct


if __name__ == "__main__":
    evaluar()
