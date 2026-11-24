import json
import queue
import re
import sys
import time
import serial
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import ollama


PORTA_SERIAL = 'COM3'         
BAUD_RATE = 9600
CAMINHO_MODELO_VOSK = "model" 
MODELO_OLLAMA = "qwen3.5:4b"  
SAMPLE_RATE = 16000           

try:
    arduino = serial.Serial(PORTA_SERIAL, BAUD_RATE, timeout=1)
    time.sleep(2)  
    print(f"[SERIAL] Conectado ao Arduino em {PORTA_SERIAL}")
except Exception as e:
    print(f"[ERRO SERIAL] Falha ao abrir {PORTA_SERIAL}: {e}")
    sys.exit(1)

try:
    print("[VOSK] Carregando modelo local de linguagem...")
    model = Model(CAMINHO_MODELO_VOSK)
    rec = KaldiRecognizer(model, SAMPLE_RATE)
except Exception as e:
    print(f"[ERRO VOSK] Verifique se a pasta '{CAMINHO_MODELO_VOSK}' existe: {e}")
    sys.exit(1)

audio_queue = queue.Queue()

def callback_audio(indata, frames, time_info, status):
    if status:
        print(f"[AUDIO AVISO] {status}", file=sys.stderr)
    audio_queue.put(bytes(indata))

# 3. Prompt de extração para o LLM
PROMPT_SISTEMA = """Você é um compilador de comandos de voz para automação Arduino.
Converta o comando do usuário em linguagem natural EXCLUSIVAMENTE usando uma ou mais das tags a seguir (uma por linha, se houver mais de uma ordem na mesma frase):

- LED:1 (acender ou ligar a luz/lâmpada/led)
- LED:0 (apagar ou desligar a luz/lâmpada/led)
- FAN:1 (ligar o ventilador ou cooler)
- FAN:0 (desligar o ventilador ou cooler)
- SERVO:90 (abrir portão, porta ou servo)
- SERVO:0 (fechar portão, porta ou servo)
- DIST:<numero> (alterar distância limite em cm. Exemplo: "mude a distância para 40" -> DIST:40)
- AUTO:1 (ativar o sensor ultrassônico/modo automático)
- AUTO:0 (desativar modo automático)
- NONE (se a frase não contiver ordens para os atuadores)

REGRA ABSOLUTA: Retorne APENAS a(s) tag(s). Sem pontuações adicionais, sem markdown e sem explicações."""

PADRAO_TAGS = re.compile(r'\b(?:LED:[01]|FAN:[01]|SERVO:\d+|DIST:\d+|AUTO:[01])\b')

def interpretar_comando(texto: str) -> list[str]:
    try:
        resposta = ollama.chat(
            model=MODELO_OLLAMA,
            messages=[
                {'role': 'system', 'content': PROMPT_SISTEMA},
                {'role': 'user', 'content': texto}
            ],
            options={'temperature': 0.0}
        )
        conteudo = resposta['message']['content']
        # Remove blocos de raciocínio (<think>...</think>) caso o modelo gere
        conteudo = re.sub(r'<think>.*?</think>', '', conteudo, flags=re.DOTALL).strip()
        tags = PADRAO_TAGS.findall(conteudo.upper())
        return list(dict.fromkeys(tags))
    except Exception as e:
        print(f"[ERRO OLLAMA] Falha na inferência: {e}")
        return []

def enviar_arduino(comando: str):
    arduino.write(f"{comando}\n".encode('utf-8'))
    time.sleep(0.05)
    while arduino.in_waiting > 0:
        resposta = arduino.readline().decode('utf-8', errors='ignore').strip()
        if resposta:
            print(f"[ARDUINO] {resposta}")

# 4. Loop Principal de Captura e Processamento
def main():
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype='int16',
                           channels=1, callback=callback_audio):
        print("\n=== SISTEMA PRONTO ===")
        print("Fale próximo ao microfone (Ctrl+C para encerrar)...")

        while True:
            dado_audio = audio_queue.get()
            
            # Vosk processa blocos de áudio em busca de pausas/conclusão de sentenças
            if rec.AcceptWaveform(dado_audio):
                resultado = json.loads(rec.Result())
                texto_falado = resultado.get("text", "").strip()

                if texto_falado:
                    print(f"\n[VOZ RECONHECIDA]: \"{texto_falado}\"")
                    
                    comandos_ia = interpretar_comando(texto_falado)
                    print(f"[QWEN EXTRAIU]: {comandos_ia if comandos_ia else 'NONE'}")

                    if comandos_ia:
                        for cmd in comandos_ia:
                            enviar_arduino(cmd)
                    else:
                        print("[IGNORADO] Comando não mapeado.")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[ENCERRANDO] Fechando conexões...")
        arduino.close()