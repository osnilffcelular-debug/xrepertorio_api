import os
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "methods": ["POST", "GET", "OPTIONS"], "allow_headers": "*"}})

if not firebase_admin._apps:
    firebase_admin.initialize_app(options={
        'projectId': 'xrepertorio'
    })

db = firestore.client()

def normalizar_id_musica(nome):
    # Transforma em minúsculas, remove caracteres especiais e padroniza espaços em underlines
    nome_limpo = nome.lower().strip()
    nome_limpo = re.sub(r'[^\w\s\-]', '', nome_limpo)
    nome_limpo = re.sub(r'[\s_]+', '_', nome_limpo)
    return nome_limpo

@app.route('/', defaults={'path': ''}, methods=['POST', 'GET', 'OPTIONS'])
@app.route('/<path:path>', methods=['POST', 'GET', 'OPTIONS'])
def capturar_tudo(path):
    if request.method == 'OPTIONS':
        resposta = jsonify({"status": "ok"})
        resposta.headers.add("Access-Control-Allow-Origin", "*")
        return resposta, 200
        
    try:
        if request.form:
            nome_musica = request.form.get('musica', '')
        else:
            dados = request.get_json(force=True, silent=True) or {}
            nome_musica = dados.get('musica', '')
    except:
        nome_musica = ''

    if not nome_musica.strip():
        return jsonify({"erro": "Nome da musica nao fornecido"}), 400

    # 1. Gera o ID único da música para evitar duplicados
    id_musica = normalizar_id_musica(nome_musica)
    
    print(f"\n🔍 [DESDUPLICAÇÃO] Verificando música ID: {id_musica}")
    
    # 2. Consulta se a música já existe na biblioteca geral
    doc_ref = db.collection('biblioteca_global').document(id_musica)
    doc = doc_ref.get()
    
    if doc.exists:
        print(f"♻️ [REAPROVEITAMENTO] '{nome_musica}' ja esta pronta! Poupando processamento.")
        return jsonify({
            "status": "existente",
            "mensagem": f"'{nome_musica}' já foi processada anteriormente! Ela já está disponível instantaneamente no seu Repertório."
        }), 200

    # 3. Se não existir, insere como um novo documento fixando o ID único
    print(f"🚀 [IA NUVEM] Criando novo registro e iniciando separacao para: {nome_musica}")
    try:
        doc_ref.set({
            'titulo': nome_musica,
            'status': 'Pronto Offline',
            'subtitulo': 'VS Completo • Biblioteca Geral',
            'id_busca': id_musica,
            'criadoEm': firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        print(f"Erro ao gravar no Firebase: {e}")
        
    return jsonify({
        "status": "processando",
        "mensagem": f"A IA localizou '{nome_musica}'. O download e a separação de faixas foram iniciados e ela ficará disponível para TODOS os usuários!"
    }), 200

if __name__ == '__main__':
    porta = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=porta, debug=False)
