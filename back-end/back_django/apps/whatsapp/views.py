
from datetime import datetime
import requests


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Mensagem, Atendimento
from .services.utils import normalizar_id
from .services.waha import WahaClient

@method_decorator(login_required, name='dispatch')
class QRCodeView(View):
    def get(self, request, *args, **kwargs):
        waha = WahaClient()
        status_response = waha.get_session_status()

        if status_response.ok:
            session_data = status_response.json()
            if session_data.get('status') == 'WORKING':
                return redirect('listar-chats')
            elif session_data.get('status') == 'STOPPED':
                waha.startar_sessao()
        return render(request, 'qr_code.html')

    def post(self, request, *args, **kwargs):
        waha = WahaClient()
        try:
            response = waha.criar_sessao()
            if response.ok:
                return render(
                    request,
                    'qr_code.html',
                    {'message': 'Sessão criada com sucesso. Escaneie o QR Code.'}
                )
            return render(
                request,
                'qr_code.html',
                {'message': f'Erro ao criar sessão: {response.text}'}
            )
        except requests.RequestException as e:
            return render(
                request,
                'qr_code.html',
                {'message': f'Erro de conexão: {str(e)}'}
            )

@method_decorator(login_required, name='dispatch')
class ListarChatsView(View):
    def get(self, request, *args, **kwargs):
        # Mostrar apenas atendimentos do colaborador logado
        atendimentos = Atendimento.objects.filter(colaborador=request.user)
        chat_ids = [atendimento.chat_id for atendimento in atendimentos]

        waha = WahaClient()
        try:
            response = waha.get_chats()
            if not response.ok:
                messages.error(request, f'Erro ao buscar chats: {response.text}')
                chats = []
                return render(request, 'listar_chats.html', {'chats': chats})

            todos_os_chats = response.json()
            
            # Filtrar chats que não são grupos e que pertencem ao colaborador logado
            chats = [
                chat for chat in todos_os_chats
                if not chat.get('id', '').endswith('@g.us')  # não grupos
                and chat.get('id')
                and normalizar_id(chat.get('id')) in chat_ids
                and chat.get('id') != 'status@broadcast'    # exclui status (stories)
            ]


            for chat in chats:
                timestamp = chat.get('lastMessage', {}).get('timestamp')
                if timestamp:
                    chat['lastMessage']['formatted_time'] = datetime.fromtimestamp(
                        timestamp
                    ).strftime('%H:%M')
                else:
                    chat['lastMessage']['formatted_time'] = ''
                
                # Adicionar status do atendimento ao chat para exibir na interface
                normalized_id = normalizar_id(chat.get('id'))
                atendimento = next((a for a in atendimentos if a.chat_id == normalized_id), None)
                if atendimento:
                    chat['status'] = atendimento.status
        
        except requests.RequestException as e:
            messages.error(request, f'Erro de conexão: {str(e)}')
            chats = []  
        return render(request, 'listar_chats.html', {'chats': chats})


@method_decorator(login_required, name='dispatch')
class VerChatView(View):
    def get(self, request, chat_id, *args, **kwargs):
        atendimento = None  # <<< Correção aqui
        try:
            normalized_chat_id = normalizar_id(chat_id)
            
            # Verificar se este chat pertence ao colaborador logado
            atendimento = get_object_or_404(Atendimento, chat_id=normalized_chat_id)
            
            if atendimento.colaborador != request.user:
                messages.error(request, 'Você não tem permissão para acessar este atendimento.')
            
            mensagens = (
                Mensagem.objects
                .filter(chat_id=normalized_chat_id)
                .order_by('-timestamp')[:50]
            )

        except Exception as e:
            mensagens = []
            messages.error(request, f'Erro ao buscar mensagens no banco: {str(e)}')

        return render(
            request,
            'partials/ver_chat.html',
            {'chat_id': chat_id, 'mensagens': mensagens, 'atendimento': atendimento}
        )


@method_decorator(login_required, name='dispatch')
class FinalizarAtendimentoView(APIView):
    def post(self, request, chat_id):
        try:
            atendimento = Atendimento.objects.get(chat_id=chat_id)
            atendimento.status = 'finalizado'
            atendimento.save()

            # Enviar evento para o grupo main_chat_updates
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
        except Exception as e:
            # Loga o erro para ajudar no debug (opcional)
            print(f"Erro ao finalizar atendimento: {str(e)}")
            return Response(
                {'success': False, 'message': 'Erro interno ao finalizar atendimento.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


        return Response({'success': True, 'message': 'Atendimento finalizado com sucesso.'})