from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from users.models import User
from urllib.parse import parse_qs

@database_sync_to_async
def get_user_from_token(token_key):
    """
    Obtiene el usuario desde el token JWT.
    """
    try:
        access_token = AccessToken(token_key)
        user_id = access_token['user_id']
        user = User.objects.get(id=user_id)
        return user
    except InvalidToken as e:
        return AnonymousUser()
    except TokenError as e:
        return AnonymousUser()
    except User.DoesNotExist:
        return AnonymousUser()
    except Exception as e:
        return AnonymousUser()

class JWTAuthMiddleware(BaseMiddleware):
    """
    Middleware para autenticar WebSockets usando JWT desde query params.
    Uso: ws://localhost:8000/ws/chat/{order_id}/?token=<jwt_access_token>
    """
    
    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]
        
        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)
