import io
import os
from PIL import Image
from pdf2image import convert_from_path, convert_from_bytes

from quantara.config import PDF_DPI, MAX_IMAGE_SIZE

# Módulo Preprocessor
# Responsabilidad: Preprocesamiento de imágenes de albaranes (rasterizado,
# redimensionado, conversión) de forma multiplataforma y económica en cómputo.

# Poppler: se localiza vía PATH del sistema. En Windows se puede inyectar la
# carpeta bin con la variable de entorno POPPLER_PATH; en Linux/macOS basta
# con tener poppler-utils instalado (pdftoppm en el PATH).
_POPPLER_PATH = os.getenv("POPPLER_PATH") or None


def pdf_to_image(pdf_path: str, solo_primera: bool = True) -> list:
    """
    Rasteriza un PDF a imágenes PIL.
    Por defecto solo la primera página (los albaranes caben en una) para no
    malgastar cómputo convirtiendo páginas que nunca se usan.
    """
    kwargs = {"dpi": PDF_DPI}
    if _POPPLER_PATH:
        kwargs["poppler_path"] = _POPPLER_PATH
    if solo_primera:
        kwargs["first_page"] = 1
        kwargs["last_page"] = 1
    return convert_from_path(pdf_path, **kwargs)


def pdf_bytes_to_image(data: bytes, solo_primera: bool = True) -> list:
    """Igual que pdf_to_image pero desde bytes en memoria (sin fichero temporal)."""
    kwargs = {"dpi": PDF_DPI}
    if _POPPLER_PATH:
        kwargs["poppler_path"] = _POPPLER_PATH
    if solo_primera:
        kwargs["first_page"] = 1
        kwargs["last_page"] = 1
    return convert_from_bytes(data, **kwargs)


def resize_image(image: Image.Image, max_size: tuple = MAX_IMAGE_SIZE) -> Image.Image:
    """
    Redimensiona manteniendo el ratio para no exceder max_size.
    Menos píxeles que procesar = detección OCR más barata, sin perder nitidez
    de texto si el lado máximo se mantiene razonable.
    """
    img_copy = image.copy()
    img_copy.thumbnail(max_size, Image.Resampling.LANCZOS)
    return img_copy


def load_image(path_or_bytes) -> Image.Image:
    """
    Carga una imagen a un objeto PIL desde ruta en disco o desde bytes crudos.
    La convierte a RGB asegurando compatibilidad con el procesador.
    """
    if isinstance(path_or_bytes, (bytes, bytearray)):
        img = Image.open(io.BytesIO(path_or_bytes))
    else:
        img = Image.open(path_or_bytes)
    return img.convert("RGB")
