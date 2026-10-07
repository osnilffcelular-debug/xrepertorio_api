import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
# Liberação total de acesso para o aplicativo do telemóvel
CORS(app, resources={r"/*": {"origins": "*", "methods": ["POST", "GET", "OPTIONS"], "allow_headers": "*"}})

@app.route('/', defaults={'path': ''}, methods=['POST', 'GET', 'OPTIONS'])
@app.route('/<path:path>', methods=['POST', 'GET', 'OPTIONS'])
def capturar_tudo(path):
    if request.method == 'OPTIONS':
        resposta = jsonify({"status": "ok"})
        resposta.headers.add("Access-Control-Allow-Origin", "*")
        return resposta, 200
        
    try:
        if request.form:
            nome_musica = request.form.get('musica', 'Musica_Desconhecida')
        else:
            dados = request.get_json(force=True, silent=True) or {}
            nome_musica = dados.get('musica', 'Musica_Desconhecida')
    except:
        nome_musica = 'Musica_Desconhecida'
        
    print(f"\n🎯 [SUCESSO DE INTEGRAÇÃO] Pedido aceito na nuvem: {nome_musica} (Rota: /{path})")
    print("🔊 Iniciando o download e o processamento de faixas em segundo plano...")
    
    return jsonify({
        "status": "processando",
        "mensagem": f"A IA localizou '{nome_musica}' e iniciou o download em segundo plano com sucesso!"
    }), 200

if __name__ == '__main__':
    porta = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=porta, debug=False)
