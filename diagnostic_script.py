#!/usr/bin/env python3
"""
============================================================
AuraTracking - Script de Diagnóstico Completo
============================================================
Verifica o fluxo completo de dados:
1. Celular → Mosquitto (MQTT)
2. Mosquitto → TimescaleDB (via Ingest Worker)

Uso:
python3 diagnostic_script.py

============================================================
"""

import asyncio
import json
import os
import psycopg2
import paho.mqtt.client as mqtt
import requests
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

class DiagnosticResult:
    """Resultado de um teste diagnóstico."""

    def __init__(self, test_name: str, success: bool, message: str, details: Dict[str, Any] = None):
        self.test_name = test_name
        self.success = success
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self):
        return {
            "test": self.test_name,
            "success": self.success,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }

class AuraTrackingDiagnostics:
    """Diagnóstico completo do sistema AuraTracking."""

    def __init__(self):
        self.results = []
        self.config = {
            "mqtt_host": "10.10.10.10",
            "mqtt_port": 1883,
            "db_host": "10.10.10.20",
            "db_port": 5432,
            "db_name": "auratracking",
            "db_user": "aura",
            "db_password": "aura2025",
            "ingest_host": "10.10.10.30",
            "ingest_port": 8080,
            "test_device": "diagnostic_test",
            "test_topic": "aura/tracking/diagnostic_test/telemetry"
        }

    def log_result(self, result: DiagnosticResult):
        """Registra resultado de teste."""
        self.results.append(result)
        status = "✅ PASSOU" if result.success else "❌ FALHOU"
        print(f"[{status}] {result.test_name}: {result.message}")
        if result.details:
            for key, value in result.details.items():
                print(f"  {key}: {value}")

    async def test_docker_services(self):
        """Testa se os serviços Docker estão rodando."""
        try:
            # Tenta executar docker ps
            result = subprocess.run(
                ["docker", "ps", "--format", "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                services = {}
                for line in lines[1:]:  # Skip header
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            name = parts[0].strip()
                            status = parts[1].strip()
                            services[name] = status

                expected_services = ['aura_emqx', 'aura_timescaledb', 'aura_ingest', 'aura_grafana']
                running_services = []
                failed_services = []

                for service in expected_services:
                    if service in services:
                        if 'Up' in services[service]:
                            running_services.append(service)
                        else:
                            failed_services.append(f"{service}: {services[service]}")
                    else:
                        failed_services.append(f"{service}: not found")

                success = len(failed_services) == 0
                message = f"{len(running_services)}/{len(expected_services)} serviços rodando"
                details = {
                    "running": running_services,
                    "failed": failed_services,
                    "all_services": services
                }

            else:
                success = False
                message = f"Docker não disponível: {result.stderr.strip()}"
                details = {"error": result.stderr.strip()}

        except Exception as e:
            success = False
            message = f"Erro ao verificar Docker: {str(e)}"
            details = {"error": str(e)}

        self.log_result(DiagnosticResult("Docker Services", success, message, details))

    def test_mqtt_connectivity(self):
        """Testa conectividade MQTT."""
        def on_connect(client, userdata, flags, rc, properties=None):
            nonlocal connection_result
            if rc == 0:
                connection_result = "connected"
            else:
                connection_result = f"failed_rc_{rc}"

        def on_disconnect(client, userdata, rc, properties=None):
            nonlocal connection_result
            if connection_result == "connected":
                connection_result = "disconnected"

        connection_result = "timeout"
        client = mqtt.Client(client_id="diagnostic_client", protocol=mqtt.MQTTv5)
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect

        try:
            client.connect(self.config["mqtt_host"], self.config["mqtt_port"], keepalive=5)
            client.loop_start()

            # Wait for connection
            timeout = 5
            start_time = time.time()
            while time.time() - start_time < timeout:
                if connection_result != "timeout":
                    break
                time.sleep(0.1)

            client.loop_stop()
            client.disconnect()

            success = connection_result == "connected"
            message = f"Conectividade MQTT: {connection_result}"
            details = {
                "host": self.config["mqtt_host"],
                "port": self.config["mqtt_port"],
                "result": connection_result
            }

        except Exception as e:
            success = False
            message = f"Falha na conexão MQTT: {str(e)}"
            details = {"error": str(e)}

        self.log_result(DiagnosticResult("MQTT Connectivity", success, message, details))

    def test_mqtt_publish_subscribe(self):
        """Testa publicação e subscrição MQTT."""
        received_messages = []
        connection_status = {"publisher": False, "subscriber": False}

        def on_publisher_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                connection_status["publisher"] = True

        def on_subscriber_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                connection_status["subscriber"] = True

        def on_message(client, userdata, msg):
            received_messages.append({
                "topic": msg.topic,
                "payload": msg.payload.decode('utf-8'),
                "qos": msg.qos
            })

        # Publisher
        publisher = mqtt.Client(client_id="diagnostic_publisher", protocol=mqtt.MQTTv5)
        publisher.on_connect = on_publisher_connect

        # Subscriber
        subscriber = mqtt.Client(client_id="diagnostic_subscriber", protocol=mqtt.MQTTv5)
        subscriber.on_connect = on_subscriber_connect
        subscriber.on_message = on_message

        try:
            # Connect both
            publisher.connect(self.config["mqtt_host"], self.config["mqtt_port"], keepalive=5)
            subscriber.connect(self.config["mqtt_host"], self.config["mqtt_port"], keepalive=5)

            publisher.loop_start()
            subscriber.loop_start()

            # Wait for connections
            timeout = 5
            start_time = time.time()
            while time.time() - start_time < timeout:
                if connection_status["publisher"] and connection_status["subscriber"]:
                    break
                time.sleep(0.1)

            if not (connection_status["publisher"] and connection_status["subscriber"]):
                raise Exception("Falha na conexão publisher/subscriber")

            # Subscribe
            subscriber.subscribe(self.config["test_topic"], qos=1)

            # Publish test message
            test_payload = {
                "messageId": f"diagnostic_{int(time.time())}",
                "deviceId": self.config["test_device"],
                "timestamp": int(time.time() * 1000),
                "gps": {"lat": -23.550520, "lon": -46.633308, "accuracy": 5.0},
                "diagnostic": True
            }

            publisher.publish(
                self.config["test_topic"],
                json.dumps(test_payload),
                qos=1,
                retain=False
            )

            # Wait for message
            start_time = time.time()
            while time.time() - start_time < 5:
                if received_messages:
                    break
                time.sleep(0.1)

            # Cleanup
            publisher.loop_stop()
            subscriber.loop_stop()
            publisher.disconnect()
            subscriber.disconnect()

            success = len(received_messages) > 0
            message = f"MQTT Pub/Sub: {len(received_messages)} mensagens recebidas"
            details = {
                "topic": self.config["test_topic"],
                "sent": test_payload,
                "received_count": len(received_messages),
                "received": received_messages[:1] if received_messages else None
            }

        except Exception as e:
            success = False
            message = f"Falha no teste MQTT Pub/Sub: {str(e)}"
            details = {"error": str(e)}

        self.log_result(DiagnosticResult("MQTT Pub/Sub", success, message, details))

    def test_database_connectivity(self):
        """Testa conectividade com TimescaleDB."""
        try:
            conn = psycopg2.connect(
                host=self.config["db_host"],
                port=self.config["db_port"],
                dbname=self.config["db_name"],
                user=self.config["db_user"],
                password=self.config["db_password"],
                connect_timeout=5
            )

            with conn.cursor() as cur:
                # Test basic query
                cur.execute("SELECT COUNT(*) FROM telemetry")
                telemetry_count = cur.fetchone()[0]

                # Test recent data
                cur.execute("""
                    SELECT COUNT(*) FROM telemetry
                    WHERE time > NOW() - INTERVAL '1 hour'
                """)
                recent_count = cur.fetchone()[0]

                # Test hypertable info
                cur.execute("SELECT hypertable_name FROM timescaledb_information.hypertables")
                hypertables = [row[0] for row in cur.fetchall()]

            conn.close()

            success = True
            message = f"TimescaleDB conectado, {telemetry_count} registros totais"
            details = {
                "telemetry_count": telemetry_count,
                "recent_count": recent_count,
                "hypertables": hypertables,
                "host": self.config["db_host"],
                "database": self.config["db_name"]
            }

        except Exception as e:
            success = False
            message = f"Falha na conexão TimescaleDB: {str(e)}"
            details = {"error": str(e)}

        self.log_result(DiagnosticResult("Database Connectivity", success, message, details))

    def test_ingest_worker_health(self):
        """Testa health check do Ingest Worker."""
        try:
            url = f"http://{self.config['ingest_host']}:{self.config['ingest_port']}/health"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                health_data = response.json()

                success = health_data.get("status") == "healthy"
                message = f"Ingest Worker: {health_data.get('status', 'unknown')}"
                details = health_data

            else:
                success = False
                message = f"Ingest Worker HTTP {response.status_code}"
                details = {"status_code": response.status_code, "response": response.text}

        except requests.exceptions.RequestException as e:
            success = False
            message = f"Falha no health check do Ingest Worker: {str(e)}"
            details = {"error": str(e)}
        except Exception as e:
            success = False
            message = f"Erro no teste do Ingest Worker: {str(e)}"
            details = {"error": str(e)}

        self.log_result(DiagnosticResult("Ingest Worker Health", success, message, details))

    def test_recent_data_ingestion(self):
        """Testa se dados recentes estão sendo ingeridos."""
        try:
            conn = psycopg2.connect(
                host=self.config["db_host"],
                port=self.config["db_port"],
                dbname=self.config["db_name"],
                user=self.config["db_user"],
                password=self.config["db_password"],
                connect_timeout=5
            )

            with conn.cursor() as cur:
                # Verificar dados dos últimos 5 minutos
                cur.execute("""
                    SELECT
                        device_id,
                        COUNT(*) as count,
                        MIN(time) as oldest,
                        MAX(time) as newest,
                        AVG(speed_kmh) as avg_speed,
                        MAX(speed_kmh) as max_speed
                    FROM telemetry
                    WHERE time > NOW() - INTERVAL '5 minutes'
                    GROUP BY device_id
                    ORDER BY newest DESC
                """)

                rows = cur.fetchall()
                active_devices = []
                for row in rows:
                    active_devices.append({
                        "device_id": row[0],
                        "count": row[1],
                        "oldest": row[2].isoformat() if row[2] else None,
                        "newest": row[3].isoformat() if row[3] else None,
                        "avg_speed_kmh": round(float(row[4]), 1) if row[4] else None,
                        "max_speed_kmh": round(float(row[5]), 1) if row[5] else None
                    })

                # Verificar eventos recentes
                cur.execute("""
                    SELECT event_type, COUNT(*)
                    FROM events
                    WHERE time > NOW() - INTERVAL '1 hour'
                    GROUP BY event_type
                """)

                event_counts = {row[0]: row[1] for row in cur.fetchall()}

            conn.close()

            total_recent = sum(d["count"] for d in active_devices)
            success = total_recent > 0
            message = f"Dados recentes: {total_recent} pontos de {len(active_devices)} dispositivos"
            details = {
                "active_devices": active_devices,
                "total_points": total_recent,
                "event_types": event_counts
            }

        except Exception as e:
            success = False
            message = f"Falha ao verificar dados recentes: {str(e)}"
            details = {"error": str(e)}

        self.log_result(DiagnosticResult("Recent Data Ingestion", success, message, details))

    def test_end_to_end_flow(self):
        """Testa fluxo completo: MQTT → Ingest → DB."""
        test_message_id = f"e2e_test_{int(time.time())}"
        test_topic = "aura/tracking/e2e_test/telemetry"

        # 1. Publicar mensagem de teste
        def on_connect(client, userdata, flags, rc, properties=None):
            nonlocal connected
            connected = (rc == 0)

        connected = False
        client = mqtt.Client(client_id="e2e_test_client", protocol=mqtt.MQTTv5)
        client.on_connect = on_connect

        try:
            client.connect(self.config["mqtt_host"], self.config["mqtt_port"], keepalive=5)
            client.loop_start()

            # Wait for connection
            timeout = 5
            start_time = time.time()
            while time.time() - start_time < timeout and not connected:
                time.sleep(0.1)

            if not connected:
                raise Exception("Falha na conexão MQTT para teste E2E")

            # Publish test message
            test_payload = {
                "messageId": test_message_id,
                "deviceId": "e2e_test_device",
                "timestamp": int(time.time() * 1000),
                "gps": {
                    "lat": -23.550520,
                    "lon": -46.633308,
                    "accuracy": 1.0,
                    "speed": 50.0,
                    "bearing": 90.0
                },
                "imu": {
                    "accelX": 0.1,
                    "accelY": 0.0,
                    "accelZ": 9.8,
                    "gyroX": 0.0,
                    "gyroY": 0.0,
                    "gyroZ": 0.0
                }
            }

            result = client.publish(test_topic, json.dumps(test_payload), qos=1)
            result.wait_for_publish(5)

            client.loop_stop()
            client.disconnect()

            # 2. Aguardar processamento
            print("Aguardando processamento do Ingest Worker (10s)...")
            time.sleep(10)

            # 3. Verificar se chegou no banco
            conn = psycopg2.connect(
                host=self.config["db_host"],
                port=self.config["db_port"],
                dbname=self.config["db_name"],
                user=self.config["db_user"],
                password=self.config["db_password"],
                connect_timeout=5
            )

            with conn.cursor() as cur:
                cur.execute("""
                    SELECT time, device_id, latitude, longitude, speed_kmh, accel_magnitude
                    FROM telemetry
                    WHERE message_id = %s
                """, (test_message_id,))

                row = cur.fetchone()

            conn.close()

            if row:
                success = True
                message = "Fluxo E2E funcionando: MQTT → Ingest → DB"
                details = {
                    "message_id": test_message_id,
                    "device_id": row[1],
                    "time": row[0].isoformat(),
                    "latitude": float(row[2]),
                    "longitude": float(row[3]),
                    "speed_kmh": float(row[4]) if row[4] else None,
                    "accel_magnitude": float(row[5]) if row[5] else None
                }
            else:
                success = False
                message = "Fluxo E2E falhou: mensagem não chegou no banco"
                details = {"message_id": test_message_id}

        except Exception as e:
            success = False
            message = f"Falha no teste E2E: {str(e)}"
            details = {"error": str(e)}

        self.log_result(DiagnosticResult("End-to-End Flow", success, message, details))

    def check_android_app_logs(self):
        """Verifica logs do app Android (se disponível)."""
        log_files = [
            "/Users/sapucaia/tracking/AuraTracking/mqtt_monitoring.log",
            "/Users/sapucaia/tracking/AuraTracking/mqtt_final_test.log"
        ]

        found_logs = []
        latest_entries = {}

        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        if lines:
                            found_logs.append(log_file)
                            # Últimas 5 linhas
                            latest_entries[log_file] = [line.strip() for line in lines[-5:]]
                except Exception as e:
                    latest_entries[log_file] = [f"Erro ao ler: {e}"]

        success = len(found_logs) > 0
        message = f"Logs do Android: {len(found_logs)} arquivos encontrados"
        details = {
            "log_files": found_logs,
            "latest_entries": latest_entries
        }

        self.log_result(DiagnosticResult("Android App Logs", success, message, details))

    async def run_all_diagnostics(self):
        """Executa todos os diagnósticos."""
        print("🚀 Iniciando diagnóstico completo do AuraTracking")
        print("=" * 60)

        # Testes de infraestrutura
        await self.test_docker_services()

        # Testes MQTT
        self.test_mqtt_connectivity()
        self.test_mqtt_publish_subscribe()

        # Testes de banco
        self.test_database_connectivity()

        # Testes do Ingest Worker
        self.test_ingest_worker_health()

        # Testes de dados
        self.test_recent_data_ingestion()

        # Teste E2E
        self.test_end_to_end_flow()

        # Logs do Android
        self.check_android_app_logs()

        print("\n" + "=" * 60)
        print("📊 RESUMO DOS DIAGNÓSTICOS")
        print("=" * 60)

        successful = sum(1 for r in self.results if r.success)
        total = len(self.results)

        print(f"Total de testes: {total}")
        print(f"Passaram: {successful}")
        print(f"Falharam: {total - successful}")

        if successful == total:
            print("🎉 SISTEMA FUNCIONANDO PERFEITAMENTE!")
        elif successful >= total * 0.7:
            print("⚠️ SISTEMA COM ALGUMAS QUESTÕES - VERIFICAR DETALHES")
        else:
            print("❌ SISTEMA COM PROBLEMAS GRAVES - NECESSITA ATENÇÃO")

        print("\n📋 DETALHES:")
        for result in self.results:
            status = "✅" if result.success else "❌"
            print(f"{status} {result.test_name}")

        # Salvar relatório completo
        self.save_report()

    def save_report(self):
        """Salva relatório completo em JSON."""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_tests": len(self.results),
                "passed": sum(1 for r in self.results if r.success),
                "failed": sum(1 for r in self.results if not r.success)
            },
            "results": [r.to_dict() for r in self.results]
        }

        report_file = f"/Users/sapucaia/tracking/diagnostic_report_{int(time.time())}.json"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Relatório salvo em: {report_file}")
        except Exception as e:
            print(f"\n❌ Erro ao salvar relatório: {e}")

def main():
    """Função principal."""
    diagnostics = AuraTrackingDiagnostics()

    # Executar diagnósticos de forma assíncrona
    asyncio.run(diagnostics.run_all_diagnostics())

if __name__ == "__main__":
    main()
