import json
import logging
from channels.generic.websocket import WebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from .models import ServiceOrder, Message
from .serializers import MessageSerializer

# Configuración del logger
logger = logging.getLogger(__name__)


class ChatConsumer(WebsocketConsumer):
    """
    Consumer para manejar conexiones WebSocket del chat en tiempo real.
    
    URL: ws://localhost:8000/ws/chat/{order_id}/?token=<jwt_access_token>
    
    Protocolo:
    - Cliente envía: {"message": "Texto del mensaje"}
    - Servidor broadcast: {"id": 123, "sender": 6, "sender_name": "María", "content": "...", "timestamp": "..."}
    """
    
    def connect(self):
        """
        Maneja la conexión inicial del WebSocket.
        Valida autenticación y permisos antes de aceptar.
        
        Códigos de cierre:
        - 4001: Usuario no autenticado
        - 4003: Usuario sin permisos para esta orden
        - 4004: Orden no encontrada
        - 4005: Orden en estado no válido para chat
        """
        self.user = self.scope['user']
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.room_group_name = f'chat_{self.order_id}'
        
        # Validar autenticación
        if isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            logger.warning(f"Intento de conexión anónima a orden {self.order_id}")
            self.close(code=4001)
            return
        
        # Validar existencia de la orden
        try:
            self.order = ServiceOrder.objects.select_related(
                'client', 'worker', 'worker__user'
            ).get(id=self.order_id)
        except ServiceOrder.DoesNotExist:
            logger.warning(f"Usuario {self.user.email} intentó conectar a orden inexistente: {self.order_id}")
            self.close(code=4004)
            return
        except ValueError:
            logger.error(f"ID de orden inválido: {self.order_id}")
            self.close(code=4004)
            return
        
        # Validar permisos del usuario
        is_client = self.user == self.order.client
        is_worker = self.user == self.order.worker.user
        
        if not (is_client or is_worker):
            logger.warning(
                f"Usuario {self.user.email} sin permisos para orden {self.order_id}"
            )
            self.close(code=4003)
            return
        
        # Validar estado de la orden
        if self.order.status in ['CANCELLED', 'COMPLETED']:
            logger.info(
                f"Intento de conexión a orden {self.order_id} con estado {self.order.status}"
            )
            self.close(code=4005)
            return
        
        # Agregar usuario al grupo de chat
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )
        
        # Aceptar conexión
        self.accept()
        
        # Enviar mensaje de confirmación
        role = "cliente" if is_client else "trabajador"
        logger.info(f"Usuario {self.user.email} ({role}) conectado a orden {self.order_id}")
        
        self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': f'Conectado al chat de la orden #{self.order_id}',
            'order_id': self.order_id,
            'user_role': role
        }))
    
    def disconnect(self, close_code):
        """
        Maneja la desconexión del WebSocket.
        Remueve usuario del grupo y registra la desconexión.
        
        Args:
            close_code (int): Código de cierre de la conexión
        """
        if hasattr(self, 'room_group_name'):
            async_to_sync(self.channel_layer.group_discard)(
                self.room_group_name,
                self.channel_name
            )
            
            if hasattr(self, 'user') and hasattr(self, 'order_id'):
                logger.info(
                    f"Usuario {self.user.email} desconectado de orden {self.order_id} "
                    f"(código: {close_code})"
                )
    
    def receive(self, text_data):
        """
        Recibe mensaje del cliente WebSocket.
        Valida, guarda en BD y hace broadcast al grupo.
        
        Args:
            text_data (str): Datos JSON con el mensaje
        """
        try:
            data = json.loads(text_data)
            message_content = data.get('message', '').strip()
            
            # Validar que el mensaje no esté vacío
            if not message_content:
                logger.warning(f"Usuario {self.user.email} intentó enviar mensaje vacío")
                self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'El mensaje no puede estar vacío'
                }))
                return
            
            # Validar longitud del mensaje
            if len(message_content) > 5000:
                logger.warning(
                    f"Usuario {self.user.email} intentó enviar mensaje demasiado largo "
                    f"({len(message_content)} caracteres)"
                )
                self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'El mensaje no puede exceder 5000 caracteres'
                }))
                return
            
            # Crear mensaje en la base de datos
            message = Message.objects.create(
                service_order=self.order,
                sender=self.user,
                content=message_content
            )
            
            logger.info(
                f"Mensaje #{message.id} creado por {self.user.email} en orden {self.order_id}"
            )
            
            # Serializar mensaje para envío
            serializer = MessageSerializer(message)
            
            # Broadcast al grupo
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': serializer.data
                }
            )
        
        except json.JSONDecodeError as e:
            logger.error(f"Error de JSON del usuario {self.user.email}: {str(e)}")
            self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Formato JSON inválido'
            }))
        except Exception as e:
            logger.error(
                f"Error al procesar mensaje de {self.user.email}: {str(e)}",
                exc_info=True
            )
            self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Error al procesar mensaje: {str(e)}'
            }))
    
    def chat_message(self, event):
        """
        Recibe mensaje del grupo y lo envía al WebSocket del cliente.
        
        Args:
            event (dict): Evento con el mensaje a enviar
        """
        message = event['message']
        
        # Enviar mensaje al cliente WebSocket
        self.send(text_data=json.dumps({
            'type': 'chat_message',
            **message
        }))
        
        logger.debug(f"Mensaje #{message.get('id')} enviado a cliente en orden {self.order_id}")
