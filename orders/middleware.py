import logging
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from users.models import User
from urllib.parse import parse_qs

# Configuración de logger para middleware
logger = logging.getLogger(__name__)

@database_sync_to_async
def get_user_from_token(token_key):
    """
    Obtiene el usuario desde el token JWT de forma asíncrona.
    
    Args:
        token_key (str): Token JWT de acceso
        
    Returns:
        User | AnonymousUser: Usuario autenticado o usuario anónimo si el token es inválido
    """
    if not token_key or len(token_key) < 10:
        logger.warning("Token JWT vacío o demasiado corto")
        return AnonymousUser()
    
    try:
        # Validar y decodificar token JWT
        access_token = AccessToken(token_key)
        user_id = access_token['user_id']
        
        # Obtener usuario de la base de datos
        user = User.objects.select_related('worker_profile').get(id=user_id)
        
        if not user.is_active:
            logger.warning(f"Usuario inactivo intentó conectar: {user.email}")
            return AnonymousUser()
            
        logger.info(f"Usuario autenticado correctamente: {user.email}")
        return user
        
    except InvalidToken as e:
        logger.warning(f"Token JWT inválido: {str(e)}")
        return AnonymousUser()
    except TokenError as e:
        logger.warning(f"Error al procesar token JWT: {str(e)}")
        return AnonymousUser()
    except User.DoesNotExist:
        logger.warning(f"Usuario no encontrado para user_id del token")
        return AnonymousUser()
    except Exception as e:
        logger.error(f"Error inesperado en autenticación WebSocket: {str(e)}", exc_info=True)
        return AnonymousUser()

class JWTAuthMiddleware(BaseMiddleware):
    """
    Middleware para autenticar WebSockets usando JWT desde query params.
    
    Uso: ws://localhost:8000/ws/chat/{order_id}/?token=<jwt_access_token>
    
    Este middleware intercepta las conexiones WebSocket y valida el token JWT
    proporcionado en los parámetros de consulta. Si el token es válido, 
    el usuario se agrega al scope del WebSocket para su uso posterior.
    
    Ejemplo de conexión:
        ws://localhost:8000/ws/chat/123/?token=eyJ0eXAiOiJKV1QiLCJhbGc...
    """
    
    async def __call__(self, scope, receive, send):
        """
        Procesa la conexión WebSocket y autentica al usuario.
        
        Args:
            scope (dict): Información de la conexión WebSocket
            receive (callable): Función para recibir mensajes
            send (callable): Función para enviar mensajes
        """
        # Extraer query string de la URL
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = parse_qs(query_string)
        
        # Obtener token del parámetro 'token'
        token = query_params.get('token', [None])[0]
        
        if token:
            # Autenticar usuario con el token proporcionado
            scope['user'] = await get_user_from_token(token)
            logger.debug(f"WebSocket scope actualizado con usuario: {scope['user']}")
        else:
            # Sin token, el usuario será anónimo
            scope['user'] = AnonymousUser()
            logger.debug("WebSocket conectado sin token (usuario anónimo)")
        
        # Continuar con el siguiente middleware/consumer
        return await super().__call__(scope, receive, send)
