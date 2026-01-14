import json
from channels.generic.websocket import WebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from .models import ServiceOrder, Message
from .serializers import MessageSerializer


class ChatConsumer(WebsocketConsumer):
    """
    Consumer para manejar conexiones WebSocket del chat en tiempo real.
    
    URL: ws://localhost:8000/ws/chat/{order_id}/?token=<jwt_access_token>
    
    Protocolo:
    - Cliente envía: {"message": "Texto del mensaje"}
    - Servidor broadcast: {"id": 123, "sender": 6, "sender_name": "María", "content": "...", "timestamp": "..."}
    """
    
    def connect(self):
        self.user = self.scope['user']
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.room_group_name = f'chat_{self.order_id}'
        
        if isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            self.close(code=4001)
            return
        
        try:
            self.order = ServiceOrder.objects.select_related(
                'client', 'worker', 'worker__user'
            ).get(id=self.order_id)
        except ServiceOrder.DoesNotExist:
            self.close(code=4004)
            return
        
        is_client = self.user == self.order.client
        is_worker = self.user == self.order.worker.user
        
        if not (is_client or is_worker):
            self.close(code=4003)
            return
        
        if self.order.status in ['CANCELLED', 'COMPLETED']:
            self.close(code=4005)
            return
        
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )
        
        self.accept()
        
        self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': f'Conectado al chat de la orden #{self.order_id}'
        }))
    
    def disconnect(self, close_code):
        """
        Maneja la desconexión del WebSocket.
        Remueve usuario del grupo.
        """
        if hasattr(self, 'room_group_name'):
            async_to_sync(self.channel_layer.group_discard)(
                self.room_group_name,
                self.channel_name
            )
    
    def receive(self, text_data):
        """
        Recibe mensaje del cliente WebSocket.
        Guarda en BD y hace broadcast al grupo.
        """
        try:
            data = json.loads(text_data)
            message_content = data.get('message', '').strip()
            
            if not message_content:
                self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'El mensaje no puede estar vacío'
                }))
                return
            
            message = Message.objects.create(
                service_order=self.order,
                sender=self.user,
                content=message_content
            )
            
            serializer = MessageSerializer(message)
            
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': serializer.data
                }
            )
        
        except json.JSONDecodeError:
            self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Formato JSON inválido'
            }))
        except Exception as e:
            self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Error al procesar mensaje: {str(e)}'
            }))
    
    def chat_message(self, event):
        """
        Recibe mensaje del grupo y lo envía al WebSocket del cliente.
        """
        message = event['message']
        
        self.send(text_data=json.dumps({
            'type': 'chat_message',
            **message
        }))
