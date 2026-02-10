"""
Validadores de imágenes para portfolio.

Provee validadores reutilizables siguiendo el principio de
Responsabilidad Única (SRP). Cada validador tiene un propósito claro.
"""

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _
from django.utils.deconstruct import deconstructible

from .constants import (
    MAX_IMAGE_SIZE_BYTES,
    MAX_IMAGE_SIZE_MB,
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_IMAGE_MIME_TYPES,
)


def validate_image_size(image):
    """Valida que el tamaño de la imagen no exceda el límite permitido."""
    if image.size > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError(
            _(f"La imagen supera el límite de {MAX_IMAGE_SIZE_MB} MB.")
        )


@deconstructible
class ImageContentTypeValidator:
    """
    Valida el tipo MIME de imágenes.
    
    @deconstructible permite usar esta clase en migraciones
    sin problemas de serialización.
    """
    
    allowed_mime_types = ALLOWED_IMAGE_MIME_TYPES
    
    def __call__(self, image):
        """Valida que el tipo MIME sea permitido."""
        content_type = getattr(image.file, "content_type", None)
        
        # Si el MIME type es None (común en Postman), validar por extensión
        if content_type is None:
            import os
            ext = os.path.splitext(image.name)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                return  # Extensión válida, permitir
            else:
                raise ValidationError(
                    _(f"Extensión de archivo no permitida: {ext}. Use: .jpg, .png o .webp")
                )
        
        # Validación normal por MIME type
        if content_type not in self.allowed_mime_types:
            raise ValidationError(
                _(f"Tipo de archivo no permitido. Use: JPG, PNG o WEBP.")
            )


# ============================================================================
# LISTA DE VALIDADORES REUTILIZABLES
# ============================================================================

portfolio_image_validators = [
    validate_image_size,
    FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS),
    ImageContentTypeValidator(),
]
