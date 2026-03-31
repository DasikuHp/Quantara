import sys, os
sys.path.insert(0, 'E:/Quantara')
os.environ['PATH'] += r';C:\poppler-25.12.0\bin'

from quantara.ocr.preprocessor import pdf_to_image
from quantara.ocr.donut_model import DonutExtractor

# Pon aquí la ruta a tu carpeta de albaranes
ALBARANES_DIR = 'E:/Quantara/data/albaranes'

extractor = DonutExtractor()

pdfs = [f for f in os.listdir(ALBARANES_DIR) if f.endswith('.pdf')]

for pdf in sorted(pdfs):
    path = os.path.join(ALBARANES_DIR, pdf)
    print("\n" + "="*60)
    print(f"ARCHIVO: {pdf}")
    print("="*60)
    try:
        images = pdf_to_image(path)
        if not images:
            print("ERROR: No se pudo convertir a imagen")
            continue
        image = images[0]
        # Acceder directamente al OCR interno
        import numpy as np
        img_array = np.array(image.convert("RGB"))
        result = extractor.ocr.ocr(img_array, cls=True)
        if result and result[0]:
            for i, line in enumerate(result[0]):
                text = line[1][0]
                conf = line[1][1]
                print(f"  [{i:02d}] ({conf:.2f}) {text}")
        else:
            print("  Sin resultado OCR")
    except Exception as e:
        print(f"  ERROR: {e}")

print("\n" + "="*60)
print("FIN DEL DIAGNÓSTICO")
print("="*60)
