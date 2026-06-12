from gevent import monkey
monkey.patch_all()

from flask import Flask, request, session, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from google import genai
from google.genai import types
from dotenv import load_dotenv
from uuid import uuid4
import os
import sys

load_dotenv()

MODELO = "gemini-2.5-flash"

instrucoes = """
Você é o FashionBot, um assistente virtual especialista em moda, estilo e tendências. Sua missão é ajudar os usuários com dicas de moda, combinações de roupas, tendências atuais e conselhos de estilo.

REGRAS IMPORTANTES:
1. Seja sempre amigável, entusiasmada e com um tom fashionista
2. Dê dicas sobre combinações de cores, tecidos e acessórios
3. Recomende looks para diferentes ocasiões (trabalho, festa, casual, academia)
4. Fale sobre tendências atuais e atemporais
5. Considere diferentes biótipos e estilos pessoais
6. Sugira onde encontrar inspiração (passarelas, redes sociais, revistas)
7. Se não souber algo, seja honesta e sugira pesquisar em fontes confiáveis de moda

EXEMPLOS DE RESPOSTAS:
- "Para um look casual chique, experimente combinar uma calça de alfaiataria com uma t-shirt básica e um tênis branco!"
- "A cor do momento é o verde menta! Combina super bem com tons neutros como bege e branco."
- "Seu biotipo é incrível! Para valorizar, aposte em peças que marcam a cintura..."

Responda grosserias com elegância e mantenha o foco em ajudar com moda e estilo.
"""

api_key = os.getenv("GENAI_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("ERRO: Nenhuma chave de API encontrada!")
    client = None
else:
    client = genai.Client(api_key=api_key)

app = Flask(__name__)
app.secret_key = "ch@tb07"
CORS(app, resources={r"/*": {"origins": "*"}})

socketio = SocketIO(app, cors_allowed_origins="*")

active_chats = {}

def get_user_chat(session_id=None):
    if client is None:
        return None
        
    if not session_id:
        if 'session_id' not in session:
            session['session_id'] = str(uuid4())
        session_id = session['session_id']

    if session_id not in active_chats:
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
        "api_key_configured": client is not None
    })

@socketio.on('connect')
def handle_connect():
    print(f"Cliente conectado: {request.sid}")
    if client is None:
        emit('erro', {'erro': 'API key não configurada'})
        return
        
    # Recupera ou gera o ID de sessão para enviar ao cliente
    if 'session_id' not in session:
        session['session_id'] = str(uuid4())
    session_id = session['session_id']
    
    emit('status_conexao', {
        'data': 'Conectado com sucesso!',
        'session_id': session_id
    })

@socketio.on('enviar_mensagem')
def handle_enviar_mensagem(data):
    if client is None:
        emit('erro', {"erro": "API key não configurada"})
        return
        
    try:
        mensagem_usuario = data.get("mensagem")
        session_id = data.get("session_id")
        if not mensagem_usuario:
            emit('erro', {"erro": "Mensagem vazia"})
            return

        user_chat = get_user_chat(session_id)
        if user_chat is None:
            emit('erro', {"erro": "Sessão não inicializada"})
            return

        resposta_gemini = user_chat.send_message(mensagem_usuario)
        resposta_texto = resposta_gemini.text if hasattr(resposta_gemini, 'text') else resposta_gemini.candidates[0].content.parts[0].text
        
        emit('nova_mensagem', {"remetente": "bot", "texto": resposta_texto})

    except Exception as e:
        print(f"Erro: {e}")
        emit('erro', {"erro": str(e)})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Cliente desconectado: {request.sid}")

application = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)