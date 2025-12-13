# Script para testar o dashboard
import requests
import time

print("Testando dashboard...")

# Aguardar o servidor iniciar
time.sleep(2)

try:
    # Testar se o servidor está respondendo
    response = requests.get('http://127.0.0.1:8050/')
    print(f"Status code: {response.status_code}")

    if response.status_code == 200:
        print("✅ Dashboard está funcionando!")

        # Verificar se há dados no HTML
        if 'Dash' in response.text:
            print("✅ Interface Dash carregada")

        if 'Dashboard de Telemetria' in response.text:
            print("✅ Título do dashboard encontrado")

        if 'device-dropdown' in response.text:
            print("✅ Dropdown de dispositivo encontrado")

        print("\n📋 Instruções para uso:")
        print("1. Abra seu navegador")
        print("2. Acesse: http://127.0.0.1:8050/")
        print("3. Selecione um dispositivo no dropdown")
        print("4. Navegue pelas abas para ver os gráficos")
        print("\n🎯 Principais abas:")
        print("- GPS/Localização: Mapa + métricas GPS")
        print("- Acelerômetro: Dados 3D + séries temporais")
        print("- Giroscópio: Rotação XYZ + magnitude")
        print("- Bateria: Nível + temperatura + voltagem")
        print("- Redes: WiFi + celular")
        print("- Orientação: Azimuth, pitch, roll")
        print("- Movimento: Detecção de movimento")

    else:
        print(f"❌ Erro no servidor: {response.status_code}")

except requests.exceptions.RequestException as e:
    print(f"❌ Erro de conexão: {e}")
    print("Verifique se o dashboard está rodando: python dashboard.py")

