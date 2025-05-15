import requests

# Classe para consumir a API do WAHA.
class WahaClient:
    BASE_URL = "http://waha:3000/"
    SESSION_ID = "default"
    HEADERS = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    def get_session_status(self):
        return requests.get(f"{self.BASE_URL}/api/sessions/{self.SESSION_ID}")

    def startar_sessao(self):
        return requests.post(f"{self.BASE_URL}/api/sessions/{self.SESSION_ID}/start")

    def criar_sessao(self):
        payload = {
            "name": self.SESSION_ID,
            "start": True,
        }

        return requests.post(f"{self.BASE_URL}/api/sessions", json=payload)

    def get_chats(self, limit=50):
        return requests.get(
            f"{self.BASE_URL}/api/{self.SESSION_ID}/chats/overview",
            params={"limit": limit}
            )

    def get_messages(self, chat_id, limit=30, download_media=True):
        return requests.get(
            f"{self.BASE_URL}/api/{self.SESSION_ID}/chats/{chat_id}/messages",
            params={"downloadMedia": "true" , "limit": limit}
        )

    def enviar_mensagem(self, chat_id, text):
        # Primeiro: marcar como lido
        requests.post(
            f"{self.BASE_URL}/api/sendSeen",
            json={"chatId": chat_id, "session": self.SESSION_ID},
            headers=self.HEADERS
        )

        # Segundo: enviar a mensagem
        return requests.post(
            f"{self.BASE_URL}/api/sendText",
            json={"chatId": chat_id, "text": text, "session": self.SESSION_ID},
            headers=self.HEADERS
        )


    # Enviar imagem

    # Enviar vídeo

    # Enviar documento (PDF, DOCX, etc.)

    # Enviar áudio
