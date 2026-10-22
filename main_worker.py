import json
import sys

from gerador_assinatura_propria import (
    definir_url_original,
    preparar_ambiente,
    processar_com_status,
    reservar,
)


def processar_musica(musica_id, url_mp3=None):
    """Processa uma música específica da fila e devolve o resultado."""
    if url_mp3:
        definir_url_original(musica_id, url_mp3)
    musica = reservar(musica_id)
    if musica is None:
        return {"status": "indisponivel", "musica_id": musica_id}
    return processar_com_status(musica)


def iniciar_servico_trabalhador():
    if len(sys.argv) < 2:
        print("Uso: python main_worker.py <musica_id> [url_mp3]")
        sys.exit(1)

    musica_id = sys.argv[1]
    url_mp3 = sys.argv[2] if len(sys.argv) > 2 else None
    try:
        preparar_ambiente()
        resultado = processar_musica(musica_id, url_mp3)
    except Exception as falha:
        resultado = {"status": "erro_fatal", "detalhes": str(falha)}
    print(json.dumps(resultado))
    if resultado["status"] in ("failed", "erro_fatal"):
        sys.exit(1)


if __name__ == "__main__":
    iniciar_servico_trabalhador()
