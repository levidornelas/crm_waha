import json
import re
from datetime import datetime
import requests

from channels.layers import get_channel_layer
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from asgiref.sync import async_to_sync
from django.utils.timezone import make_aware


from .services.utils import normalizar_id
from .services.waha import WahaClient

"""
Os consumers são os Websockets: Eles permitem que haja uma comunicação em Real-Time do front com o backend, sem que haja F5;
É preciso um JavaScript no front-end para consumir esses websockets e renderizar as informações de forma nativa.
"""

#Websocket responsável por notificar e enviar mensagens num chat específico
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.safe_chat_id = re.sub(r'[^a-zA-Z0-9_.-]', '_', self.chat_id)
        self.room_group_name = f"chat_{self.safe_chat_id[:90]}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('text')
        normalized_chat_id = normalizar_id(self.chat_id)
        has_media = data.get('hasMedia', False)
        media_url = data.get('mediaUrl', '')
        media_mimetype = data.get('mediaTipo', '')
        media_filename = data.get('mediaFileName', '')
        waha = WahaClient()

        try:
            response = waha.enviar_mensagem(normalized_chat_id, message)
            if response.ok:
                res_data = response.json()
                timestamp_unix = int(res_data.get('timestamp', datetime.now().timestamp()))
              
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'new_message',
                        'message': message,
                        'fromMe': True,
                        'timestamp': timestamp_unix,
                        'hasMedia': has_media,
                        'mediaUrl': media_url,
                        'mediaTipo': media_mimetype,
                        'mediaFileName': media_filename,
                    }
                )

                await self.channel_layer.group_send(
                    "main_chat_updates",
                    {
                        'type': 'new_message',
                        'chatId': self.chat_id,
                        'message': message,
                        'fromMe': True,
                        'timestamp': timestamp_unix,
                        'hasMedia': has_media,
                        'mediaUrl': media_url,
                        'mediaTipo': media_mimetype,
                        'mediaFileName': media_filename,
                    }
                )
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f"Erro ao enviar mensagem: {response.text}"
                }))
        except requests.RequestException as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Erro de conexão com WAHA: {str(e)}"
            }))

    async def new_message(self, event):
        from .models import Mensagem

        timestamp_unix = event.get('timestamp')
        timestamp_dt = None
        if timestamp_unix:
            timestamp_dt = make_aware(datetime.fromtimestamp(timestamp_unix))

        # Enviar a mensagem para o frontend
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event.get('message'),
            'fromMe': event.get('fromMe'),
            'timestamp': timestamp_dt.strftime('%H:%M') if timestamp_dt else '',
            'hasMedia': event.get('hasMedia', False),
            'mediaUrl': event.get('mediaUrl'),
            'mediaTipo': event.get('mediaTipo'),
            'mediaFileName': event.get('mediaFileName'),
        }))

        atendimento = await self.get_atendimento(normalizar_id(self.chat_id))

        # Salvar no banco
        await self.salvar_mensagem(
            chat_id=normalizar_id(self.chat_id),
            from_me=event.get('fromMe', False),
            mensagem=event.get('message'),
            timestamp=timestamp_dt,
            has_media=event.get('hasMedia', False),
            media_url=event.get('mediaUrl'),
            media_tipo=event.get('mediaTipo'),
            media_file_name=event.get('mediaFileName'),
            media_file=None,
            atendimento=atendimento,
        )

        # Atualizar status para "em_andamento" se for a primeira mensagem do atendente
        if event.get('fromMe', False):
            await self.atualizar_status_atendimento(atendimento)

    @sync_to_async
    def salvar_mensagem(self, **kwargs):
        from .models import Mensagem
        Mensagem.objects.create(**kwargs)
        print('Salvando no banco!')

    @sync_to_async
    def get_atendimento(self, chat_id):
        from .models import Atendimento

        """Recupera o atendimento para o chat_id."""
        try:
            return Atendimento.objects.filter(chat_id=chat_id).first()
        except Exception as e:
            print(f"Erro ao recuperar atendimento: {str(e)}")
            return None
    
    @sync_to_async
    def atualizar_status_atendimento(self, atendimento):
        if atendimento and atendimento.status == 'pendente':
            atendimento.status = 'em_andamento'
            atendimento.save()

            # Enviar evento para o grupo 'main_chat_updates'
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'main_chat_updates',
                {
                    'type': 'atualizar_status',
                    'atendimento': {
                        'chat_id': atendimento.chat_id,
                        'colaborador': atendimento.colaborador.username if atendimento.colaborador else None,
                        'status': atendimento.status,
                    },
                }
            )

# Websocket principal: atualizações em tempo real que correspondem a todas as conversas, não relacionada a chats específicos.
# SERVE PARA ATUALIZAR A SIDEBAR DE MENSAGENS
class MainConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'main_chat_updates'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def new_message(self, event):
        timestamp_unix = event.get('timestamp')
        timestamp_str = datetime.fromtimestamp(timestamp_unix).strftime('%H:%M') if timestamp_unix else datetime.now().strftime('%H:%M')

        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'chatId': event['chatId'],
            'message': event['message'],
            'fromMe': event.get('fromMe'),
            'timestamp': timestamp_str,
            'hasMedia': event.get('hasMedia', False),
            'mediaUrl': event.get('mediaUrl'),
            'mediaTipo': event.get('mediaTipo'),
            'mediaFileName': event.get('mediaFileName'),
        }))

    async def novo_atendimento(self, event):
        await self.send(text_data=json.dumps({
            'type': 'novo_atendimento',
            'atendimento': event['atendimento'],
        }))

    async def atualizar_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'atualizar_status',
            'atendimento': event['atendimento'],
        }))