# Aura Tracking Dashboard

Dashboard para rastreamento e monitoramento de equipamentos.

## Configuração do Supabase

Para conectar com o banco de dados Supabase, siga estes passos:

### 1. Configurar Variáveis de Ambiente

1. Copie o arquivo de exemplo:
   ```bash
   cp .env.example .env.local
   ```

2. Preencha as variáveis com os dados do seu projeto Supabase:
   ```env
   NEXT_PUBLIC_SUPABASE_URL=your_supabase_project_url
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
   ```

### 2. Executar o Projeto

```bash
npm install
npm run dev
```

O projeto estará disponível em `http://localhost:3001`

## Estrutura do Projeto

### Páginas Disponíveis

- **Dashboard**: `/` - Página inicial
- **Monitoramento**: `/monitoramento` - Visão geral dos dispositivos
- **Tempo Real**: `/monitoramento/tempo-real` - Monitoramento em tempo real
- **Análise**: `/analise` - Dashboard de análises
- **Cadastro**:
  - **Dispositivos**: `/cadastro`
  - **Operadores**: `/cadastro/operadores` (busca tabela `operators`)
  - **Equipamentos**: `/cadastro/equipamentos` (busca tabela `equipament`)
- **Admin**: `/admin` - Configurações administrativas

### Serviços

- **Operadores**: `src/services/operadores.ts` - Gerencia dados da tabela `operators`
- **Equipamentos**: `src/services/equipamentos.ts` - Gerencia dados da tabela `equipament`

### Componentes

- **Sidebar**: `src/components/layout/AppSidebar.tsx` - Navegação lateral com estados preservados
- **UI**: Componentes reutilizáveis em `src/components/ui/`

## Funcionalidades Implementadas

### Sidebar Inteligente
- Preserva estado das seções entre aberturas/fechamentos
- Permite múltiplas seções abertas simultaneamente
- Comportamento responsivo para dispositivos móveis

### Página de Operadores
- Lista todos os operadores da tabela `operators` do Supabase
- Exibe informações: nome, email, telefone, função, status
- Formatação de datas em português brasileiro
- Estados de carregamento e erro
- Botão para atualizar dados

## Tabelas do Banco de Dados

### Tabela `operators`
```sql
CREATE TABLE operators (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR NOT NULL,
  email VARCHAR,
  phone VARCHAR,
  role VARCHAR,
  status VARCHAR DEFAULT 'active',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Tabela `equipament` (ou `equipment`)
```sql
CREATE TABLE equipament (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  -- Adicione os campos conforme sua necessidade
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Desenvolvimento

### Scripts Disponíveis

- `npm run dev` - Inicia servidor de desenvolvimento
- `npm run build` - Gera build de produção
- `npm start` - Inicia servidor de produção
- `npm run lint` - Executa linter

### Estrutura de Pastas

```
src/
├── app/                    # App Router do Next.js
│   ├── (dashboard)/       # Layout do dashboard
│   ├── globals.css        # Estilos globais
│   └── layout.tsx         # Layout raiz
├── components/            # Componentes React
│   ├── layout/           # Componentes de layout
│   └── ui/               # Componentes de UI
├── lib/                  # Utilitários e configurações
│   ├── supabase/         # Cliente Supabase
│   └── utils.ts          # Funções utilitárias
└── services/             # Serviços de API
```

## Status do Projeto

✅ **Concluído:**
- Estrutura base do dashboard
- Sidebar com navegação inteligente
- Página de operadores conectada ao Supabase
- Sistema de build funcional

🔄 **Em desenvolvimento:**
- Funcionalidades de CRUD para operadores
- Interface de edição de dados
- Validações de formulários
