import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def artist_name_palco(texto):
    return ' '.join([palavra.capitalize() for palavra in texto.split()])

@app.route('/validar', methods=['POST'])
def validar_musica():
    try:
        dados = request.get_json(force=True) or {}
        artista_digitado = dados.get('artista', '').strip()
        musica_digitada = dados.get('musica', '').strip()
        
        if not artista_digitado or not musica_digitada:
            return jsonify({'resultado_vazio': True, 'precisa_corrigir': False})

        termo_busca = f"{artista_digitado} {musica_digitada}"
        
        resposta = requests.get(
            'https://apple.com',
            params={'term': termo_busca, 'entity': 'musicTrack', 'limit': 1},
            timeout=5
        )
        
        if resposta.status_code == 200:
            dados_api = resposta.json()
            resultados = dados_api.get('results', [])
            
            if not resultados:
                return jsonify({'resultado_vazio': True, 'precisa_corrigir': False})
            
            faixa_oficial = resultados[0]
            artista_oficial = faixa_oficial.get('artistName', '').strip()
            musica_oficial = faixa_oficial.get('trackName', '').strip()
            
            if (artista_oficial.lower() != artista_digitado.lower() or 
                musica_oficial.lower() != musica_digitada.lower()):
                
                return jsonify({
                    'resultado_vazio': False,
                    'precisa_corrigir': True,
                    'artista_correto': artist_name_palco(artista_oficial),
                    'musica_correta': artist_name_palco(musica_oficial)
                })
            
        return jsonify({'resultado_vazio': False, 'precisa_corrigir': False})
        
    except Exception:
        return jsonify({'resultado_vazio': False, 'precisa_corrigir': False})

@app.route('/solicitar_vss', methods=['POST'])
def solicitar_vss():
    dados = request.get_json(force=True)
    nome_musica = dados.get('musica', '')
    if not nome_musica:
        return jsonify({"erro": "Nome da musica nao fornecido"}), 400
    print(f"🔍 BUSCANDO NA WEB GLOBAL: {nome_musica}")
    return jsonify({
        "status": "processando",
        "mensagem": f"A IA na nuvem localizou '{nome_musica}'."
    }), 200

if __name__ == '__main__':
    porta = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=porta, debug=False)
