#include <Servo.h>

const int PIN_SERVO = 2;
const int PIN_LED   = 3;
const int PIN_ECHO  = 4;
const int PIN_TRIG  = 5;
const int PIN_FAN   = 8;
//const int PIN_TEMP  = A3;

int  distAbrir = 30;      // cm (alterável via DIST:<numero>)
bool modoAuto  = false;   // false = controlado por voz; true = sensor ultrassônico

Servo servo;

long lerDistanciaCm() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  long duracao = pulseIn(PIN_ECHO, HIGH, 30000); // timeout 30 ms
  if (duracao == 0) return 999;                  // sem leitura
  return duracao * 0.0343 / 2;
}

void processarComando(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  if (cmd == "LED:1") {
    modoAuto = false;
    digitalWrite(PIN_LED, HIGH);
    Serial.println("OK: LED ligado");
  } else if (cmd == "LED:0") {
    modoAuto = false;
    digitalWrite(PIN_LED, LOW);
    Serial.println("OK: LED desligado");
  } else if (cmd == "FAN:1") {
    digitalWrite(PIN_FAN, HIGH);
    Serial.println("OK: Ventilador ligado");
  } else if (cmd == "FAN:0") {
    digitalWrite(PIN_FAN, LOW);
    Serial.println("OK: Ventilador desligado");
  } else if (cmd.startsWith("SERVO:")) {
    modoAuto = false;
    int angulo = constrain(cmd.substring(6).toInt(), 0, 180);
    servo.write(angulo);
    Serial.print("OK: Servo em ");
    Serial.println(angulo);
  } else if (cmd.startsWith("DIST:")) {
    int novaDist = cmd.substring(5).toInt();
    if (novaDist > 0) {
      distAbrir = novaDist;
      Serial.print("OK: Distancia limite = ");
      Serial.println(distAbrir);
    }
  } else if (cmd == "AUTO:1") {
    modoAuto = true;
    Serial.println("OK: Modo automatico ativado");
  } else if (cmd == "AUTO:0") {
    modoAuto = false;
    Serial.println("OK: Modo automatico desativado");
  } else {
    Serial.print("ERRO: Comando desconhecido -> ");
    Serial.println(cmd);
  }
}

void setup() {
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_FAN, OUTPUT);
  digitalWrite(PIN_LED, LOW);
  digitalWrite(PIN_FAN, LOW);
  servo.attach(PIN_SERVO);
  servo.write(0);
  Serial.begin(9600);
}

void loop() {
  if (Serial.available() > 0) {
    String comando = Serial.readStringUntil('\n');
    processarComando(comando);
  }

  if (modoAuto) {
    long dist = lerDistanciaCm();
    if (dist > 0 && dist <= distAbrir) {
      servo.write(90);
      digitalWrite(PIN_LED, HIGH);
    } else {
      servo.write(0);
      digitalWrite(PIN_LED, LOW);
    }
  }

  delay(50);
}
