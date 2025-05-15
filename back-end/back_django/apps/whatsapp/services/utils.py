import re


# Normaliza o ID do grupo para um formato seguro para uso em websockets;
def normalizarGrupoWs(chat_id):
    safe_chat_id = re.sub(r'[^a-zA-Z0-9_.-]', '_', chat_id)
    return f"chat_{safe_chat_id[:90]}"


def normalizar_id(chat_id):
    # Se já estiver com @c.us ou @g.us, retorna como está
    if chat_id.endswith("@c.us") or chat_id.endswith("@g.us"):
        return chat_id
    # Remove caracteres não numéricos
    phone_number = re.sub(r'\D', '', chat_id)
    return f"{phone_number}@c.us"
