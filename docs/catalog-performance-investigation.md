# Investigação de catálogos — 2026-11-01

Estado: entrega parcial. A melhoria medida nesta revisão é exclusiva do Desktop.
Não há demonstração de que o objetivo completo das três plataformas foi atingido.

## Fontes e bases

Repositórios clonados integralmente; branches remotas e PRs abertos consultados pelo conector GitHub antes das alterações.

- Android main: `ef5fe30ceb49fd98b741abece72a2fb8108381bf`. Já incorpora comparação em lotes e atualização incremental. PRs abertos 18, 23, 26, 32 e 40 não foram integrados automaticamente.
- Desktop main: `165150ccec85348744dbfc7123772608fda4505a`. PR #2 aberto e em conflito; alterações locais partem da main, sem remover recursos do PR.
- TV: main é uma prévia incompleta. Cadeia inspecionada: #1 → #2 → #3 → #4 → #5. Cópia local na head do #5, `6b9ef0ea16fd8b3fd414132a1a3e4b0ae08dd746`. Sem integração nem publicação.
- Android AGENTS.md lido. Nenhum commit, push, release ou mudança de versão realizado.

## Gargalos comprovados

No Desktop, 10 mil itens sintéticos com IDs de provedor e três tipos de conteúdo:

| Operação | Antes | Depois |
|---|---:|---:|
| Primeira importação | 1,176 s | 1,221 s |
| Reabrir banco e consultar 48 canais | 0,010 s | 0,007 s |
| Reimportar lista idêntica | 31,137 s | 0,999 s |
| Reimportar com dois registros adicionais, sob cProfile | 32,744 s | 2,878 s |

Uma execução por configuração; sem intervalo de confiança. São tempos de operações locais, não tempos de interface, reprodução ou rede. O cenário de dois registros do benchmark mistura os tipos em rotação; o teste de regressão separado usa exatamente episódios 16 e 17.

O perfil inicial de atualização de 10 mil itens atribuiu 30,606 s às chamadas SQLite e 1,346 s à classificação. O rastreamento identificou `CREATE TEMP TABLE key_remaps AS ...` como responsável por cerca de 30,6 s.

O EXPLAIN mostrou que a junção consultava `idx_items_tvg` somente por playlist em vez de procurar pelo ID. O índice parcial `(playlist_id,xui_id) WHERE xui_id<>''` já existia, mas a consulta não explicitava a condição necessária. Adicioná-la preserva a semântica: a tabela de IDs únicos já exclui IDs vazios.

A classificação paginada também usava uma ordenação temporária por lote. O índice de playlist, cuja chave implícita inclui rowid, permite avançar pelo rowid sem ordenar repetidamente o catálogo inteiro.

## Implementação

- Predicados explícitos de ID não vazio na reconciliação.
- Índices temporários para ID do provedor, chaves de entrada e IDs únicos.
- Índice persistente não destrutivo por playlist para lotes em ordem de rowid.
- Preservadas transações, regras de classificação, deduplicação e identidade, favoritos, progresso, dados antigos e modos de importação.
- A classificação completa ainda ocorre após cada importação. Não foi removida: pode depender de evidência agregada dos grupos e de metadados do provedor.
- O novo índice persistente exige uma construção única ao abrir um banco antigo. Remover apenas esse índice do banco sintético concluído com 600.002 itens e reabrir LibraryV2 levou 0,316 s para a inicialização que o recria. Uma medição, sem interface Qt. Os números de reabertura abaixo são posteriores à criação do índice.

## Validação realizada

24 testes Desktop distintos selecionados passaram: core, classificação v7, paridade de provedor, regressões críticas e novos testes de índices/sincronização.

O novo teste verifica ausência de escritas de itens numa atualização idêntica, dois episódios novos, troca de URLs sem duplicação ou perda de favoritos/progresso, persistência após reabertura, ausência de ordenação temporária na consulta de lotes e rollback após interrupção da leitura.

Outro teste bloqueia a leitura da fonte num trabalhador após iniciar a transação e confirma que uma segunda conexão lê o catálogo salvo antes de liberar a importação. Isso comprova leitura concorrente no banco desse cenário, não reprodução ou responsividade Qt.

TV: 40 testes Node passaram na branch mais recente. Empacotamento de pastas LG/Tizen passou. Não gera IPK/WGT assinado e não certifica reprodução em TV.

Android: sem alterações ou compilação. JDK, SDK e emulador não disponíveis nos caminhos verificados. A inspeção confirma ETag/Last-Modified, retorno 304, parser em fluxo, hash do corpo e atualização em segundo plano após inicialização. Não se deve implementar de novo esses recursos.

## Arquitetura restante proposta

Prioridade: índice persistido utilizável antes de qualquer operação remota. Medir separadamente abertura do banco, migrações, primeira página, primeira interação, início/fim da sincronização e reprodução durante atualização.

Android: medir `restore`, migração de favoritos, carregamento do guia e overview antes de mudar a ordem de inicialização. Separar migração necessária de manutenção adiável, preservando controle parental e identidade. Não alterar FULL nem compressão sem medições e testes de integridade.

Desktop: medir interface Qt e contenção durante atualização; adicionar validação HTTP persistida com commit dos validadores somente após snapshot válido; reclassificar apenas conjuntos afetados sem perder a evidência agregada dos grupos. O parser e a staging continuam recebendo a lista inteira quando ela muda; delta de escrita não equivale a delta de transferência ou interpretação.

Bloqueio visual encontrado em `modern.py::_refresh`: quando a playlist não pertence ao conjunto `_indexed` do processo, a interface limpa resultados e grupos e retorna antes de mostrar a lista. Isso ocorre mesmo com catálogo persistido. Não foi alterado nesta revisão, pois faltam testes Qt de navegação, controle parental e migração. Verificar também regravações quando a classificação final do provedor ou uma correção manual difere da classificação do parser.

TV: `catalog-db.mjs` guarda cada catálogo como um único valor IndexedDB; `hydrateCatalogs` carrega todos os catálogos/guias e reclassifica antes da renderização final. Migrar de forma retomável para itens individuais, índices por playlist/tipo/grupo/série, paginação por cursor e resumo persistido. Carregar primeiro a playlist ativa e adiar guias, playlists inativas e enriquecimento. Worker/streaming para importação; preservar catálogo anterior até commit da geração nova. Apenas reduzir o número de cards no DOM não resolve o consumo de memória do catálogo completo.

Xtream: séries e temporadas sob demanda, quando a API permitir, com cache por identidade estável. Em M3U sem API de delta, dois episódios novos podem exigir reler a resposta inteira; somente ETag/Last-Modified/304 confiáveis permitem evitá-la quando não mudou.

Metas propostas, ainda não validadas na interface: primeira página local até 500 ms no Desktop e até 2 s em smartphone/TV modestos; navegação e reprodução disponíveis durante toda a atualização; zero escritas em itens inalterados. Registrar hardware e usar várias repetições antes de aprovar essas metas.

## Concorrentes: evidência pública versus hipóteses

- [VU IPTV Player](https://vuiptvplayer.com/) anuncia M3U e Xtream. Não fornece evidência pública suficiente sobre banco, cache ou tempos comparáveis.
- [PLAYSIM PLAYER, pacote playsim.tv](https://play.google.com/store/apps/details?id=playsim.tv) declara M3U/Xtream e sincronização eficiente. Há apps com nomes semelhantes; não foi confirmado que esse pacote é o usado pelo solicitante.
- [IPTV Smart Pro, termos do aplicativo](https://iptv-web.iapplabz.co.in/terms) descreve conteúdo do usuário e Xtream; [FAQ de produto com nome semelhante](https://iptvsmartproplayer.com/faqs) não permite confirmar identidade exata nem arquitetura interna.
- Cache-first, índices e detalhes sob demanda são propostas para Aurora, não fatos observados sobre código proprietário.
- Sem benchmark controlado dos concorrentes, instalação em dispositivos ou fonte remota de demonstração. Nenhuma alegação de superioridade.

## Pendências

Baseline dos tamanhos grandes; memória máxima, CPU, bytes de rede e armazenamento; tempos reais de interface e reprodução; rede offline e falhas HTTP em integração; URLs alteradas em todos os tamanhos; testes Android instrumentados; Qt GUI e executáveis Windows/Linux; TV física modesta; Android TV/Tizen/webOS e migração IndexedDB; classificação incremental e atualização HTTP Desktop/TV. A abertura local medida não comprova responsividade durante uma sincronização concorrente.

Não publicar como solução completa sem essas validações. As alterações locais estão preparadas para revisão, sem commit/push.

## Escala após a alteração (resultados disponíveis)

| Registros | Importação inicial | Reabrir + 48 canais | Lista idêntica |
|---|---:|---:|---:|
| 10.000 | 1,221 s | 0,0069 s | 0,999 s |
| 100.000 | 13,508 s | 0,0070 s | 12,116 s |
| 300.000 | 43,291 s | 0,0051 s | 40,658 s |
| 600.000 | 90,521 s | 0,0066 s | 87,855 s |
| 1.200.000 | 188,080 s | 0,0068 s | 459,722 s |

300 mil: a primeira execução instrumentada não produziu JSON final. A repetição sem profiler concluiu todas as etapas do benchmark atual: primeira importação 43,291 s, reabertura 0,0051 s, atualização idêntica 40,658 s e dois registros adicionais 42,255 s. Pico do processo: 51.314.688 bytes. Isso não cobre a matriz completa de testes solicitada (URLs alteradas, offline, dispositivos e interface em cada tamanho).

1,2 milhão: execução sem cProfile. Pico do working set do processo até a reabertura: 44.949.504 bytes (aproximadamente 42,9 MiB), incluindo o gerador/parser e rastreamento SQL, sem interface Qt, imagens ou player. CPU da importação inicial: 183,25 s. Essa medição não é o consumo do aplicativo completo.

A atualização idêntica de 1,2 milhão consumiu 184,05 s de CPU apesar de 459,72 s de parede. O rastreamento registrou um intervalo de 271,9 s ao redor de uma inserção na staging; isso pode incluir espera e execução entre callbacks e não é uma medição isolada de latência de disco. Causa não estabelecida. Repetir com ambiente controlado antes de usar como previsão de desempenho. Pico do processo até esse ponto: 48.807.936 bytes.

A atualização seguinte com dois registros adicionais, sem profiler, concluiu em 430,252 s de parede e 184,48 s de CPU. Pico final do processo: 51.486.720 bytes (49,1 MiB). Portanto, a meta de atualização barata com delta pequeno NÃO foi atingida no catálogo de 1,2 milhão. Poucas escritas finais não evitam ler, interpretar, comparar e classificar o snapshot inteiro.

Durante a importação seguinte, uma segunda conexão consultou o snapshot salvo com 1,2 milhão de itens. As operações reais de `LibraryV2` levaram: categorias de canais 0,660 s, primeira página de 48 canais 0,021 s; categorias de filmes 0,060 s, primeira página de filmes 0,0024 s; categorias de séries 0,080 s, primeira página do diretório agrupado de séries 0,914 s. Uma medição, com concorrência e caches do sistema; sem interface. Isso distingue a consulta simples de episódios de uma consulta agrupada do diretório de séries.

100 mil e 600 mil: atualização com dois registros adicionais instrumentada pelo cProfile levou respectivamente 29,793 s e 195,654 s. O profiler acrescenta custo relevante; esses valores não devem ser comparados com execução sem profiler como se fossem o mesmo método.

Reprodução: instalar requirements.txt e executar `python benchmark_catalog.py --size 10000 --output resultado.json`; usar `--profile` apenas para diagnóstico. O script cria dados sintéticos locais e não acessa provedores. Testes de regressão: `python -m pytest tests/test_core.py tests/test_catalog_reclassification_v7.py tests/test_provider_parity.py tests/test_critical_regressions.py tests/test_catalog_sync_indexes.py`.
