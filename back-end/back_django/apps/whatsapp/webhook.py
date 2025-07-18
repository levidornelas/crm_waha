import json
from datetime import datetime
import os
import uuid
import requests

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.http import JsonResponse, HttpResponse
from django.utils.timezone import make_aware
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.core.files.base import ContentFile

from .services.utils import normalizarGrupoWs, normalizar_id
from .models import Mensagem, Atendimento
from .services.waha import WahaClient


@csrf_exempt
def webhook_recebimento(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        body_unicode = request.body.decode('utf-8')
        data = json.loads(body_unicode)

        payload = data.get('payload', {})
        chat_id = payload.get('from') or payload.get('to')

        # Ignorar grupos (chat_id terminando com '@g.us')
        if chat_id and chat_id.endswith('@g.us') or chat_id == 'status@broadcast':
            print(f'Ignorando mensagem de grupo ou Status: {chat_id}')
            return JsonResponse({'status': 'ignored group message'})

        mensagem = payload.get('body', '')
        has_media = payload.get('hasMedia', False)
        media = payload.get('media', {}) or {}

        media_url = media.get('url') if has_media else None
        media_mimetype = media.get('mimetype') if has_media else None
        media_filename = media.get('filename') if has_media else None

        normalized_chat_id = normalizar_id(chat_id)
        from_me = payload.get('fromMe', False)
        timestamp_unix = payload.get('timestamp')
        timestamp_dt = make_aware(datetime.fromtimestamp(timestamp_unix))

        media_file = None
        if media_url:
            media_url_download = media_url.replace('localhost', 'waha')
            try:
                response = requests.get(media_url_download)
                response.raise_for_status()

                file_name = (
                    media_filename
                    or os.path.basename(media_url)
                    or f"arquivo_{uuid.uuid4().hex}.bin"
                )

                media_file = ContentFile(response.content, name=file_name)
            except requests.RequestException as e:
                print(f"Erro ao baixar mídia: {e}")

        atendimento = None
        if not from_me:
            atendimento = create_or_get_atendimento(normalized_chat_id)
        else:
            atendimento = Atendimento.objects.filter(chat_id=normalized_chat_id).first()

        Mensagem.objects.create(
            chat_id=normalized_chat_id,
            from_me=from_me,
            mensagem=mensagem,
            timestamp=timestamp_dt,
            has_media=has_media,
            media_url=media_url,
            media_tipo=media_mimetype,
            media_file_name=media_filename,
            media_file=media_file,
            atendimento=atendimento,
        )

        group_name = normalizarGrupoWs(chat_id)
        msg_payload = {
            'type': 'new_message',
            'message': mensagem,
            'fromMe': from_me,
            'timestamp': timestamp_unix,
            'hasMedia': has_media,
            'mediaUrl': media_url,
            'chatId': chat_id,
            'mediaTipo': media_mimetype,
            'mediaFileName': media_filename,
            'atendimento': {
                'chat_id': atendimento.chat_id if atendimento else None,
                'status': atendimento.status if atendimento else None,
            } if atendimento else None
        }

        print(f'Mensagem recebida e salva: {msg_payload}')

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(group_name, msg_payload)
        async_to_sync(channel_layer.group_send)('main_chat_updates', msg_payload)

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        print(f"Erro no webhook: {str(e)}")
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)


def create_or_get_atendimento(chat_id):
    waha = WahaClient()
    try:
        atendimento = Atendimento.objects.filter(chat_id=chat_id).first()
        if not atendimento:
            colaborador = User.objects.filter(is_staff=True).first()
            atendimento = Atendimento.objects.create(
                chat_id=chat_id,
                colaborador=colaborador,
                status='pendente'
            )
            print(f"Novo atendimento criado para o chat {chat_id}, atribuído a {colaborador.username if colaborador else 'ninguém'}")
        chats = waha.get_chats()
        chats_json = chats.json()

        chat_data = next((chat for chat in chats_json if chat.get('id') == atendimento.chat_id), None)

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'main_chat_updates',
            {
                'type': 'novo_atendimento',
                'atendimento': {
                    'chat_id': atendimento.chat_id,
                    'colaborador': atendimento.colaborador.username if atendimento.colaborador else None,
                    'status': atendimento.status,
                    'picture': chat_data.get('picture') if chat_data else None,
                    'lastMessage': chat_data.get('lastMessage'),
                    'name': chat_data.get('name')
                },
            }
        )
        return atendimento
    except Exception as e:
        print(f"Erro ao criar/obter atendimento: {str(e)}")
        return None
