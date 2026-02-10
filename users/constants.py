"""
Constantes del módulo Portfolio.

Centraliza valores de configuración para evitar números mágicos.
Sigue principios de Clean Code.
"""

# ============================================================================
# CONFIGURACIÓN DE CARGA DE IMÁGENES
# ============================================================================

MAX_IMAGE_SIZE_MB = 5  # Aumentado para soportar cámaras modernas
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]

ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

# ============================================================================
# CONFIGURACIÓN DE PROCESAMIENTO DE IMÁGENES
# ============================================================================

MAX_IMAGE_WIDTH = 1600  # Ancho máximo, mantiene aspect ratio

IMAGE_QUALITY_JPEG = 80
IMAGE_QUALITY_WEBP = 80
IMAGE_QUALITY_PNG_OPTIMIZE = True

DEFAULT_IMAGE_FORMAT = "JPEG"
DEFAULT_IMAGE_EXTENSION = "jpg"
