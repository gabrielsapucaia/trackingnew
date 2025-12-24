# Plano de Correcao: Calculo de Duracoes Limpas

## Problema Identificado

### Situacao Atual

O sistema detecta dois tipos de paradas ociosas durante uma fase:

| Tipo | Descricao | Exemplo Ciclo 46 |
|------|-----------|------------------|
| `durante_carga_embutida` | Micro-paradas especificas | 4 paradas = 246s |
| `durante_carga` | Parada geral (anomalia MAD) | 1 parada = 856s* |

*Nota: 856s e o valor no JSON mas o periodo real e 455s (11:11:07-11:18:42)

### O Bug

O codigo atual **so subtrai** as paradas `_embutida`:

```python
# Codigo atual (INCORRETO)
paradas_carga_emb = sum(
    p.duracao_sec for p in paradas_ociosas_ciclo
    if p.fase.startswith('durante_carga')
)
```

**Problema**: Existem SOBREPOSICOES entre `durante_carga` e `durante_carga_embutida`!

```
11:05:41-11:07:10  [embutida 89s]
11:11:07-----------11:18:42  [durante_carga 455s]
       11:11:21-11:12:30 [embutida 69s - SOBREPOE!]
              11:13:11-11:14:00 [embutida 49s - SOBREPOE!]
                     11:14:51-11:15:30 [embutida 39s - SOBREPOE!]
```

Somar tudo causa **CONTAGEM DUPLA** (246s + 856s = 1102s vs real = 578s)

---

## Solucao Proposta: Merge de Intervalos

### Algoritmo

1. Coletar TODOS os intervalos de parada (ambos os tipos)
2. Ordenar por horario de inicio
3. Mesclar intervalos sobrepostos
4. Calcular duracao total sem duplicacao

### Pseudocodigo

```python
def merge_intervals(paradas):
    """Mescla intervalos sobrepostos e retorna duracao total."""
    if not paradas:
        return 0

    # Ordenar por inicio
    intervals = sorted([(p.inicio, p.fim) for p in paradas])

    # Mesclar sobreposicoes
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:  # Sobreposicao
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # Calcular duracao total
    return sum((end - start).total_seconds() for start, end in merged)
```

### Resultado Esperado

| Ciclo | Fase | Atual | Corrigido |
|-------|------|-------|-----------|
| 46 | Carga | 13.7m | **8.2m** |
| 46 | Basc | 3.1m | ~1.5m |

---

## Implementacao

### Arquivos a Modificar

1. `3_processamento/gerar_extrato_ciclos_rev2.py`
   - Adicionar funcao `merge_intervals()`
   - Modificar calculo de `carga_duracao_limpa` e `basculamento_duracao_limpa`

### Passos

#### Passo 1: Adicionar funcao de merge

```python
from datetime import datetime

def merge_paradas_intervals(paradas: list, fase_prefix: str) -> float:
    """
    Mescla intervalos de paradas sobrepostos e retorna duracao total.

    Args:
        paradas: Lista de ParadaOciosa
        fase_prefix: Prefixo da fase (ex: 'durante_carga', 'durante_basc')

    Returns:
        Duracao total em segundos (sem duplicacoes)
    """
    # Filtrar paradas da fase
    intervals = []
    for p in paradas:
        if p.fase.startswith(fase_prefix):
            intervals.append((p.inicio, p.fim))

    if not intervals:
        return 0.0

    # Ordenar por inicio
    intervals.sort(key=lambda x: x[0])

    # Mesclar sobreposicoes
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # Calcular duracao total
    total = sum((end - start).total_seconds() for start, end in merged)
    return total
```

#### Passo 2: Modificar calculo das duracoes limpas

```python
# ANTES (incorreto - soma simples)
paradas_carga_emb = sum(
    p.duracao_sec for p in paradas_ociosas_ciclo
    if p.fase.startswith('durante_carga')
)

# DEPOIS (correto - merge de intervalos)
paradas_carga_merged = merge_paradas_intervals(
    paradas_ociosas_ciclo, 'durante_carga'
)
paradas_basc_merged = merge_paradas_intervals(
    paradas_ociosas_ciclo, 'durante_basc'
)

carga_duracao_limpa = max(0, carga_duracao - paradas_carga_merged)
basc_duracao_limpa = max(0, basc_duracao - paradas_basc_merged)
```

---

## Validacao

### Antes da Correcao

```
Ciclo 46:
  carga_duracao_sec = 1070 (17.8m)
  carga_duracao_limpa_sec = 824 (13.7m)  <- INCORRETO

Histograma Carregamento:
  Max = 13.7 min  <- OUTLIER VISIVEL
```

### Apos a Correcao

```
Ciclo 46:
  carga_duracao_sec = 1070 (17.8m)
  carga_duracao_limpa_sec = ~492 (8.2m)  <- CORRETO

Histograma Carregamento:
  Max = ~8 min  <- SEM OUTLIER EXTREMO
```

---

## Genericidade para Outros Datasets

### Parametros Configuraveis

O algoritmo e generico e funciona com qualquer dataset que tenha:

1. **Dados de telemetria**: lat, lon, timestamp, vibracao
2. **Poligonos de areas**: JSON com coordenadas
3. **Configuracao**: YAML com thresholds

### Estrutura de Dados Requerida

```yaml
# config.yaml
deteccao:
  vibracao_threshold: 0.3  # g - limiar para parada
  parada_min_duracao: 30   # segundos
  mad_multiplier: 3.0      # para anomalias

fases:
  - nome: carregamento
    tipo: area
    areas: [PAIOL, FRENTE_A, FRENTE_B]
  - nome: basculamento
    tipo: area
    areas: [BF - Paiol, BF - Frente]
```

### Fluxo Generico

```
1. Carregar telemetria (CSV)
2. Carregar poligonos (JSON)
3. Detectar ciclos (area-based)
4. Detectar paradas (vibracao-based)
5. Extrair paradas embutidas (por fase)
6. Merge intervalos sobrepostos
7. Calcular duracoes limpas
8. Exportar CSV + JSON
```

---

## Consideracoes Finais

### Por que usar MERGE em vez de MAX?

| Abordagem | Pros | Contras |
|-----------|------|---------|
| SUM | Simples | Conta duplicado se sobreposicao |
| MAX | Simples | Ignora paradas fora do intervalo maior |
| **MERGE** | Correto matematicamente | Mais complexo |

**MERGE e a unica abordagem correta** pois:
- Nao conta duplicado (evita sobreposicoes)
- Nao ignora paradas separadas (captura todas)

### Impacto em Outros Ciclos

O algoritmo so afeta ciclos que tem AMBOS os tipos de parada na mesma fase.
Ciclos com apenas `_embutida` ou apenas `durante_X` nao serao afetados.

### Reprocessamento Necessario

Apos implementar a correcao:
1. Re-executar `gerar_extrato_ciclos_rev2.py`
2. Copiar novos CSVs para `5_visualizacao/`
3. Verificar histogramas

---

## Checklist

- [ ] Adicionar funcao `merge_paradas_intervals()`
- [ ] Modificar calculo de duracoes limpas
- [ ] Testar com Ciclo 46
- [ ] Verificar outros ciclos nao foram afetados negativamente
- [ ] Atualizar CSV e JSON
- [ ] Verificar histogramas
