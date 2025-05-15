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


@csrf_exempt
def webhook_recebimento(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        body_unicode = request.body.decode('utf-8')
        data = json.loads(body_unicode)

        payload = data.get('payload', {})
        mensagem = payload.get('body', '')
        has_media = payload.get('hasMedia', False)
        media = payload.get('media', {}) or {}

        media_url = media.get('url') if has_media else None
        media_mimetype = media.get('mimetype') if has_media else None
        media_filename = media.get('filename') if has_media else None

        chat_id = payload.get('from') or payload.get('to')
        normalized_chat_id = normalizar_id(chat_id)
        from_me = payload.get('fromMe', False)
        timestamp_unix = payload.get('timestamp')
        timestamp_dt = make_aware(datetime.fromtimestamp(timestamp_unix))

        # Processar mídia se existir
        media_file = None
        if media_url:
            media_url_download = media_url.replace('localhost', 'waha')  # só para backend baixar
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


        # Verificar e criar atendimento se necessário (apenas para mensagens recebidas)
        atendimento = None
        if not from_me:
            atendimento = create_or_get_atendimento(normalized_chat_id)
        else:
            # Para mensagens enviadas, apenas buscar o atendimento existente
            atendimento = Atendimento.objects.filter(chat_id=normalized_chat_id).first()

        # Salvar mensagem no banco
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

        # Enviar mensagem para os websockets
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
    """Cria um novo atendimento ou retorna o existente para o chat_id."""
    try:
        # Verificar se já existe um atendimento para este chat
        atendimento = Atendimento.objects.filter(chat_id=chat_id).first()
        

        # FUNÇÃO IMPORTANTE A SER ADICIONADA: REDIRECIONAR AO COLABORADOR;
        if not atendimento:
            # Se não existir, criar um novo atendimento
            # Atribuir ao primeiro colaborador disponível (simplificado)
            colaborador = User.objects.filter(is_staff=True).first()
            
            atendimento = Atendimento.objects.create(
                chat_id=chat_id,
                colaborador=colaborador,
                status='pendente'
            )
            print(f"Novo atendimento criado para o chat {chat_id}, atribuído a {colaborador.username if colaborador else 'ninguém'}")
                   
        return atendimento
    except Exception as e:
        print(f"Erro ao criar/obter atendimento: {str(e)}")
        return None