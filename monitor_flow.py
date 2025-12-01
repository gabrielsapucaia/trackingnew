#!/usr/bin/env python3
"""
============================================================
AuraTracking - Monitor de Fluxo de Dados em Tempo Real
============================================================
Monitora o fluxo de dados em tempo real:
- Celular → Mosquitto
- Mosquitto → TimescaleDB

Uso:
python3 monitor_flow.py [--duration SEGUNDOS] [--interval SEGUNDOS]

Exemplo:
python3 monitor_flow.py --duration 300 --interval 10

============================================================
"""

import argparse
import json
import psycopg2
import paho.mqtt.client as mqtt
import requests
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List

class FlowMonitor:
    """Monitor de fluxo de dados em tempo real."""

    def __init__(self, duration: int = 60, interval: int = 5):
        self.duration = duration
        self.interval = interval
        self.start_time = time.time()
        self.end_time = self.start_time + duration

        # Estatísticas
        self.stats = {
            "mqtt_messages": defaultdict(int),
            "db_inserts": defaultdict(int),
            "android_devices": set(),
            "db_devices": set(),
            "errors": []
        }

        # Configurações
        self.mqtt_config = {
            "host": "10.10.10.10",
            "port": 1883,
            "topic": "aura/tracking/#",
            "client_id": "flow_monitor"
        }

        self.db_config = {
            "host": "10.10.10.20",
            "port": 5432,
            "dbname": "auratracking",
            "user": "aura",
            "password": "aura2025"
        }

        # Conexões
        self.mqtt_client = None
        self.db_conn = None
        self.running = True

    def setup_signal_handlers(self):
        """Configura handlers de sinal."""
        def signal_handler(signum, frame):
            print(f"\n🛑 Recebido sinal {signum}, encerrando...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def connect_mqtt(self):
        """Conecta ao MQTT broker."""
        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                print("✅ Conectado ao MQTT broker")
                client.subscribe(self.mqtt_config["topic"], qos=1)
                print(f"📡 Subscribed to: {self.mqtt_config['topic']}")
            else:
                print(f"❌ Falha na conexão MQTT: {rc}")

        def on_message(client, userdata, msg):
            try:
                payload = json.loads(msg.payload.decode('utf-8'))
                device_id = payload.get('deviceId', 'unknown')
                topic_parts = msg.topic.split('/')

                if len(topic_parts) >= 3:
                    msg_type = topic_parts[-1]  # telemetry, events, status
                    self.stats["mqtt_messages"][f"{device_id}:{msg_type}"] += 1
                    self.stats["android_devices"].add(device_id)

                    print(f"📨 MQTT: {device_id} → {msg_type} ({len(msg.payload)} bytes)")

            except Exception as e:
                print(f"❌ Erro ao processar mensagem MQTT: {e}")

        self.mqtt_client = mqtt.Client(
            client_id=self.mqtt_config["client_id"],
            protocol=mqtt.MQTTv5
        )
        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_message = on_message

        try:
            self.mqtt_client.connect(
                self.mqtt_config["host"],
                self.mqtt_config["port"],
                keepalive=30
            )
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"❌ Falha ao conectar MQTT: {e}")
            self.stats["errors"].append(f"MQTT connection failed: {e}")

    def connect_database(self):
        """Conecta ao TimescaleDB."""
        try:
            self.db_conn = psycopg2.connect(**self.db_config)
            self.db_conn.autocommit = True
            print("✅ Conectado ao TimescaleDB")
        except Exception as e:
            print(f"❌ Falha ao conectar TimescaleDB: {e}")
            self.stats["errors"].append(f"Database connection failed: {e}")

    def check_database_ingestion(self):
        """Verifica ingestão no banco de dados."""
        if not self.db_conn:
            return

        try:
            with self.db_conn.cursor() as cur:
                # Verificar dispositivos ativos nos últimos 5 minutos
                cur.execute("""
                    SELECT device_id, COUNT(*) as count,
                           MAX(time) as last_time
                    FROM telemetry
                    WHERE time > NOW() - INTERVAL '5 minutes'
                    GROUP BY device_id
                """)

                for row in cur.fetchall():
                    device_id = row[0]
                    count = row[1]
                    last_time = row[2]

                    key = f"{device_id}:telemetry"
                    current_count = self.stats["db_inserts"][key]
                    new_count = count

                    if new_count > current_count:
                        ingested = new_count - current_count
                        self.stats["db_inserts"][key] = new_count
                        self.stats["db_devices"].add(device_id)

                        time_diff = (datetime.now(timezone.utc) - last_time).total_seconds()
                        status = "🟢 ATIVO" if time_diff < 60 else "🟡 INATIVO"

                        print(f"💾 DB: {device_id} → {ingested} novos pontos ({status})")

        except Exception as e:
            print(f"❌ Erro ao verificar banco: {e}")
            self.stats["errors"].append(f"Database check failed: {e}")

    def check_ingest_health(self):
        """Verifica health do Ingest Worker."""
        try:
            response = requests.get("http://10.10.10.30:8080/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                if health.get("status") == "healthy":
                    mqtt_conn = "✅" if health.get("mqtt_connected") else "❌"
                    db_conn = "✅" if health.get("db_connected") else "❌"
                    queue_size = health.get("offline_queue_size", 0)
                    messages_recv = health.get("messages_received", 0)

                    print(f"🔧 Ingest: MQTT:{mqtt_conn} DB:{db_conn} Queue:{queue_size} Recv:{messages_recv}")
                else:
                    print(f"⚠️ Ingest não saudável: {health.get('status')}")
            else:
                print(f"❌ Ingest HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ Erro no health check do Ingest: {e}")

    def print_summary(self):
        """Imprime resumo das estatísticas."""
        runtime = time.time() - self.start_time

        print("\n" + "="*60)
        print("📊 RESUMO DO MONITORAMENTO")
        print("="*60)
        print(".1f")
        print(f"Android devices detectados: {len(self.stats['android_devices'])}")
        print(f"Database devices ativos: {len(self.stats['db_devices'])}")
        print()

        if self.stats["mqtt_messages"]:
            print("📨 MENSAGENS MQTT RECEBIDAS:")
            for key, count in sorted(self.stats["mqtt_messages"].items()):
                device, msg_type = key.split(':', 1)
                print(f"  {device} ({msg_type}): {count}")
            print()

        if self.stats["db_inserts"]:
            print("💾 DADOS INSERIDOS NO BANCO:")
            for key, count in sorted(self.stats["db_inserts"].items()):
                device, msg_type = key.split(':', 1)
                print(f"  {device} ({msg_type}): {count}")
            print()

        # Verificar consistência
        android_devices = self.stats["android_devices"]
        db_devices = self.stats["db_devices"]

        missing_in_db = android_devices - db_devices
        extra_in_db = db_devices - android_devices

        if missing_in_db:
            print(f"⚠️ Dispositivos no MQTT mas não no DB: {', '.join(missing_in_db)}")

        if extra_in_db:
            print(f"ℹ️ Dispositivos no DB mas não no MQTT: {', '.join(extra_in_db)}")

        # Avaliação geral
        mqtt_total = sum(self.stats["mqtt_messages"].values())
        db_total = sum(self.stats["db_inserts"].values())

        if mqtt_total == 0:
            print("❌ NENHUMA MENSAGEM MQTT RECEBIDA - VERIFICAR CELULAR/APLICATIVO")
        elif db_total == 0:
            print("❌ NENHUMA MENSAGEM CHEGOU NO BANCO - VERIFICAR INGEST WORKER")
        elif mqtt_total == db_total:
            print("🎉 FLUXO COMPLETO FUNCIONANDO - TODAS AS MENSAGENS CHEGARAM!")
        elif db_total > 0:
            loss_rate = (mqtt_total - db_total) / mqtt_total * 100
            if loss_rate < 5:
                print(".1f"            else:
                print(".1f"
        if self.stats["errors"]:
            print("
❌ ERROS ENCONTRADOS:"            for error in self.stats["errors"][-5:]:  # Últimos 5 erros
                print(f"  {error}")

    def run(self):
        """Executa o monitoramento."""
        print("🚀 Iniciando monitoramento do fluxo de dados AuraTracking")
        print(f"Duração: {self.duration}s | Intervalo: {self.interval}s")
        print("-" * 60)

        self.setup_signal_handlers()
        self.connect_mqtt()
        self.connect_database()

        last_check = 0
        iteration = 0

        try:
            while self.running and time.time() < self.end_time:
                current_time = time.time()
                iteration += 1

                print(f"\n🔄 Iteração {iteration} - {datetime.now().strftime('%H:%M:%S')}")

                # Verificações periódicas
                if current_time - last_check >= self.interval:
                    self.check_database_ingestion()
                    self.check_ingest_health()
                    last_check = current_time

                # Aguardar próximo ciclo
                time.sleep(min(self.interval, self.end_time - current_time))

        except KeyboardInterrupt:
            print("\n🛑 Monitoramento interrompido pelo usuário")

        finally:
            self.cleanup()
            self.print_summary()

    def cleanup(self):
        """Limpa conexões."""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            print("✅ MQTT desconectado")

        if self.db_conn:
            self.db_conn.close()
            print("✅ Database desconectado")

def main():
    parser = argparse.ArgumentParser(description="Monitor de fluxo de dados AuraTracking")
    parser.add_argument("--duration", type=int, default=60,
                       help="Duração do monitoramento em segundos (padrão: 60)")
    parser.add_argument("--interval", type=int, default=5,
                       help="Intervalo entre verificações em segundos (padrão: 5)")

    args = parser.parse_args()

    monitor = FlowMonitor(duration=args.duration, interval=args.interval)
    monitor.run()

if __name__ == "__main__":
    main()
