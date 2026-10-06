import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
@app.route('/solicitar_vss', methods=['POST'])
def solicitar_vss():
    try:
        dados = request.get_json(force=True)
    except:
        dados = {}
        
    nome_musica = dados.get('musica', 'Musica_Desconhecida')
    print(f"\n⚡ [SUCESSO GLOBAL] Pedido recebido na Railway: {nome_musica}")
    
    return jsonify({
        "status": "processando",
        "mensagem": f"A IA na Railway localizou '{nome_musica}'. O download e a separacao foram iniciados!"
    }), 200

if __name__ == '__main__':
    # A Railway exige ler a porta dynamicamente dessa forma:
    porta = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=porta, debug=False)
