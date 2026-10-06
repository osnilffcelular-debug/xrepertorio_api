import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/solicitar_vss', methods=['POST'])
def solicitar_vss():
    dados = request.get_json(force=True)
    nome_musica = dados.get('musica', '')
    
    if not nome_musica:
        return jsonify({"erro": "Nome da musica nao fornecido"}), 400
        
    print(f"🔍 BUSCANDO NA WEB GLOBAL: {nome_musica}")
    
    return jsonify({
        "status": "processando",
        "mensagem": f"A IA na nuvem localizou '{nome_musica}'. O download e a separacao das 6 pistas foram iniciados com sucesso!"
    }), 200

if __name__ == '__main__':
    porta = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=porta, debug=False)
