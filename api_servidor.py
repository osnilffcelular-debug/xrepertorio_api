import hmac
import os
import subprocess
import sys
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="XRepertorio Worker API")

CAMINHO_MAIN_WORKER = Path(__file__).resolve().parent / "main_worker.py"


class PayloadMusica(BaseModel):
    musica_id: str
    url_mp3: str | None = None


def executar_script_assinatura(musica_id: str, url_mp3: str | None):
    comando = [sys.executable, str(CAMINHO_MAIN_WORKER), musica_id]
    if url_mp3:
        comando.append(url_mp3)
    try:
        subprocess.run(comando, check=True, cwd=str(CAMINHO_MAIN_WORKER.parent))
    except subprocess.CalledProcessError as erro:
        print(f"Erro ao executar o worker para a musica {musica_id}: {erro}")


def validar_token(token: str | None, authorization: str | None = None):
    esperado = os.environ.get("WORKER_API_TOKEN")
    if not esperado:
        raise HTTPException(status_code=503, detail="WORKER_API_TOKEN não configurado.")
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token or not hmac.compare_digest(token, esperado):
        raise HTTPException(status_code=401, detail="Token inválido.")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/processar")
async def processar_nova_musica(
    dados: PayloadMusica,
    tarefas: BackgroundTasks,
    x_worker_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    validar_token(x_worker_token, authorization)
    if not dados.musica_id.strip():
        raise HTTPException(status_code=400, detail="Parametros insuficientes.")

    # Responde de imediato e processa em segundo plano
    tarefas.add_task(executar_script_assinatura, dados.musica_id, dados.url_mp3)
    return {"status": "processamento_iniciado", "musica_id": dados.musica_id}
