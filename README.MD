### Inicie os containers

Execute o comando abaixo para iniciar os containers do Docker:

```bash
cd docker
docker-compose up --build
```

### Adicione o webhook no WAHA: 

* Após acessar o django, a sessão default deve ser startada automaticamente.
* Clique em 'configuration', que estará como símbolo de engrenagem na sessão
* Clique no +webhook, e adicione um webhook com url 'http://django:8000/webhook/'
* Remova o event de session status e deixe só o de message.
* Ao depender da quantidade de mensagens, a sessão irá demorar para sincronizar (como no whatsapp web.)

### Crie um SUPERUSER: 

```
docker exec -it docker-django-1 python manage.py createsuperuser
```


### Acesse o aplicativo

* O Django estará disponível em: `http://localhost:8000`
* O WAHA estará disponível em: `http://localhost:3000`

### TODO: 

* Conseguir baixar e exibir os arquivos de mídia que são enviados pelo webhook;
* Enviar anexos(imagens, videos, PDF);
* auth;
* Gerenciamento de lógica das mensagens (criação de atendimento, atribuição de colaborador, etc)