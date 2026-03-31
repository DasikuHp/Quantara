import sys
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR
from quantara.ocr.preprocessor import pdf_to_image

def debug_ocr(pdf_path):
    print(f"Procesando: {pdf_path}")
    images = pdf_to_image(pdf_path)
    print(f"Páginas encontradas: {len(images)}")
    
    ocr = PaddleOCR(use_textline_orientation=True, lang="es")
    image = images[0]
    numpy_img = np.array(image.convert("RGB"))
    result = ocr.ocr(numpy_img, cls=True)
    
    print("\n--- TEXTO EXTRAÍDO ---")
    if result and result[0]:
        for line in result[0]:
            texto = line[1][0]
            confianza = line[1][1]
            print(f"[{confianza:.2f}] {texto}")

if __name__ == "__main__":
    debug_ocr(sys.argv[1])
