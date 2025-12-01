# Configuração do Supabase - AuraTracking

Este guia explica como configurar o banco de dados Supabase para o projeto AuraTracking.

## 📋 Pré-requisitos

- Conta no Supabase criada
- Credenciais do projeto configuradas no código (ou variáveis de ambiente)

## 🚀 Passo a Passo

### 1. Acessar o SQL Editor do Supabase

1. Faça login no [Supabase Dashboard](https://app.supabase.com)
2. Selecione seu projeto (`nucqowewuqeveocmsdnq`)
3. No menu lateral, clique em **SQL Editor**

### 2. Executar o Script SQL

1. Clique em **New Query**
2. Abra o arquivo `supabase_schema.sql` deste projeto
3. Copie todo o conteúdo do arquivo
4. Cole no editor SQL do Supabase
5. Clique em **Run** (ou pressione `Ctrl+Enter` / `Cmd+Enter`)

### 3. Verificar Tabelas Criadas

Após executar o script, você deve ver as seguintes tabelas criadas:

- ✅ `profiles` - Perfis de usuários
- ✅ `devices` - Metadados dos dispositivos
- ✅ `alerts` - Configurações de alertas
- ✅ `audit_logs` - Logs de auditoria
- ✅ `health_check` - Verificação de saúde

Para verificar, vá em **Table Editor** no menu lateral do Supabase.

## 🔐 Row Level Security (RLS)

O script já configura políticas de segurança (RLS) para todas as tabelas:

- **profiles**: Usuários podem ver e editar apenas seu próprio perfil
- **devices**: Todos podem ver, apenas admins podem modificar
- **alerts**: Todos podem ver, operadores e admins podem criar/editar
- **audit_logs**: Apenas admins podem ver
- **health_check**: Todos podem ver

## 📝 Inserir Dados de Teste (Opcional)

Após criar as tabelas, você pode inserir alguns dados de teste:

```sql
-- Inserir dispositivo de teste
INSERT INTO public.devices (device_id, operator_id, name, description, device_type, is_active)
VALUES 
  ('ZF524XRLK3', 'OP001', 'Caminhão 001', 'Caminhão de carga pesada', 'truck', true),
  ('AB123DEF45', 'OP002', 'Caminhão 002', 'Caminhão de carga média', 'truck', true),
  ('CD789GHI01', 'OP003', 'Escavadeira 001', 'Escavadeira hidráulica', 'excavator', true);

-- Inserir alerta de teste
INSERT INTO public.alerts (device_id, alert_type, title, message, severity, is_active, created_by)
SELECT 
  'ZF524XRLK3',
  'speed',
  'Velocidade Alta',
  'Velocidade acima de 60 km/h detectada',
  'high',
  true,
  (SELECT id FROM public.profiles LIMIT 1);
```

## ⚠️ Troubleshooting

### Erro: "Could not find the table"

Se você ainda receber este erro após executar o script:

1. **Verifique se o script foi executado completamente** - Veja se há erros no SQL Editor
2. **Verifique as permissões** - Certifique-se de que o usuário tem permissão para criar tabelas
3. **Limpe o cache** - O Supabase pode precisar de alguns segundos para atualizar o schema cache
4. **Verifique o schema** - Certifique-se de que está usando o schema `public`

### Erro: "permission denied"

Se você receber erros de permissão:

1. Verifique se está usando a chave correta (anon key vs service role key)
2. Verifique as políticas RLS configuradas
3. Certifique-se de que o usuário está autenticado (se necessário)

## 🔄 Atualizar Schema

Se precisar atualizar o schema no futuro:

1. Faça backup das tabelas existentes
2. Execute apenas as partes novas do script SQL
3. Ou use migrations do Supabase para gerenciar mudanças

## 📚 Recursos Adicionais

- [Documentação do Supabase](https://supabase.com/docs)
- [SQL Editor Guide](https://supabase.com/docs/guides/database/tables)
- [Row Level Security](https://supabase.com/docs/guides/auth/row-level-security)

## ✅ Checklist

- [ ] Script SQL executado com sucesso
- [ ] Todas as tabelas criadas
- [ ] Políticas RLS configuradas
- [ ] Dados de teste inseridos (opcional)
- [ ] Aplicação funcionando sem erros
