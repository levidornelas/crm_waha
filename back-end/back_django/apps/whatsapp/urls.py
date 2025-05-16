from django.urls import path

from .views import (
    QRCodeView,
    ListarChatsView,
    VerChatView,
    FinalizarAtendimentoView
)
from .webhook import webhook_recebimento

urlpatterns = [
    path('', QRCodeView.as_view(), name='qr-code'),
    path("chats/", ListarChatsView.as_view(), name="listar-chats"),
    path("chats/<str:chat_id>/", VerChatView.as_view(), name="ver-chat"),
    path('webhook/', webhook_recebimento, name='webhook_waha'),
    path('api/finalizar/<str:chat_id>/', FinalizarAtendimentoView.as_view(), name='finalizar-atendimento'),
]
