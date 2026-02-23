"""
Tests para Gestión de Perfil de Usuario y Contraseña

Cubre:
- Actualización de información de contacto
- Cambio de contraseña con validaciones
- Solicitud de reset de contraseña
- Confirmación de reset con token
- Permisos y validaciones de seguridad
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from users.models import WorkerProfile

User = get_user_model()


# ============================================================================
# TESTS DE ACTUALIZACIÓN DE PERFIL
# ============================================================================

class UserProfileUpdateTests(APITestCase):
    """Tests para actualización de información de perfil de usuario"""
    
    def setUp(self):
        """Configuración inicial para cada test"""
        self.client = APIClient()
        
        # Crear usuario cliente
        self.client_user = User.objects.create_user(
            email="client@test.com",
            password="testpass123",
            first_name="Juan",
            last_name="Pérez",
            role="CLIENT"
        )
        
        # Crear usuario trabajador
        self.worker_user = User.objects.create_user(
            email="worker@test.com",
            password="testpass123",
            first_name="Carlos",
            last_name="García",
            role="WORKER"
        )
        
        self.profile_url = '/api/users/me/'
    
    def test_get_user_profile_authenticated(self):
        """Usuario autenticado puede ver su perfil completo"""
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'client@test.com')
        self.assertEqual(response.data['first_name'], 'Juan')
        self.assertEqual(response.data['last_name'], 'Pérez')
        
        # Verificar que incluye campos de contacto
        self.assertIn('phone_number', response.data)
        self.assertIn('address', response.data)
        self.assertIn('city', response.data)
        self.assertIn('state', response.data)
        self.assertIn('country', response.data)
        self.assertIn('postal_code', response.data)
    
    def test_get_user_profile_unauthenticated(self):
        """Usuario no autenticado no puede ver perfiles"""
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_update_contact_information(self):
        """Usuario puede actualizar su información de contacto"""
        self.client.force_authenticate(user=self.client_user)
        
        data = {
            'phone_number': '+52 333 123 4567',
            'address': 'Calle Principal 123',
            'city': 'Guadalajara',
            'state': 'Jalisco',
            'country': 'México',
            'postal_code': '44100'
        }
        
        response = self.client.patch(self.profile_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['phone_number'], '+52 333 123 4567')
        self.assertEqual(response.data['city'], 'Guadalajara')
        self.assertEqual(response.data['state'], 'Jalisco')
        
        # Verificar en BD
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.phone_number, '+52 333 123 4567')
        self.assertEqual(self.client_user.city, 'Guadalajara')
    
    def test_update_name(self):
        """Usuario puede actualizar su nombre y apellido"""
        self.client.force_authenticate(user=self.client_user)
        
        data = {
            'first_name': 'Juan Carlos',
            'last_name': 'Pérez López'
        }
        
        response = self.client.patch(self.profile_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Juan Carlos')
        self.assertEqual(response.data['last_name'], 'Pérez López')
    
    def test_cannot_update_email(self):
        """Usuario NO puede cambiar su email"""
        self.client.force_authenticate(user=self.client_user)
        
        data = {'email': 'newemail@test.com'}
        response = self.client.patch(self.profile_url, data, format='json')
        
        # El email debe seguir siendo el original
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.email, 'client@test.com')
    
    def test_cannot_update_role(self):
        """Usuario NO puede cambiar su rol"""
        self.client.force_authenticate(user=self.client_user)
        
        data = {'role': 'WORKER'}
        response = self.client.patch(self.profile_url, data, format='json')
        
        # El rol debe seguir siendo CLIENT
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.role, 'CLIENT')
    
    def test_worker_can_update_profile(self):
        """Trabajadores también pueden actualizar su información"""
        self.client.force_authenticate(user=self.worker_user)
        
        data = {
            'phone_number': '+52 555 987 6543',
            'city': 'Ciudad de México',
            'state': 'CDMX'
        }
        
        response = self.client.patch(self.profile_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['phone_number'], '+52 555 987 6543')
        self.assertEqual(response.data['city'], 'Ciudad de México')
    
    def test_partial_update(self):
        """Puede actualizar solo algunos campos (PATCH)"""
        self.client.force_authenticate(user=self.client_user)
        
        # Solo actualizar ciudad
        data = {'city': 'Monterrey'}
        response = self.client.patch(self.profile_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['city'], 'Monterrey')
        
        # Los demás campos deben mantenerse
        self.assertEqual(response.data['first_name'], 'Juan')
        self.assertEqual(response.data['last_name'], 'Pérez')


# ============================================================================
# TESTS DE CAMBIO DE CONTRASEÑA
# ============================================================================

class ChangePasswordTests(APITestCase):
    """Tests para cambio de contraseña de usuario autenticado"""
    
    def setUp(self):
        """Configuración inicial para cada test"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="user@test.com",
            password="oldpass123",
            first_name="Test",
            last_name="User"
        )
        self.change_password_url = '/api/auth/change-password/'
    
    def test_change_password_success(self):
        """Usuario puede cambiar su contraseña correctamente"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            'old_password': 'oldpass123',
            'new_password': 'newpass456',
            'confirm_password': 'newpass456'
        }
        
        response = self.client.post(self.change_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Contraseña actualizada exitosamente', response.data['detail'])
        
        # Verificar que la nueva contraseña funciona
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass456'))
        self.assertFalse(self.user.check_password('oldpass123'))
    
    def test_change_password_unauthenticated(self):
        """Usuario no autenticado no puede cambiar contraseña"""
        data = {
            'old_password': 'oldpass123',
            'new_password': 'newpass456',
            'confirm_password': 'newpass456'
        }
        
        response = self.client.post(self.change_password_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_change_password_wrong_old_password(self):
        """Falla si la contraseña actual es incorrecta"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            'old_password': 'wrongpassword',
            'new_password': 'newpass456',
            'confirm_password': 'newpass456'
        }
        
        response = self.client.post(self.change_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('old_password', response.data)
        self.assertIn('incorrecta', str(response.data['old_password'][0]))
    
    def test_change_password_mismatch(self):
        """Falla si las contraseñas nuevas no coinciden"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            'old_password': 'oldpass123',
            'new_password': 'newpass456',
            'confirm_password': 'differentpass'
        }
        
        response = self.client.post(self.change_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('confirm_password', response.data)
        self.assertIn('no coinciden', str(response.data['confirm_password'][0]))
    
    def test_change_password_same_as_old(self):
        """Falla si la nueva contraseña es igual a la actual"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            'old_password': 'oldpass123',
            'new_password': 'oldpass123',
            'confirm_password': 'oldpass123'
        }
        
        response = self.client.post(self.change_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)
        self.assertIn('diferente', str(response.data['new_password'][0]))
    
    def test_change_password_too_short(self):
        """Falla si la nueva contraseña es muy corta"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            'old_password': 'oldpass123',
            'new_password': 'short',
            'confirm_password': 'short'
        }
        
        response = self.client.post(self.change_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)
    
    def test_change_password_missing_fields(self):
        """Falla si faltan campos requeridos"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            'old_password': 'oldpass123',
            'new_password': 'newpass456'
            # Falta confirm_password
        }
        
        response = self.client.post(self.change_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('confirm_password', response.data)


# ============================================================================
# TESTS DE RESET DE CONTRASEÑA
# ============================================================================

class PasswordResetTests(APITestCase):
    """Tests para reset de contraseña con token"""
    
    def setUp(self):
        """Configuración inicial para cada test"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="user@test.com",
            password="oldpass123",
            first_name="Test",
            last_name="User"
        )
        self.reset_url = '/api/auth/password-reset/'
        self.reset_confirm_url = '/api/auth/password-reset-confirm/'
    
    def test_request_password_reset_valid_email(self):
        """Puede solicitar reset con email válido"""
        data = {'email': 'user@test.com'}
        
        response = self.client.post(self.reset_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.data)
        
        # En desarrollo, debe retornar el token
        self.assertIn('dev_token', response.data)
        self.assertIn('dev_uid', response.data)
    
    def test_request_password_reset_invalid_email(self):
        """Respuesta genérica para email no existente (seguridad)"""
        data = {'email': 'nonexistent@test.com'}
        
        response = self.client.post(self.reset_url, data, format='json')
        
        # Por seguridad, retorna 200 OK incluso si el email no existe
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.data)
    
    def test_request_password_reset_no_email(self):
        """Falla si no se proporciona email"""
        data = {}
        
        response = self.client.post(self.reset_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)
    
    def test_confirm_password_reset_with_valid_token(self):
        """Puede resetear contraseña con token válido"""
        # Generar token
        token = default_token_generator.make_token(self.user)
        
        data = {
            'token': token,
            'new_password': 'newpass789',
            'confirm_password': 'newpass789'
        }
        
        response = self.client.post(self.reset_confirm_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('restablecida exitosamente', response.data['detail'])
        
        # Verificar que la nueva contraseña funciona
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass789'))
    
    def test_confirm_password_reset_with_invalid_token(self):
        """Falla con token inválido"""
        data = {
            'token': 'invalid-token-123',
            'new_password': 'newpass789',
            'confirm_password': 'newpass789'
        }
        
        response = self.client.post(self.reset_confirm_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('inválido', response.data['detail'])
    
    def test_confirm_password_reset_password_mismatch(self):
        """Falla si las contraseñas no coinciden"""
        token = default_token_generator.make_token(self.user)
        
        data = {
            'token': token,
            'new_password': 'newpass789',
            'confirm_password': 'differentpass'
        }
        
        response = self.client.post(self.reset_confirm_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('confirm_password', response.data)
    
    def test_confirm_password_reset_too_short(self):
        """Falla si la contraseña es muy corta"""
        token = default_token_generator.make_token(self.user)
        
        data = {
            'token': token,
            'new_password': 'short',
            'confirm_password': 'short'
        }
        
        response = self.client.post(self.reset_confirm_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)
    
    def test_token_only_works_once(self):
        """Token solo puede usarse una vez"""
        token = default_token_generator.make_token(self.user)
        
        data = {
            'token': token,
            'new_password': 'newpass789',
            'confirm_password': 'newpass789'
        }
        
        # Primera vez: éxito
        response1 = self.client.post(self.reset_confirm_url, data, format='json')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Segunda vez: falla (el token se invalida al cambiar la contraseña)
        data['new_password'] = 'anotherpass'
        data['confirm_password'] = 'anotherpass'
        response2 = self.client.post(self.reset_confirm_url, data, format='json')
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_deactivated_user_cannot_reset_password(self):
        """Usuario desactivado no puede resetear contraseña"""
        self.user.is_active = False
        self.user.save()
        
        token = default_token_generator.make_token(self.user)
        
        data = {
            'token': token,
            'new_password': 'newpass789',
            'confirm_password': 'newpass789'
        }
        
        response = self.client.post(self.reset_confirm_url, data, format='json')
        
        # El token no es válido para usuarios desactivados
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ============================================================================
# TESTS DE INTEGRACIÓN
# ============================================================================

class ProfileManagementIntegrationTests(APITestCase):
    """Tests de integración de flujos completos"""
    
    def setUp(self):
        """Configuración inicial para cada test"""
        self.client = APIClient()
    
    def test_complete_user_lifecycle(self):
        """Test completo: registro -> actualizar perfil -> cambiar contraseña"""
        
        # 1. Registrar usuario
        register_data = {
            'email': 'newuser@test.com',
            'password': 'initialpass123',
            'first_name': 'María',
            'last_name': 'González',
            'role': 'CLIENT'
        }
        
        register_response = self.client.post(
            '/api/auth/register/',
            register_data,
            format='json'
        )
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        
        # 2. Login
        login_data = {
            'email': 'newuser@test.com',
            'password': 'initialpass123'
        }
        
        login_response = self.client.post(
            '/api/auth/login/',
            login_data,
            format='json'
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        token = login_response.data['access']
        
        # 3. Actualizar perfil
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        profile_data = {
            'phone_number': '+52 999 888 7777',
            'city': 'Querétaro',
            'state': 'Querétaro'
        }
        
        profile_response = self.client.patch(
            '/api/users/me/',
            profile_data,
            format='json'
        )
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_response.data['phone_number'], '+52 999 888 7777')
        
        # 4. Cambiar contraseña
        password_data = {
            'old_password': 'initialpass123',
            'new_password': 'newpass456',
            'confirm_password': 'newpass456'
        }
        
        password_response = self.client.post(
            '/api/auth/change-password/',
            password_data,
            format='json'
        )
        self.assertEqual(password_response.status_code, status.HTTP_200_OK)
        
        # 5. Verificar login con nueva contraseña
        self.client.credentials()  # Limpiar credenciales
        
        new_login_data = {
            'email': 'newuser@test.com',
            'password': 'newpass456'
        }
        
        new_login_response = self.client.post(
            '/api/auth/login/',
            new_login_data,
            format='json'
        )
        self.assertEqual(new_login_response.status_code, status.HTTP_200_OK)
    
    def test_complete_password_reset_flow(self):
        """Test completo de reset de contraseña"""
        
        # 1. Crear usuario
        user = User.objects.create_user(
            email='resettest@test.com',
            password='oldpass123'
        )
        
        # 2. Solicitar reset
        reset_request = self.client.post(
            '/api/auth/password-reset/',
            {'email': 'resettest@test.com'},
            format='json'
        )
        self.assertEqual(reset_request.status_code, status.HTTP_200_OK)
        
        token = reset_request.data['dev_token']
        
        # 3. Confirmar reset con token
        reset_confirm = self.client.post(
            '/api/auth/password-reset-confirm/',
            {
                'token': token,
                'new_password': 'resetpass456',
                'confirm_password': 'resetpass456'
            },
            format='json'
        )
        self.assertEqual(reset_confirm.status_code, status.HTTP_200_OK)
        
        # 4. Login con nueva contraseña
        login_response = self.client.post(
            '/api/auth/login/',
            {
                'email': 'resettest@test.com',
                'password': 'resetpass456'
            },
            format='json'
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
