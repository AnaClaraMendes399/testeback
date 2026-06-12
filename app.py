from flask import Flask, request, session, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from google import genai
from google.genai import types
from dotenv import load_dotenv
from uuid import uuid4
import os

# Carrega variáveis de ambiente
load_dotenv()

MODELO = "gemini-2.5-flash"

instrucoes = """
Você é um assistente virtual amigável e prestativo. Sua função é responder a perguntas dos usuários e fornecer informações úteis somente sobre diversos assuntos.
Tente manter as respostas curtas, concisas, objetivas e claras. Se não souber a resposta, diga que não sabe e sugira que o usuário procure em outro lugar.
Responda grosserias, ofensas e palavrões de forma amigável e cortês.
"""

# Inicializa o cliente Gemini
api_key = os.getenv("GENAI_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("⚠️ ERRO: Nenhuma chave de API encontrada! Configure GENAI_KEY ou GOOGLE_API_KEY")
    api_key = "CHAVE_NAO_CONFIGURADA"  # Placeholder para não quebrar

client = genai.Client(api_key=api_key)

app = Flask(__name__)
app.secret_key = "ch@tb07"

# Configura CORS corretamente
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

active_chats = {}

def get_user_chat():
    if 'session_id' not in session:
        session['session_id'] = str(uuid4())
        print(f"Nova sessão: {session['session_id']}")

    session_id = session['session_id']

    if session_id not in active_chats:
        print(f"Criando chat para: {session_id}")
        try:
            chat_session = client.chats.create(
                model=MODELO,
                config=types.GenerateContentConfig(system_instruction=instrucoes)
            )
            active_chats[session_id] = chat_session
        except Exception as e:
            print(f"Erro ao criar chat: {e}")
            return None
    
    return active_chats.get(session_id)

@app.route('/')
def root():
    return jsonify({
        "api-websocket": "chatbot",
        "status": "ok",
        "message": "Servidor funcionando!"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@socketio.on('connect')
def handle_connect():
    print(f"Cliente conectado: {request.sid}")
    try:
        user_chat = get_user_chat()
        emit('status_conexao', {'data': 'Conectado com sucesso!'})
    except Exception as e:
        print(f"Erro no connect: {e}")
        emit('erro', {'erro': 'Falha ao inicializar'})

@socketio.on('enviar_mensagem')
def handle_enviar_mensagem(data):
    try:
        mensagem_usuario = data.get("mensagem")
        print(f"Mensagem recebida: {mensagem_usuario}")

        if not mensagem_usuario:
            emit('erro', {"erro": "Mensagem vazia"})
            return

        user_chat = get_user_chat()
        if user_chat is None:
            emit('erro', {"erro": "Sessão não inicializada"})
            return

        resposta_gemini = user_chat.send_message(mensagem_usuario)
        resposta_texto = resposta_gemini.text if hasattr(resposta_gemini, 'text') else resposta_gemini.candidates[0].content.parts[0].text
        
        emit('nova_mensagem', {"remetente": "bot", "texto": resposta_texto})
        print(f"Resposta enviada")

    except Exception as e:
        print(f"Erro: {e}")
        emit('erro', {"erro": str(e)})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Cliente desconectado: {request.sid}")

# ⚠️ IMPORTANTE: Para o Render
if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5000)

# O Gunicorn precisa disso
application = app