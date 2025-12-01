# Supabase Integration

Este módulo integra o Supabase ao projeto AuraTracking, fornecendo autenticação, banco de dados relacional e funcionalidades em tempo real.

## Configuração

### Credenciais

As credenciais do Supabase estão configuradas diretamente no código por enquanto. Para produção, mova-as para variáveis de ambiente:

```bash
# .env.local
VITE_SUPABASE_URL=https://nucqowewuqeveocmsdnq.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
VITE_SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Arquivos

- `client.ts` - Cliente Supabase configurado
- `types.ts` - Tipos TypeScript para as tabelas
- `auth.ts` - Utilitários de autenticação
- `realtime.ts` - Funcionalidades em tempo real
- `index.ts` - Exportações principais

## Uso Básico

### Importação

```typescript
import { supabase, authUtils, realtimeManager } from '@/lib/supabase'
```

### Autenticação

```typescript
import { AuthManager } from '@/lib/supabase'

// Login
const { user, error } = await AuthManager.signIn({
  email: 'user@example.com',
  password: 'password123'
})

// Registro
const { user, error } = await AuthManager.signUp({
  email: 'user@example.com',
  password: 'password123',
  full_name: 'João Silva'
})

// Logout
await AuthManager.signOut()

// Verificar se está autenticado
const isAuth = await AuthManager.isAuthenticated()

// Ouvir mudanças de estado
const { data: { subscription } } = AuthManager.onAuthStateChange((user) => {
  console.log('User changed:', user)
})
```

### Banco de Dados

```typescript
import { supabase } from '@/lib/supabase'

// Buscar dispositivos
const { data: devices, error } = await supabase
  .from('devices')
  .select('*')
  .eq('is_active', true)

// Inserir novo dispositivo
const { data, error } = await supabase
  .from('devices')
  .insert({
    device_id: 'DEV001',
    operator_id: 'OP001',
    name: 'Equipamento de Teste'
  })
  .select()
```

### Tempo Real

```typescript
import { realtimeManager } from '@/lib/supabase'

// Inscrever em mudanças de dispositivos
const channelName = realtimeManager.subscribeToTable('devices', {
  onInsert: (payload) => console.log('Novo dispositivo:', payload.new),
  onUpdate: (payload) => console.log('Dispositivo atualizado:', payload.new),
  onDelete: (payload) => console.log('Dispositivo removido:', payload.old)
})

// Cancelar inscrição
realtimeManager.unsubscribe(channelName)
```

### API Client Integrado

O cliente API existente foi estendido com métodos Supabase:

```typescript
import { api } from '@/lib/api'

// Usar métodos Supabase
const { devices } = await api.getDevicesFromSupabase()
const device = await api.createDevice({
  device_id: 'DEV001',
  operator_id: 'OP001',
  name: 'Novo Equipamento'
})

// Métodos REST originais continuam funcionando
const { devices } = await api.getDevices() // Via REST API
```

## Tabelas Disponíveis

### Profiles
Informações de usuários/autenticação.

### Devices
Metadados de dispositivos (complementar ao TimescaleDB).

### Alerts
Configurações de alertas e notificações.

### Audit Logs
Logs de auditoria do sistema.

## Próximos Passos

1. **Configurar variáveis de ambiente** para produção
2. **Criar tabelas no Supabase** conforme os tipos definidos
3. **Implementar Row Level Security (RLS)** para controle de acesso
4. **Configurar triggers e funções** no banco
5. **Integrar autenticação** na interface do usuário
6. **Adicionar subscriptions em tempo real** nos componentes

## Segurança

- Use sempre HTTPS em produção
- Configure RLS nas tabelas
- Não exponha chaves service_role no cliente
- Valide dados no backend antes de inserir
- Use JWT com expiração adequada

## Monitoramento

O módulo inclui funções de health check:

```typescript
import { supabaseHelpers } from '@/lib/supabase'

const { healthy, error } = await supabaseHelpers.healthCheck()
```
