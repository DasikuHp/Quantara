import io
import os
os.environ["PATH"] += r";C:\poppler-25.12.0\bin"
from PIL import Image
from pdf2image import convert_from_path

# Módulo Preprocessor
# Responsabilidad: Preprocesamiento de imágenes de albaranes (redimensionar, conversión, etc.)

def pdf_to_image(pdf_path: str) -> list:
    return convert_from_path(
        pdf_path,
        poppler_path=r"C:\poppler-25.12.0\Library\bin"
    )

def resize_image(image: Image.Image, max_size: tuple) -> Image.Image:
    """
    Redimensiona una imagen PIL manteniendo el ratio de aspecto, 
    asegurando un tamaño apropiado para la inferencia sin exceder max_size.
    """
    img_copy = image.copy()
    img_copy.thumbnail(max_size, Image.Resampling.LANCZOS)
    return img_copy

def load_image(path_or_bytes) -> Image.Image:
    """
    Carga una imagen a un objeto PIL desde una ruta en disco o desde bytes en crudo.
    La convierte a RGB asegurando compatibilidad con el procesador.
    """
    if isinstance(path_or_bytes, bytes):
        img = Image.open(io.BytesIO(path_or_bytes))
    else:
        img = Image.open(path_or_bytes)
    
    return img.convert("RGB")
