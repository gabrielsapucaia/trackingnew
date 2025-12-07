# Relatório de Testes End-to-End - Aura Tracking

**Data:** 06/12/2025
**Executor:** QA Engineer (AI Agent)
**Versão:** revisao-7

---

## 📊 Resumo Executivo

O sistema **Aura Tracking** demonstra estabilidade nas funcionalidades principais de ingestão e transmissão de dados em tempo real. O fluxo crítico (MQTT -> DB -> SSE) está operacional e performático. No entanto, foram identificadas falhas na **resiliência** (fila offline) e no comportamento de **heartbeat** do SSE, que podem impactar a confiabilidade em produção.

**Status Geral:** ⚠️ **APROVADO COM RESTRIÇÕES**

---

## 📝 Resultados por Fase

### ✅ Fase 1: Backend (Ingestão & Throttle)
- **Ingestão:** 100% de sucesso. Mensagens MQTT são persistidas corretamente no TimescaleDB.
- **Throttle:** Funcional. O sistema limita corretamente o broadcast para ~1 evento a cada 5 segundos por dispositivo, mesmo sob carga de 10Hz.
- **Correção Realizada:** Ajuste no formato do payload JSON (camelCase e timestamp em ms) foi necessário para compatibilidade.

### ⚠️ Fase 2: SSE (Isolado)
- **Conexão:** Sucesso (HTTP 200, Headers corretos).
- **Heartbeat:** ❌ **FALHA**. O sistema não envia heartbeats quando há tráfego de outros dispositivos ou o timeout de 15s é resetado por qualquer atividade global.
  - *Impacto:* O frontend pode assumir falsamente que a conexão caiu se o dispositivo monitorado estiver silencioso, mas houver tráfego no sistema.

### ✅ Fase 3: Frontend (Simulação)
- **Bootstrap:** API `/api/devices` retorna lista correta de dispositivos.
- **Fluxo SSE:** O cliente recebe atualizações de `device-update` corretamente.
- **Fallback:** Simulado com sucesso (detecção de falha e reconexão).

### ❌ Fase 4: Resiliência (Chaos Engineering)
- **Cenário:** Parada do TimescaleDB durante ingestão.
- **Resultado Esperado:** Enfileiramento de mensagens na fila offline (SQLite).
- **Resultado Obtido:** Fila offline permaneceu vazia (tamanho 0).
- **Análise:** O worker parece reter os dados em memória (`batch_buffer`) e retentar indefinidamente ou falhar silenciosamente sem persistir no disco.
- **Risco:** **ALTO**. Perda de dados em caso de crash do worker durante indisponibilidade do banco.

### ✅ Fase 5: Carga
- **Throughput:** Suportou rajadas de ~26k msg/s (publicação) sem queda imediata dos serviços.

---

## 🐛 Bugs e Riscos Identificados

1.  **BUG CRÍTICO (Resiliência):** A fila offline não está sendo populada quando o banco cai. O mecanismo de flush parece depender da chegada de novas mensagens e o tratamento de erro de conexão pode estar incompleto.
2.  **BUG (SSE Heartbeat):** O heartbeat só é enviado se *nenhuma* mensagem for processada no loop global, ao invés de ser por conexão/cliente.
3.  **BUG (Payload Validation):** O backend rejeita payloads com `device_id` (snake_case), exigindo `deviceId` (camelCase), o que pode ser inconsistente com outros sistemas.

---

## 🔧 Recomendações Técnicas

1.  **Corrigir Lógica de Flush:** Implementar um loop de background independente para forçar o flush do `batch_buffer` a cada `batch_timeout_ms`, independente da chegada de novas mensagens.
2.  **Revisar Tratamento de Erro no Ingest:** Garantir que falhas de conexão no `ensure_connected` disparem imediatamente o mecanismo de `offline_queue`.
3.  **Refatorar Heartbeat SSE:** O heartbeat deve ser enviado pelo gerador do SSE (dentro da view `stream_events`), garantindo que cada cliente receba um sinal de vida a cada 15s, independente do tráfego global.
4.  **Padronização de API:** Definir contrato estrito (Snake vs Camel Case) e aplicar validadores mais flexíveis ou transformadores no Pydantic.

---

## 🚀 Conclusão

O sistema **NÃO ESTÁ PRONTO** para produção crítica devido à falha na persistência offline (Risco de Perda de Dados). Recomenda-se corrigir os itens de Resiliência e Heartbeat antes do Go-Live.
