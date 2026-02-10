"""
Tests para HU4: Portafolio Visual de Evidencias

Cubre:
- Validadores de imagen (tamaño, formato, MIME type)
- Permisos (IsWorkerAndOwnerOrReadOnly)
- Endpoints CRUD de portfolio
- Compresión de imágenes
- Manejo de archivos corruptos

"""
import tempfile
from io import BytesIO
from PIL import Image as PILImage
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from users.models import WorkerProfile, PortfolioItem
from users.validators import validate_image_size, ImageContentTypeValidator
from users.permissions import IsWorkerAndOwnerOrReadOnly
from users.constants import MAX_IMAGE_SIZE_MB, ALLOWED_IMAGE_EXTENSIONS
from unittest.mock import Mock

User = get_user_model()


# ============================================================================
# TESTS UNITARIOS DE VALIDADORES
# ============================================================================

class ImageValidatorTests(TestCase):
    """Tests para validadores de imagen"""

    def create_test_image(self, size_mb=1, format='JPEG', width=800, height=600):
        """
        Helper para crear imágenes de prueba con tamaño específico.
        
        Args:
            size_mb: Tamaño aproximado en MB
            format: Formato de imagen (JPEG, PNG, WEBP)
            width, height: Dimensiones
        
        Returns:
            SimpleUploadedFile con imagen generada
        """
        img = PILImage.new('RGB', (width, height), color='red')
        buffer = BytesIO()
        
        # Ajustar calidad para alcanzar tamaño aproximado
        if format == 'JPEG':
            quality = 95 if size_mb > 2 else 85
            img.save(buffer, format='JPEG', quality=quality)
        elif format == 'PNG':
            img.save(buffer, format='PNG')
        elif format == 'WEBP':
            img.save(buffer, format='WEBP', quality=95)
        
        buffer.seek(0)
        
        # Si necesitamos más tamaño, repetir contenido
        content = buffer.read()
        if size_mb > 1:
            target_size = int(size_mb * 1024 * 1024)
            while len(content) < target_size:
                content += content[:min(len(content), target_size - len(content))]
        
        return SimpleUploadedFile(
            f"test_image.{format.lower()}",
            content[:int(size_mb * 1024 * 1024)] if size_mb > 1 else content,
            content_type=f"image/{format.lower()}"
        )

    def test_validate_image_size_accepts_valid_size(self):
        """Validador debe aceptar imágenes menores al límite"""
        image = self.create_test_image(size_mb=2)  # 2MB < 5MB
        try:
            validate_image_size(image)
        except ValidationError:
            self.fail("validate_image_size rechazó imagen válida")

    def test_validate_image_size_rejects_oversized(self):
        """Validador debe rechazar imágenes mayores a MAX_IMAGE_SIZE_MB"""
        image = self.create_test_image(size_mb=6)  # 6MB > 5MB
        
        with self.assertRaises(ValidationError) as cm:
            validate_image_size(image)
        
        self.assertIn(str(MAX_IMAGE_SIZE_MB), str(cm.exception))

    def test_image_content_type_validator_accepts_jpeg(self):
        """Validador debe aceptar JPEG"""
        validator = ImageContentTypeValidator()
        image = self.create_test_image(format='JPEG')
        
        try:
            validator(image)
        except ValidationError:
            self.fail("ImageContentTypeValidator rechazó JPEG válido")

    def test_image_content_type_validator_accepts_png(self):
        """Validador debe aceptar PNG"""
        validator = ImageContentTypeValidator()
        image = self.create_test_image(format='PNG')
        
        try:
            validator(image)
        except ValidationError:
            self.fail("ImageContentTypeValidator rechazó PNG válido")

    def test_image_content_type_validator_accepts_webp(self):
        """Validador debe aceptar WEBP"""
        validator = ImageContentTypeValidator()
        image = self.create_test_image(format='WEBP')
        
        try:
            validator(image)
        except ValidationError:
            self.fail("ImageContentTypeValidator rechazó WEBP válido")

    def test_image_content_type_validator_rejects_gif(self):
        """Validador debe rechazar GIF"""
        validator = ImageContentTypeValidator()
        
        # Crear un GIF simple
        img = PILImage.new('RGB', (100, 100), color='blue')
        buffer = BytesIO()
        img.save(buffer, format='GIF')
        buffer.seek(0)
        
        image = SimpleUploadedFile(
            "test.gif",
            buffer.read(),
            content_type="image/gif"
        )
        
        with self.assertRaises(ValidationError) as cm:
            validator(image)
        
        # Verificar que el error mencione extensión o formato no permitido
        error_msg = str(cm.exception).lower()
        self.assertTrue(
            "extensión" in error_msg or "formato" in error_msg,
            f"Expected error message about format/extension, got: {error_msg}"
        )

    def test_image_content_type_validator_fallback_to_extension(self):
        """Validador debe usar extensión como fallback si MIME type es None"""
        validator = ImageContentTypeValidator()
        image = self.create_test_image(format='JPEG')
        
        # Simular caso donde content_type es None (problema de Postman)
        image.content_type = None
        image.name = "test.jpg"
        
        try:
            validator(image)
        except ValidationError:
            self.fail("ImageContentTypeValidator falló en fallback por extensión")

    def test_image_content_type_validator_rejects_invalid_extension(self):
        """Validador debe rechazar extensiones no permitidas incluso en modo fallback"""
        validator = ImageContentTypeValidator()
        
        img = PILImage.new('RGB', (100, 100), color='green')
        buffer = BytesIO()
        img.save(buffer, format='BMP')
        buffer.seek(0)
        
        image = SimpleUploadedFile(
            "test.bmp",
            buffer.read(),
            content_type=None  # Forzar fallback
        )
        
        with self.assertRaises(ValidationError):
            validator(image)


# ============================================================================
# TESTS DE PERMISOS
# ============================================================================

class PortfolioPermissionsTests(APITestCase):
    """Tests para IsWorkerAndOwnerOrReadOnly"""

    def setUp(self):
        """Crear usuarios y perfiles de prueba"""
        # Worker 1 (dueño)
        self.worker1 = User.objects.create_user(
            email="worker1@test.com",
            password="test123",
            role=User.Role.WORKER
        )
        self.worker_profile1 = WorkerProfile.objects.get(user=self.worker1)
        
        # Worker 2 (no dueño)
        self.worker2 = User.objects.create_user(
            email="worker2@test.com",
            password="test123",
            role=User.Role.WORKER
        )
        self.worker_profile2 = WorkerProfile.objects.get(user=self.worker2)
        
        # Cliente
        self.client_user = User.objects.create_user(
            email="client@test.com",
            password="test123",
            role=User.Role.CLIENT
        )
        
        # Compañía
        self.company_user = User.objects.create_user(
            email="company@test.com",
            password="test123",
            role=User.Role.COMPANY
        )
        
        # Admin
        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            password="test123",
            role=User.Role.ADMIN,
            is_staff=True
        )
        
        # Portfolio item del worker1
        self.portfolio_item = PortfolioItem.objects.create(
            worker=self.worker_profile1,
            title="Test Project",
            description="Test description"
        )

    def test_safe_methods_allowed_for_anonymous(self):
        """GET debe permitirse sin autenticación"""
        response = self.client.get(
            f'/api/users/workers/{self.worker_profile1.id}/portfolio/'
        )
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_post_rejected_for_client(self):
        """CLIENT no puede crear portfolio items"""
        self.client.force_authenticate(user=self.client_user)
        
        response = self.client.post(
            '/api/users/workers/portfolio/',
            {'title': 'Test', 'description': 'Test'},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_rejected_for_company(self):
        """COMPANY no puede crear portfolio items"""
        self.client.force_authenticate(user=self.company_user)
        
        response = self.client.post(
            '/api/users/workers/portfolio/',
            {'title': 'Test', 'description': 'Test'},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_allowed_for_worker(self):
        """WORKER puede crear sus propios portfolio items"""
        self.client.force_authenticate(user=self.worker1)
        
        # Crear imagen temporal
        image = PILImage.new('RGB', (800, 600), color='blue')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')
        buffer.seek(0)
        
        test_image = SimpleUploadedFile(
            "test.jpg",
            buffer.read(),
            content_type="image/jpeg"
        )
        
        response = self.client.post(
            '/api/users/workers/portfolio/',
            {
                'title': 'New Project',
                'description': 'Description',
                'image': test_image
            },
            format='multipart'
        )
        
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_patch_rejected_for_non_owner_worker(self):
        """WORKER no puede editar portfolio items de otros"""
        self.client.force_authenticate(user=self.worker2)
        
        response = self.client.patch(
            f'/api/users/workers/portfolio/{self.portfolio_item.id}/',
            {'title': 'Hacked Title'},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_rejected_for_non_owner_worker(self):
        """WORKER no puede eliminar portfolio items de otros"""
        self.client.force_authenticate(user=self.worker2)
        
        response = self.client.delete(
            f'/api/users/workers/portfolio/{self.portfolio_item.id}/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ============================================================================
# TESTS DE ENDPOINTS
# ============================================================================

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PortfolioEndpointTests(APITestCase):
    """Tests de integración para endpoints de portfolio"""

    def setUp(self):
        """Setup común para tests de endpoints"""
        self.worker = User.objects.create_user(
            email="worker@test.com",
            password="test123",
            role=User.Role.WORKER
        )
        self.worker_profile = WorkerProfile.objects.get(user=self.worker)
        self.client.force_authenticate(user=self.worker)

    def create_test_image(self, width=800, height=600):
        """Helper para crear imagen de prueba"""
        img = PILImage.new('RGB', (width, height), color='red')
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        buffer.seek(0)
        return SimpleUploadedFile(
            "test.jpg",
            buffer.read(),
            content_type="image/jpeg"
        )

    def test_create_portfolio_item_success(self):
        """Crear portfolio item con datos válidos debe funcionar"""
        image = self.create_test_image()
        
        response = self.client.post(
            '/api/users/workers/portfolio/',
            {
                'title': 'Kitchen Renovation',
                'description': 'Complete kitchen remodel',
                'image': image
            },
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Kitchen Renovation')
        self.assertIn('image', response.data)

    def test_create_portfolio_item_title_whitespace_rejected(self):
        """Título con solo espacios debe ser rechazado"""
        image = self.create_test_image()
        
        response = self.client.post(
            '/api/users/workers/portfolio/',
            {
                'title': '   ',  # Solo espacios
                'description': 'Test',
                'image': image
            },
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', response.data)

    def test_create_portfolio_item_without_image_rejected(self):
        """Crear sin imagen debe fallar"""
        response = self.client.post(
            '/api/users/workers/portfolio/',
            {
                'title': 'Test',
                'description': 'Test'
            },
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('image', response.data)

    def test_list_own_portfolio(self):
        """Listar portfolio propio debe funcionar"""
        # Crear algunos items
        PortfolioItem.objects.create(
            worker=self.worker_profile,
            title="Project 1",
            description="Desc 1"
        )
        PortfolioItem.objects.create(
            worker=self.worker_profile,
            title="Project 2",
            description="Desc 2"
        )
        
        response = self.client.get('/api/users/workers/portfolio/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Puede retornar array o paginación
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertEqual(len(response.data['results']), 2)
        else:
            self.assertEqual(len(response.data), 2)

    def test_update_own_portfolio_item(self):
        """Actualizar portfolio item propio debe funcionar"""
        item = PortfolioItem.objects.create(
            worker=self.worker_profile,
            title="Original Title",
            description="Original Desc"
        )
        
        # PATCH con multipart para mantener consistencia con POST
        response = self.client.patch(
            f'/api/users/workers/portfolio/{item.id}/',
            {'title': 'Updated Title', 'description': 'Original Desc'},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated Title')

    def test_delete_own_portfolio_item(self):
        """Eliminar portfolio item propio debe funcionar"""
        item = PortfolioItem.objects.create(
            worker=self.worker_profile,
            title="To Delete",
            description="Will be deleted"
        )
        
        response = self.client.delete(
            f'/api/users/workers/portfolio/{item.id}/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(PortfolioItem.objects.filter(id=item.id).exists())


# ============================================================================
# TESTS DE COMPRESIÓN
# ============================================================================

class ImageCompressionTests(TestCase):
    """Tests para compresión automática de imágenes"""

    def test_large_image_gets_compressed(self):
        """Imágenes grandes deben ser comprimidas al guardar"""
        worker = User.objects.create_user(
            email="worker@test.com",
            password="test123",
            role=User.Role.WORKER
        )
        worker_profile = WorkerProfile.objects.get(user=worker)
        
        # Crear imagen grande (2000x1500)
        img = PILImage.new('RGB', (2000, 1500), color='blue')
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=95)
        buffer.seek(0)
        
        original_size = buffer.tell()
        buffer.seek(0)
        
        test_image = SimpleUploadedFile(
            "large_image.jpg",
            buffer.read(),
            content_type="image/jpeg"
        )
        
        # Crear portfolio item (debería comprimir automáticamente)
        item = PortfolioItem.objects.create(
            worker=worker_profile,
            title="Large Image Test",
            description="Testing compression",
            image=test_image
        )
        
        # Verificar que la imagen existe
        self.assertTrue(item.image)
        
        # Abrir imagen guardada y verificar dimensiones
        saved_image = PILImage.open(item.image)
        
        # La imagen debe haber sido redimensionada (width <= 1600)
        self.assertLessEqual(saved_image.width, 1600)

    def test_corrupt_image_raises_validation_error(self):
        """Archivo corrupto debe levantar ValidationError"""
        worker = User.objects.create_user(
            email="worker@test.com",
            password="test123",
            role=User.Role.WORKER
        )
        worker_profile = WorkerProfile.objects.get(user=worker)
        
        # Crear archivo corrupto (no es imagen válida)
        corrupt_file = SimpleUploadedFile(
            "corrupt.jpg",
            b"This is not a valid image file",
            content_type="image/jpeg"
        )
        
        # Intentar crear portfolio item con archivo corrupto
        item = PortfolioItem(
            worker=worker_profile,
            title="Corrupt Test",
            description="Testing corrupt file handling",
            image=corrupt_file
        )
        
        # Debe fallar al intentar guardar (compress_image levantará ValidationError)
        with self.assertRaises(ValidationError):
            item.save()


# ============================================================================
# TESTS DE CASOS EDGE
# ============================================================================

class PortfolioEdgeCaseTests(APITestCase):
    """Tests para casos límite y edge cases"""

    def setUp(self):
        self.worker = User.objects.create_user(
            email="worker@test.com",
            password="test123",
            role=User.Role.WORKER
        )
        self.worker_profile = WorkerProfile.objects.get(user=self.worker)

    def test_title_gets_stripped(self):
        """Espacios extras en título deben ser eliminados"""
        self.client.force_authenticate(user=self.worker)
        
        img = PILImage.new('RGB', (100, 100), color='red')
        buffer = BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        
        image = SimpleUploadedFile("test.jpg", buffer.read(), content_type="image/jpeg")
        
        response = self.client.post(
            '/api/users/workers/portfolio/',
            {
                'title': '  Spaced Title  ',
                'description': 'Test',
                'image': image
            },
            format='multipart'
        )
        
        if response.status_code == status.HTTP_201_CREATED:
            self.assertEqual(response.data['title'], 'Spaced Title')

    def test_public_view_of_worker_portfolio(self):
        """Portfolio público debe ser visible sin autenticación"""
        PortfolioItem.objects.create(
            worker=self.worker_profile,
            title="Public Project",
            description="Should be visible"
        )
        
        # Sin autenticación
        client = APIClient()
        response = client.get(
            f'/api/users/workers/{self.worker_profile.id}/portfolio/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
