# Automação Arduino por Comando de Voz (Vosk + Ollama)

Sistema de automação residencial/protótipo controlado por voz em português. O áudio capturado pelo microfone é transcrito offline com **Vosk**, interpretado por um modelo de linguagem local via **Ollama** (`qwen3.5:4b`) e convertido em comandos enviados via porta serial para um **Arduino**.

## Estrutura do Projeto

- `reconhecimento.py` — Script Python que captura áudio, transcreve com Vosk, extrai comandos com Ollama e envia pela porta serial.
- `arduino_ia.ino` — Firmware do Arduino que controla os atuadores e o modo automático com sensor ultrassônico.
- `model/` — Modelo de reconhecimento de voz Vosk em português.
- `requirements.txt` — Dependências Python do projeto.

## Ligações no Arduino (`arduino_ia.ino`)

| Componente | Pino |
| --- | --- |
| Servo (portão/porta) | `2` |
| LED | `3` |
| Ultrassônico `ECHO` | `4` |
| Ultrassônico `TRIG` | `5` |
| Ventilador / Cooler (`FAN`) | `8` |

## Comandos Suportados

- `LED:1` / `LED:0` — Liga ou desliga o LED
- `FAN:1` / `FAN:0` — Liga ou desliga o ventilador
- `SERVO:90` / `SERVO:0` — Abre (90°) ou fecha (0°) o servo
- `DIST:<numero>` — Altera a distância limite em cm do modo automático (padrão: `30`)
- `AUTO:1` / `AUTO:0` — Ativa ou desativa o modo automático via sensor ultrassônico

## Como Executar

1. **Arduino**: Abra `arduino_ia.ino` na Arduino IDE e faça o upload para a placa (utiliza a biblioteca padrão `Servo.h`).
2. **Ollama**: Instale o [Ollama](https://ollama.com/) e baixe o modelo configurado em `reconhecimento.py`:
   ```bash
   ollama pull qwen3.5:4b
   ```
3. **Dependências Python**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Porta Serial**: Confira em `reconhecimento.py` se `PORTA_SERIAL` (atualmente `'COM3'`) corresponde à porta do seu Arduino.
5. **Executar**:
   ```bash
   python reconhecimento.py
   ```
