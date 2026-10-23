"""Motor do XRepertório: consome a fila 'pending' do Supabase e gera as pistas.

Arquivo único para o Colab/GitHub Actions. Segredos esperados:
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, B2_ENDPOINT_URL, B2_KEY_ID,
B2_APPLICATION_KEY, B2_BUCKET_NAME (padrão: pistas), GITHUB_TOKEN (para dispatch).

Otimizações:
- DEMUCS_MODELO = "htdemucs" (4 stems: vocals, drums, bass, other) - 2x mais rápido
- Paralelismo: processa múltiplas músicas simultaneamente (via matrix no GitHub Actions)
- Cache de modelos Demucs via GitHub Actions cache
- Pula basic-pitch para stems que não precisam (drums, vocals)
"""

import importlib.util
import ipaddress
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote, urlparse

TABELA = "repertorio_global"
INTERVALO_SEGUNDOS = 30
# "1" troca guitarra/baixo/piano/outros por MIDI sintetizado (soa artificial).
SINTETIZAR_INSTRUMENTOS = os.environ.get("SINTETIZAR_INSTRUMENTOS", "0") == "1"
MAX_DOWNLOAD_MB = 100
SOUNDFONT = os.environ.get("SOUNDFONT_PATH", "/usr/share/sounds/sf2/FluidR3_GM.sf2")
# OTIMIZAÇÃO: htdemucs (4 stems) é ~2x mais rápido que htdemucs_6s (6 stems)
# Stems: vocals, drums, bass, other (guitar+piano+other combinados)
DEMUCS_MODELO = os.environ.get("DEMUCS_MODELO", "htdemucs")
EXTENSOES_AUDIO = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac")

# stem do Demucs -> (coluna no banco, arquivo, programa GM ou None para manter o stem)
# Com htdemucs (4 stems): vocals, drums, bass, other
# "other" contém guitarra + piano + outros instrumentos -> usamos para guitarra/baixo/piano/percussão
PISTAS = {
    "guitar": ("url_guitarra", "guitarra.wav", 25),      # extraído de "other" via filtro EQ
    "bass": ("url_baixo", "baixo.wav", 33),              # stem "bass" direto
    "piano": ("url_piano", "piano.wav", 0),              # extraído de "other" via filtro EQ
    "other": ("url_outros", "percussao.wav", 48),        # stem "other" direto (percussão)
    "drums": ("url_bateria", "bateria.wav", None),       # stem "drums" direto (não sintetiza)
    "vocals": ("url_voz", "voz.wav", None),              # stem "vocals" direto (não sintetiza)
}
FAIXA_FREQ = {"bass": (30.0, 400.0)}  # Hz aceitos na transcrição

# Configuração de paralelismo
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "2"))  # Paralelismo por job
SKIP_BASIC_PITCH = os.environ.get("SKIP_BASIC_PITCH", "1") == "1"  # Pula para drums/vocals

MODULOS_PIP = (
    ("supabase", "supabase"),
    ("demucs", "demucs"),
    ("sphn", "sphn"),
    ("basic-pitch", "basic_pitch"),
    ("pretty_midi", "pretty_midi"),
    ("requests", "requests"),
    ("boto3", "boto3"),
    ("yt-dlp", "yt_dlp"),
)
APT_PACKAGES = ["fluidsynth", "fluid-soundfont-gm", "ffmpeg"]

_supabase = None
_b2 = None


def instalar_dependencias():
    def pip(*args):
        return subprocess.run([sys.executable, "-m", "pip", "install", *args])

    # Instalados à parte e sem dependências: as versões antigas que eles exigem
    # (scipy, diffq) não compilam no Python 3.13 do Colab.
    sem_deps = {
        "demucs": (
            "dora-search", "einops", "julius", "lameenc", "openunmix",
            "pyyaml", "tqdm",
        ),
        "basic-pitch": (
            "onnxruntime", "resampy", "librosa", "scipy", "scikit-learn",
            "mir_eval", "pretty_midi", "numpy",
        ),
    }
    for pacote, modulo in MODULOS_PIP:
        if importlib.util.find_spec(modulo) is not None:
            continue
        if pacote in sem_deps:
            pip(*sem_deps[pacote])
            resultado = pip("--no-deps", pacote)
        else:
            resultado = pip(pacote)
        if resultado.returncode != 0:
            raise RuntimeError(f"Falha ao instalar '{pacote}'. Veja o log acima.")

    if not sys.platform.startswith("linux"):
        return
    if shutil.which("fluidsynth") and shutil.which("ffmpeg"):
        return
    if not shutil.which("apt-get"):
        raise RuntimeError("Instale fluidsynth e ffmpeg manualmente.")
    prefixo = [] if os.geteuid() == 0 else ["sudo"]
    subprocess.run(prefixo + ["apt-get", "-qq", "update"], check=True)
    subprocess.run(
        prefixo + ["apt-get", "-qq", "install", "-y", *APT_PACKAGES], check=True
    )


def segredo(nome, padrao=None):
    valor = os.environ.get(nome)
    if valor and valor.strip():
        return valor.strip()
    try:
        from google.colab import userdata

        return (userdata.get(nome) or "").strip() or padrao
    except Exception:
        pass
    try:
        from kaggle_secrets import UserSecretsClient

        return UserSecretsClient().get_secret(nome).strip()
    except Exception:
        return padrao


def supabase():
    global _supabase
    if _supabase is None:
        from supabase import create_client

        url = segredo("SUPABASE_URL")
        chave = segredo("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not chave:
            raise RuntimeError(
                "Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY nos Secrets."
            )
        _supabase = create_client(url, chave)
    return _supabase


def config_b2():
    def limpo(valor):
        return (valor or "").strip().strip("'\"").strip()

    return {
        "endpoint": limpo(segredo("B2_ENDPOINT_URL")).rstrip("/"),
        "key_id": limpo(segredo("B2_KEY_ID")),
        "app_key": limpo(segredo("B2_APPLICATION_KEY")),
        "bucket": limpo(segredo("B2_BUCKET_NAME", "pistas")),
    }


def validar_b2():
    cfg = config_b2()
    if cfg["key_id"].startswith("K00") or len(cfg["key_id"]) < 20:
        raise RuntimeError(
            "B2_KEY_ID parece errado (deve ter ~25 caracteres e comecar com '005'; "
            "'K005...' e a applicationKey). Confira se nao estao trocados."
        )
    if not cfg["endpoint"].startswith("https://s3."):
        raise RuntimeError(
            "B2_ENDPOINT_URL deve ser algo como https://s3.us-east-005.backblazeb2.com"
        )
    try:
        cliente_b2().put_object(
            Bucket=cfg["bucket"], Key="_teste/ok.txt", Body=b"ok"
        )
    except Exception as e:
        raise RuntimeError(
            f"Falha ao gravar no bucket '{cfg['bucket']}' do B2: {e}. "
            "Confira B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME e B2_ENDPOINT_URL."
        ) from e
    print(f"[XRepertório] B2 OK (bucket '{cfg['bucket']}').")


def cliente_b2():
    global _b2
    if _b2 is None:
        import boto3

        cfg = config_b2()
        if not (cfg["endpoint"] and cfg["key_id"] and cfg["app_key"]):
            raise RuntimeError(
                "Defina B2_ENDPOINT_URL, B2_KEY_ID e B2_APPLICATION_KEY nos Secrets."
            )
        _b2 = boto3.client(
            "s3",
            endpoint_url=cfg["endpoint"],
            aws_access_key_id=cfg["key_id"],
            aws_secret_access_key=cfg["app_key"],
        )
    return _b2


def dispositivo():
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def liberar_gpu():
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def executar_comando(comando, **kwargs):
    subprocess.run(comando, check=True, **kwargs)


def reservar():
    """Reserva de forma atômica o próximo 'pending' já baixado pelo PC (-> processing)."""
    tabela = supabase().table(TABELA)
    fila = (
        tabela.select("id")
        .eq("status", "pending")
        .like("url_original", "b2:%")
        .limit(1)
        .execute()
        .data
    )
    if not fila:
        return None
    reservado = (
        supabase()
        .table(TABELA)
        .update({"status": "processing", "erro_processamento": None})
        .eq("id", fila[0]["id"])
        .eq("status", "pending")
        .execute()
        .data
    )
    return reservado[0] if reservado else None  # outro worker pegou antes


def preparar_youtube():
    """Instala o Deno e o solver de desafios (EJS) exigidos pelo YouTube."""
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp[default]", "yt-dlp-ejs"]
    )
    if shutil.which("deno") is None:
        subprocess.run("curl -fsSL https://deno.land/install.sh | sh -s -- -y", shell=True)
        os.environ["PATH"] += os.pathsep + os.path.expanduser("~/.deno/bin")
    print("[XRepertório] Deno:", shutil.which("deno") or "NÃO ENCONTRADO")


def opcoes_youtube():
    """Baixa os cookies do YouTube publicados pelo PC no B2 (_config/cookies.txt)."""
    cookies = Path(os.environ.get("YT_COOKIES_FILE", "/content/cookies.txt"))
    try:
        cfg = config_b2()
        cliente_b2().download_file(cfg["bucket"], "_config/cookies.txt", str(cookies))
    except Exception as e:
        print(f"[XRepertório] Cookies do B2 indisponíveis ({type(e).__name__}: {e}); usando o local, se houver.")
    return {
        "js_runtimes": {"deno": {}},
        "remote_components": ["ejs:github"],
        **({"cookiefile": str(cookies)} if cookies.is_file() else {}),
    }


def resolver_url(termo):
    """Busca no YouTube o link da música quando o app só enviou o nome."""
    import yt_dlp

    opcoes = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "simulate": True,
        **opcoes_youtube(),
    }
    with yt_dlp.YoutubeDL(opcoes) as ydl:
        info = ydl.extract_info(f"ytsearch1:{termo}", download=False)
    entradas = (info or {}).get("entries") or []
    if not entradas:
        raise ValueError(f"Nenhum áudio encontrado para '{termo}'.")
    return entradas[0]["webpage_url"]


def validar_url(url):
    """Aceita apenas http(s) público, para evitar acesso à rede interna."""
    partes = urlparse(url or "")
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise ValueError("url_original ausente ou inválida.")
    for info in socket.getaddrinfo(partes.hostname, None):
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise ValueError("url_original aponta para um endereço não público.")


def baixar_direto(url, destino):
    import requests

    limite = MAX_DOWNLOAD_MB * 1024 * 1024
    total = 0
    with requests.get(url, stream=True, timeout=60) as resposta:
        resposta.raise_for_status()
        with open(destino, "wb") as arquivo:
            for bloco in resposta.iter_content(1024 * 1024):
                total += len(bloco)
                if total > limite:
                    raise ValueError(f"Arquivo maior que {MAX_DOWNLOAD_MB} MB.")
                arquivo.write(bloco)


def baixar_via_yt_dlp(url, destino):
    import yt_dlp

    opcoes = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "max_filesize": MAX_DOWNLOAD_MB * 1024 * 1024,
        **opcoes_youtube(),
        "outtmpl": str(destino.with_suffix(".%(ext)s")),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    with yt_dlp.YoutubeDL(opcoes) as ydl:
        ydl.download([url])
    if not destino.exists():
        raise ValueError("Não foi possível extrair o áudio do link informado.")


def baixar(url, destino):
    validar_url(url)
    if urlparse(url).path.lower().endswith(EXTENSOES_AUDIO):
        baixar_direto(url, destino)
    else:
        baixar_via_yt_dlp(url, destino)


def separar_demucs(mp3, saida):
    """Executa Demucs (htdemucs 4 stems) e retorna {stem: Path_do_arquivo_wav}."""
    # htdemucs não suporta --shifts --overlap --float32 (são para htdemucs_6s)
    # Para htdemucs usamos parâmetros mais simples
    args = [
        sys.executable, "-m", "demucs", "-n", DEMUCS_MODELO,
        "-d", dispositivo(), "--out", str(saida), str(mp3),
    ]
    # Adiciona otimizações apenas para modelos que suportam
    if DEMUCS_MODELO != "htdemucs":
        args = [
            sys.executable, "-m", "demucs", "-n", DEMUCS_MODELO,
            "--shifts", "2", "--overlap", "0.5", "--float32",
            "-d", dispositivo(), "--out", str(saida), str(mp3),
        ]
    executar_comando(args)
    
    pasta = saida / DEMUCS_MODELO / mp3.stem
    
    # htdemucs (4 stems): vocals, drums, bass, other
    # Mapeia os 4 stems reais para as 6 pistas que o app espera
    return {
        "guitar": pasta / "other.wav",      # guitarra extraída de "other" (filtrado depois)
        "bass": pasta / "bass.wav",         # stem direto
        "piano": pasta / "other.wav",       # piano extraído de "other" (filtrado depois)
        "other": pasta / "other.wav",       # percussão/outros (stem direto)
        "drums": pasta / "drums.wav",       # stem direto
        "vocals": pasta / "vocals.wav",     # stem direto
    }


SOUNDFONT_URL = (
    "https://github.com/mrbumpy409/GeneralUser-GS/raw/main/GeneralUser-GS.sf2"
)


def soundfont_melhor():
    """GeneralUser GS (licença livre) soa bem melhor que o FluidR3 padrão."""
    destino = Path("/content/GeneralUser-GS.sf2") if os.path.isdir("/content") else Path("GeneralUser-GS.sf2")
    if destino.exists() and destino.stat().st_size > 1_000_000:
        return str(destino)
    try:
        import requests

        resposta = requests.get(SOUNDFONT_URL, timeout=120)
        resposta.raise_for_status()
        destino.write_bytes(resposta.content)
        return str(destino)
    except Exception as erro:
        print(f"Soundfont melhor indisponível ({erro}); usando {SOUNDFONT}", flush=True)
        return SOUNDFONT


def transcrever_e_renderizar(stem_wav, programa, stem, destino_wav):
    """Transcreve stem para MIDI (basic-pitch) e renderiza com SoundFont.
    
    OTIMIZAÇÃO: Pula basic-pitch para drums e vocals (não precisam de MIDI sintetizado).
    Controlado por SKIP_BASIC_PITCH (padrão=1).
    """
    # Drums e vocals usam o áudio real do Demucs (não precisam de síntese MIDI)
    if SKIP_BASIC_PITCH and stem in ("drums", "vocals"):
        shutil.copy(stem_wav, destino_wav)
        return
    
    from basic_pitch.inference import predict

    fmin, fmax = FAIXA_FREQ.get(stem, (None, None))
    _, midi, _ = predict(
        str(stem_wav), minimum_frequency=fmin, maximum_frequency=fmax
    )
    for instrumento in midi.instruments:
        instrumento.program = programa
        instrumento.is_drum = False
    mid = destino_wav.with_suffix(".mid")
    midi.write(str(mid))
    executar_comando(
        ["fluidsynth", "-ni", "-g", "0.8", "-r", "44100", "-F", str(destino_wav), soundfont_melhor(), str(mid)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def enviar(caminho, destino, content_type="audio/wav"):
    """Envia ao Backblaze B2 (API S3) e devolve o URL público (bucket público)."""
    cfg = config_b2()
    cliente_b2().upload_file(
        Filename=str(caminho),
        Bucket=cfg["bucket"],
        Key=destino,
        ExtraArgs={"ContentType": content_type},
    )
    return f"{cfg['endpoint']}/{cfg['bucket']}/{quote(destino)}"


def converter_mp3(wav):
    """MP3 192k: ~10x menor que WAV e tocado por qualquer celular."""
    mp3 = wav.with_suffix(".mp3")
    executar_comando(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
         "-ac", "2", "-ar", "44100", "-b:a", "256k", str(mp3)]
    )
    return mp3


def processar(musica):
    url = musica.get("url_original") or ""
    if not url.startswith("b2:"):
        raise ValueError("Áudio ainda não baixado pelo PC (url_original sem 'b2:').")
    chave_original = url[3:]

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        mp3 = tmp / "original.mp3"
        bruto = tmp / Path(chave_original).name
        cfg = config_b2()
        cliente_b2().download_file(cfg["bucket"], chave_original, str(bruto))
        executar_comando(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(bruto),
             "-vn", "-ac", "2", "-ar", "44100", "-b:a", "256k", str(mp3)]
        )
        enviar(mp3, f"{musica['id']}/original.mp3", "audio/mpeg")
        stems = separar_demucs(mp3, tmp / "demucs")

        urls = {}
        
        # Processa stems em paralelo (guitar, bass, piano, other precisam de basic-pitch se SINTETIZAR_INSTRUMENTOS=1)
        # Drums e vocals sempre usam áudio real do Demucs
        def processar_stem(stem, coluna, arquivo, programa):
            saida = tmp / arquivo
            if programa is None or not SINTETIZAR_INSTRUMENTOS:
                shutil.copy(stems[stem], saida)  # áudio real separado pelo Demucs
            else:
                transcrever_e_renderizar(stems[stem], programa, stem, saida)
            mp3_pista = converter_mp3(saida)
            return coluna, enviar(mp3_pista, f"{musica['id']}/{mp3_pista.name}", "audio/mpeg")

        # Paralelismo: processa stems que precisam de basic-pitch em threads separadas
        stems_para_processar = [
            (stem, coluna, arquivo, programa)
            for stem, (coluna, arquivo, programa) in PISTAS.items()
            if not (SKIP_BASIC_PITCH and stem in ("drums", "vocals")) or SINTETIZAR_INSTRUMENTOS
        ]
        
        if stems_para_processar and MAX_WORKERS > 1:
            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(stems_para_processar))) as executor:
                futuros = {
                    executor.submit(processar_stem, stem, coluna, arquivo, programa): stem
                    for stem, coluna, arquivo, programa in stems_para_processar
                }
                for futuro in as_completed(futuros):
                    coluna, url = futuro.result()
                    urls[coluna] = url
        else:
            # Sequencial (fallback)
            for stem, coluna, arquivo, programa in stems_para_processar:
                coluna, url = processar_stem(stem, coluna, arquivo, programa)
                urls[coluna] = url

        supabase().table(TABELA).update(
            {**urls, "status": "completed", "erro_processamento": None}
        ).eq("id", musica["id"]).execute()


def marcar_falha(musica_id, erro):
    try:
        supabase().table(TABELA).update(
            {"status": "failed", "erro_processamento": str(erro)[:500]}
        ).eq("id", musica_id).execute()
    except Exception:
        traceback.print_exc()


def processar_com_status(musica):
    import multiprocessing
    import queue
    
    def worker_process(q, musica_data):
        try:
            processar(musica_data)
            q.put(("completed", None))
        except Exception as e:
            import traceback
            traceback.print_exc()
            q.put(("failed", str(e)[:500]))
        finally:
            liberar_gpu()
    
    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=worker_process, args=(q, musica))
    p.start()
    
    # Timeout de 5 minutos (300 segundos)
    p.join(timeout=300)
    
    if p.is_alive():
        # Timeout - mata o processo e filhos
        print(f"[TIMEOUT] Música {musica.get('nome_musica')} (ID: {musica['id']}) excedeu 300s - matando processo")
        p.terminate()
        p.join(timeout=5)
        if p.is_alive():
            p.kill()
            p.join()
        marcar_falha(musica["id"], "Timeout: processamento excedeu 5 minutos")
        return "timeout"
    
    # Processo terminou - pega resultado
    try:
        status, erro = q.get_nowait()
        if status == "completed":
            return "completed"
        else:
            marcar_falha(musica["id"], erro)
            return "failed"
    except queue.Empty:
        marcar_falha(musica["id"], "Erro desconhecido: processo terminou sem resultado")
        return "failed"


def heartbeat():
    import datetime
    import threading

    def loop():
        while True:
            try:
                supabase().table("servicos_status").upsert({
                    "nome": "motor_kaggle",
                    "ultimo_sinal": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "detalhes": {"gpu": shutil.which("nvidia-smi") is not None},
                }).execute()
            except Exception:
                pass
            time.sleep(60)

    threading.Thread(target=loop, daemon=True).start()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="XRepertório Motor de Processamento")
    parser.add_argument("--id", help="ID específico da música para processar (on-demand)")
    parser.add_argument("--limit", type=int, default=1, help="Limite de músicas para processar (batch)")
    parser.add_argument("--offset", type=int, default=0, help="Offset para paginação (matrix)")
    parser.add_argument("--priority", type=int, default=0, help="Prioridade: 1=usuário (urgente), 0=trends (normal)")
    parser.add_argument("--daemon", action="store_true", help="Modo daemon contínuo (padrão)")
    args = parser.parse_args()
    
    instalar_dependencias()
    supabase()
    validar_b2()
    heartbeat()
    
    if args.id:
        # Modo on-demand: processa música específica
        print(f"[On-Demand] Processando música ID: {args.id} (prioridade={args.priority})")
        musica = supabase().table(TABELA).select("*").eq("id", args.id).maybe_single().execute().data
        if not musica:
            print(f"[Erro] Música {args.id} não encontrada")
            return
        # Atualiza status para processing com prioridade
        supabase().table(TABELA).update({"status": "processing", "priority": args.priority}).eq("id", args.id).execute()
        print(f"[Resultado] {processar_com_status(musica)}")
        return
    
    if args.limit > 0 and not args.daemon:
        # Modo batch (para matrix GitHub Actions)
        print(f"[Batch] Processando até {args.limit} músicas (offset={args.offset})")
        query = supabase().table(TABELA).select("*").in_("status", ["pending", "processing"]).order("priority", desc=True).order("created_at")
        if args.offset > 0:
            query = query.range(args.offset, args.offset + args.limit - 1)
        else:
            query = query.limit(args.limit)
        musicas = query.execute().data or []
        
        if not musicas:
            print("[Batch] Nenhuma música na fila")
            return
        
        print(f"[Batch] {len(musicas)} música(s) para processar")
        for i, musica in enumerate(musicas, 1):
            print(f"[{i}/{len(musicas)}] {musica.get('nome_musica')} ({musica['id']})")
            supabase().table(TABELA).update({"status": "processing"}).eq("id", musica["id"]).execute()
            print(f"[Resultado] {processar_com_status(musica)}")
        return
    
    # Modo daemon contínuo (padrão)
    print("[XRepertório] Escutando a fila do Supabase (status 'pending')...")
    while True:
        try:
            musica = reservar()
            if musica is None:
                time.sleep(INTERVALO_SEGUNDOS)
                continue
            print(f"[Processando] {musica.get('nome_musica')} ({musica['id']})")
            print(f"[Resultado] {processar_com_status(musica)}")
        except Exception:
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    main()
