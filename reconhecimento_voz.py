import argparse
import json
import queue
import re
import sys
import time
import unicodedata

import serial
import sounddevice as sd
from vosk import KaldiRecognizer, Model

PORTA_SERIAL = "COM3"
BAUD_RATE = 9600
CAMINHO_MODELO_VOSK = "model"
SAMPLE_RATE = 16000

VERBOS_LIGAR = {
    "ligar",
    "liga",
    "ligue",
    "acender",
    "acende",
    "acenda",
    "ativar",
    "ativa",
    "ative",
    "habilitar",
    "habilita",
    "habilite",
    "iniciar",
    "inicia",
    "inicie",
}

VERBOS_DESLIGAR = {
    "desligar",
    "desliga",
    "desligue",
    "apagar",
    "apaga",
    "apague",
    "desativar",
    "desativa",
    "desative",
    "desabilitar",
    "desabilita",
    "desabilite",
    "parar",
    "pare",
    "encerrar",
    "encerra",
    "encerre",
}

VERBOS_ABRIR = {
    "abrir",
    "abre",
    "abra",
    "levantar",
    "levanta",
    "levante",
    "subir",
    "sobe",
    "suba",
}

VERBOS_FECHAR = {
    "fechar",
    "fecha",
    "feche",
    "baixar",
    "baixa",
    "baixe",
    "abaixar",
    "abaixa",
    "abaixe",
    "descer",
    "desce",
    "desca",
}

ALVOS_LED = {"led", "leds", "lede", "ledi", "luz", "luzes", "lampada", "lampadas", "iluminacao"}
ALVOS_FAN = {"ventilador", "ventiladores", "cooler", "culer", "ventoinha"}
ALVOS_SERVO = {"servo", "portao", "porta", "motor"}
ALVOS_AUTO = {"automatico", "automatica", "ultrassonico", "ultrassom", "sensor"}
ALVOS_MANUAL = {"manual"}

SEPARADOR_CLAUSULAS = re.compile(r"(?:\s*[,;.]\s*|\s+(?:e|depois|entao|tambem)\s+)")
REGEX_NEGACAO = re.compile(
    r"\bnao\s+(?:"
    + "|".join(VERBOS_LIGAR | VERBOS_DESLIGAR | VERBOS_ABRIR | VERBOS_FECHAR)
    + r")\b"
)


def normalizar_texto(texto: str) -> str:
    sem_acentos = "".join(
        c
        for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )
    limpo = re.sub(r"([,;.\n])", r" \1 ", sem_acentos.lower())
    return re.sub(r"\s+", " ", limpo).strip()


def _detectar_acao(palavras: set[str]) -> str | None:
    if palavras & VERBOS_DESLIGAR:
        return "OFF"
    if palavras & VERBOS_LIGAR:
        return "ON"
    if palavras & VERBOS_FECHAR:
        return "CLOSE"
    if palavras & VERBOS_ABRIR:
        return "OPEN"
    return None


def interpretar_comando(texto: str) -> list[str]:
    normalizado = normalizar_texto(texto)
    if not normalizado:
        return []

    clausulas = [c.strip() for c in SEPARADOR_CLAUSULAS.split(normalizado) if c.strip()]
    comandos: list[str] = []
    ultima_acao: str | None = None

    for clausula in clausulas:
        palavras = set(clausula.split())

        acao_explicita = _detectar_acao(palavras)
        if acao_explicita is not None:
            ultima_acao = acao_explicita
            acao = acao_explicita
        else:
            acao = ultima_acao

        if REGEX_NEGACAO.search(clausula):
            continue

        if palavras & ALVOS_SERVO:
            if acao in {"OPEN", "ON"}:
                comandos.append("SERVO:90")
            elif acao in {"CLOSE", "OFF"}:
                comandos.append("SERVO:0")

        if palavras & ALVOS_MANUAL:
            comandos.append("AUTO:0")
        elif palavras & ALVOS_AUTO:
            if acao == "OFF":
                comandos.append("AUTO:0")
            elif acao == "ON" or "modo automatico" in clausula:
                comandos.append("AUTO:1")

        if palavras & ALVOS_LED:
            if acao == "ON":
                comandos.append("LED:1")
            elif acao == "OFF":
                comandos.append("LED:0")

        if palavras & ALVOS_FAN:
            if acao == "ON":
                comandos.append("FAN:1")
            elif acao == "OFF":
                comandos.append("FAN:0")

    return list(dict.fromkeys(comandos))


def enviar_arduino(arduino: serial.Serial, comando: str) -> None:
    arduino.write(f"{comando}\n".encode("utf-8"))
    time.sleep(0.05)
    while arduino.in_waiting > 0:
        resposta = arduino.readline().decode("utf-8", errors="ignore").strip()
        if resposta:
            print(f"[ARDUINO] {resposta}")


def executar_voz(porta: str = PORTA_SERIAL, simular: bool = False) -> None:
    arduino: serial.Serial | None = None
    if not simular:
        try:
            arduino = serial.Serial(porta, BAUD_RATE, timeout=1)
            time.sleep(2)
            print(f"[SERIAL] Conectado ao Arduino em {porta}")
        except Exception as e:
            print(f"[ERRO SERIAL] Falha ao abrir {porta}: {e}")
            sys.exit(1)
    else:
        print("[MODO SIMULAÇÃO] Serial desativada; comandos serão apenas exibidos.")

    try:
        print("[VOSK] Carregando modelo local de reconhecimento de voz...")
        model = Model(CAMINHO_MODELO_VOSK)
        rec = KaldiRecognizer(model, SAMPLE_RATE)
    except Exception as e:
        print(f"[ERRO VOSK] Verifique se a pasta '{CAMINHO_MODELO_VOSK}' existe: {e}")
        if arduino is not None:
            arduino.close()
        sys.exit(1)

    audio_queue: queue.Queue[bytes] = queue.Queue()

    def callback_audio(indata, frames, time_info, status):
        if status:
            print(f"[AUDIO AVISO] {status}", file=sys.stderr)
        audio_queue.put(bytes(indata))

    try:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=callback_audio,
        ):
            print("\n=== SISTEMA PRONTO (SEM IA) ===")
            print("Fale próximo ao microfone (Ctrl+C para encerrar)...")

            while True:
                dado_audio = audio_queue.get()
                if rec.AcceptWaveform(dado_audio):
                    resultado = json.loads(rec.Result())
                    texto_falado = resultado.get("text", "").strip()

                    if texto_falado:
                        print(f'\n[VOZ RECONHECIDA]: "{texto_falado}"')
                        comandos = interpretar_comando(texto_falado)
                        print(f"[COMANDOS]: {comandos if comandos else 'NONE'}")

                        if comandos:
                            for cmd in comandos:
                                if arduino is not None:
                                    enviar_arduino(arduino, cmd)
                                else:
                                    print(f"[SIMULAÇÃO SERIAL] -> {cmd}")
                        else:
                            print("[IGNORADO] Comando não mapeado.")
    except KeyboardInterrupt:
        print("\n[ENCERRANDO] Fechando conexões...")
    finally:
        if arduino is not None and arduino.is_open:
            arduino.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Controle do Arduino por comando de voz com Vosk (sem IA)."
    )
    parser.add_argument(
        "--porta",
        default=PORTA_SERIAL,
        help=f"Porta serial do Arduino (padrão: {PORTA_SERIAL})",
    )
    parser.add_argument(
        "--simular",
        action="store_true",
        help="Executa sem conectar à porta serial (apenas exibe os comandos).",
    )
    args = parser.parse_args()
    executar_voz(porta=args.porta, simular=args.simular)


if __name__ == "__main__":
    main()
