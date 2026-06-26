"""
Test de regresión del reconocimiento sobre fixtures reales (sin PaddleOCR).
Ancla los resultados medidos por el harness:
  - cabeceras 100%
  - productos: >= 5/8 docs con conteo exacto de líneas
Ejecutar:  python -m tests.test_recognition   (o pytest)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantara.evaluation.evaluate import evaluar


def test_reconocimiento():
    cab_pct, prod_pct = evaluar()
    assert cab_pct == 100.0, f"Regresión en cabeceras: {cab_pct:.1f}%"
    assert prod_pct >= 62.5, f"Regresión en productos: {prod_pct:.1f}%"


if __name__ == "__main__":
    test_reconocimiento()
    print("\nOK test_reconocimiento")
