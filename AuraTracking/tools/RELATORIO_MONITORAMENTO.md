# Relatório de Monitoramento - AuraTracking

**Data:** $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  
**Dispositivo:** Motorola Moto G34 5G  
**Duração:** 30+ segundos

---

## ✅ Status Geral

### Mensagens MQTT
- **Status:** ✅ **ENVIANDO CORRETAMENTE**
- **Taxa:** ~1.02 mensagens/segundo (conforme esperado - 1Hz)
- **Tamanho:** ~1.6 KB por mensagem
- **Latência MQTT:** 16-219ms (média ~50ms)
- **Mensagens em Fila:** 0 (todas sendo enviadas online)
- **Flag transmissionMode:** Funcionando corretamente

### Memória
- **Total PSS:** ~93 MB
- **Native Heap:** ~9.9 MB
- **Dalvik Heap:** ~14.6 MB
- **Análise:** ✅ **DENTRO DO ESPERADO**
  - Apps Android típicos: 50-150 MB
  - App com foreground service e múltiplos sensores: Normal

### CPU
- **Uso:** Muito baixo (<1%)
- **Análise:** ✅ **EXCELENTE**
  - App não está sobrecarregando o sistema
  - Processamento eficiente

### Dados Capturados
- ✅ **GPS:** Funcionando (lat=-11.6990226, lon=-47.1673056)
- ✅ **IMU:** Funcionando (404-405 amostras por segundo, média a 1Hz)
- ✅ **Orientação:** Funcionando (azimuth=156.8°, pitch=2.1°, roll=-1.8°)
- ✅ **Sistema:** Funcionando (com warnings de permissão, mas não crashando)

---

## 📊 Detalhamento

### Mensagens MQTT
```
Taxa de envio: 1.02 msg/s
Tamanho médio: ~1.65 KB
Latência média: ~50ms
Latência máxima: 219ms (aceitável)
Mensagens em fila: 0
```

### Uso de Memória
```
TOTAL PSS: 93.5 MB
  - Native Heap: 9.9 MB
  - Dalvik Heap: 14.6 MB
  - Code: 17.9 MB
  - Graphics: 22.6 MB
  - Stack: 3.0 MB
  - Other: 26.5 MB
```

### Latência MQTT (últimas mensagens)
- 16ms, 27ms, 25ms, 36ms, 44ms, 52ms, 68ms
- Alguns picos: 79ms, 111ms, 204ms, 219ms
- **Análise:** Latência aceitável para MQTT sobre rede

---

## ⚠️ Observações

### Warnings (Não Críticos)
1. **Permissões WiFi/Telefonia:** 
   - App está funcionando mesmo sem essas permissões
   - Dados WiFi/Celular retornam `null` quando não disponíveis
   - Não causa crash (corrigido)

2. **Latência MQTT ocasional alta:**
   - Alguns picos de 200ms+ são normais em redes móveis
   - Não afeta funcionalidade

### Pontos Positivos
1. ✅ Taxa de envio estável (1Hz)
2. ✅ Sem mensagens em fila (conexão estável)
3. ✅ Memória estável (sem vazamentos aparentes)
4. ✅ CPU baixo (eficiente)
5. ✅ Todos os sensores funcionando
6. ✅ Sem crashes

---

## 🎯 Conclusão

**Status:** ✅ **TUDO FUNCIONANDO CORRETAMENTE**

- Mensagens estão sendo enviadas via MQTT
- Uso de memória dentro do esperado
- Sem lentidão detectada
- Performance excelente

**Recomendações:**
- Monitorar memória em uso prolongado (horas/dias)
- Considerar otimizações se memória crescer acima de 150MB
- Latência MQTT está aceitável, mas pode melhorar com broker mais próximo

---

## 📝 Comandos Úteis

### Monitorar em tempo real:
```powershell
cd D:\tracking\AuraTracking\tools
.\test_monitor_simple.ps1 10.10.10.10 1883
```

### Verificar memória:
```powershell
adb shell dumpsys meminfo com.aura.tracking
```

### Verificar mensagens MQTT:
```powershell
adb logcat -d | Select-String -Pattern "Published to|Publish latency"
```

### Verificar processos:
```powershell
adb shell "ps -A | grep aura"
```

