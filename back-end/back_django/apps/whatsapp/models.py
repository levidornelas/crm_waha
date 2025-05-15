from django.db import models
import uuid
from django.contrib.auth.models import User


class Mensagem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    atendimento = models.ForeignKey('Atendimento', on_delete=models.CASCADE, related_name='mensagens', null=True, blank=True)
    chat_id = models.CharField(max_length=100)
    from_me = models.BooleanField()
    mensagem = models.TextField(blank=True)
    timestamp = models.DateTimeField()
    has_media = models.BooleanField(default=False)
    media_url = models.URLField(blank=True, null=True)
    media_tipo = models.CharField(max_length=100, blank=True, null=True)
    media_file_name = models.CharField(max_length=255, blank=True, null=True)
    media_file = models.FileField(upload_to='anexos/', blank=True, null=True)


    class Meta:
        verbose_name = 'Mensagem'
        verbose_name_plural = 'Mensagens'



class Atendimento(models.Model):

    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('em_andamento', 'Em andamento'),
        ('finalizado', 'Finalizado'),
        ('cancelado', 'Cancelado'),
    ]

    chat_id = models.CharField(max_length=100, unique=True)
    colaborador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='atendimentos')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    iniciado_em = models.DateTimeField(auto_now_add=True)
    finalizado_em = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Atendimento {self.chat_id} - {self.get_status_display()}"