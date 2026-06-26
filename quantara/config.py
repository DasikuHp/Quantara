# Configuración de Quantara
# Responsabilidad: Gestión centralizada de variables de entorno y configuración

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "quantara.db")
UPLOAD_DIR = "data/albaranes"

# ── Motor OCR (PaddleOCR) ─────────────────────────────────────────
# Nota: el motor real es PaddleOCR, no Donut. Estos valores controlan
# el coste de cómputo y la calidad de reconocimiento.
OCR_LANG = os.getenv("QUANTARA_OCR_LANG", "es")
# Clasificación de orientación de línea: solo útil en escaneos rotados.
# En PDFs digitales es coste innecesario, por eso por defecto está OFF.
OCR_USE_ANGLE_CLS = os.getenv("QUANTARA_OCR_ANGLE_CLS", "0") == "1"
# Aceleración CPU (oneDNN/MKL-DNN). Sin efecto si no está disponible.
OCR_ENABLE_MKLDNN = os.getenv("QUANTARA_OCR_MKLDNN", "1") == "1"
# Umbral de confianza del motor: 0.5 es el valor por defecto histórico de
# PaddleOCR (no regresa nada por debajo). El parsing añade su propio filtro.
OCR_DROP_SCORE = float(os.getenv("QUANTARA_OCR_DROP_SCORE", "0.5"))

# ── Preprocesado de imagen ────────────────────────────────────────
# Resolución de rasterizado del PDF. 150 DPI es nítido para texto y
# ~40% más barato que los 200 DPI por defecto de pdf2image.
PDF_DPI = int(os.getenv("QUANTARA_PDF_DPI", "150"))
# Lado máximo tras redimensionar antes de la red de detección.
MAX_IMAGE_SIDE = int(os.getenv("QUANTARA_MAX_IMAGE_SIDE", "1600"))
MAX_IMAGE_SIZE = (MAX_IMAGE_SIDE, MAX_IMAGE_SIDE)

# Compat: referencia histórica del modelo (no usada por el camino activo).
MODEL_NAME = "naver-clova-ix/donut-base"
