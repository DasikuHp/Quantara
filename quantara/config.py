# Configuración de Quantara
# Responsabilidad: Gestión centralizada de variables de entorno y configuración

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "quantara.db")
UPLOAD_DIR = "data/albaranes"
MODEL_NAME = "naver-clova-ix/donut-base"
MAX_IMAGE_SIZE = (1280, 960)
