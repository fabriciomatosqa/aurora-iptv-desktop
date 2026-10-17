# Fontes esportivas — AURORA IPTV Desktop

## Implementação
O Android é a referência técnica, com fontes em `FootballScoreRepository.kt`, `ArtworkResolver.kt` e `NationalTeams.kt` do repositório `fabriciomatosqa/iptv-player`. O Desktop usa `aurora_desktop/sports_data.py` e `aurora_desktop/football_widgets.py`.

- **ESPN:** a versão beta consulta os endpoints de placares por competição e dia, extrai placar, tempo e links para imagens de times e ligas quando disponíveis. As chamadas passam somente campeonato e data. Não enviam endereços dos canais nem credenciais das playlists.
- **TheSportsDB:** somente as URLs das imagens das quatro federações já referenciadas no aplicativo Android (Brasil, Argentina, EUA, Espanha) são usadas como referência/fallback. A versão Desktop NÃO faz buscas com a chave pública gratuita `123`.
- **XMLTV:** única fonte de informação sobre horário do canal e possíveis marcações de `AO VIVO` e `REPRISE`. O status real da partida e o status de transmissão nunca são confundidos.
- **Sem metadados confiáveis:** mostrar ícone vetorial neutro e texto `X`, nunca escudos arbitrários ou `0 X 0` fictício.

## Segurança e estabilidade
- Apenas URLs de imagem HTTPS dos hosts `a.espncdn.com` e `r2.thesportsdb.com` entram no carregador de escudos; URLs privadas de playlists não são incluídas.
- Respostas são limitadas em tamanho e tempo; máximo 12 consultas por ciclo e três requisições concorrentes.
- Atualização a cada 60 segundos **quando a agenda está aberta**, em thread separada.
- Sem alterar reprodução, favoritos, banco de dados ou posição de rolagem.
- Atualização com a seção preservada; estado da partida só é exibido se duas equipes e competição combinarem, em uma janela horária limitada.
- A opção em Configurações > Guia de futebol permite desligar a consulta externa; `AURORA_SCORE_OFFLINE=1` também bloqueia buscas.

## Direitos e distribuição comercial
**Implementação não significa que a fonte esteja licenciada para venda.** Em 17/10/2026, os termos da TheSportsDB indicam assinatura paga para apps publicados nas lojas, respeito às licenças específicas das imagens e ausência de autorização automática de marcas/logos de terceiros.

Fonte: https://www.thesportsdb.com/docs_terms_of_use.php

Antes de vender/publicar em lojas: obter autorizações aplicáveis e verificar os termos atuais das APIs e de cada logotipo, ou substituir imagens sem licença por ícones neutros. A configuração atual é adequada a testes técnicos; não representa auditoria nem autorização jurídica.

**Importante:** as imagens são carregadas diretamente dos provedores, sem redistribuição de arquivos de fontes, fotografias ou logos incluídos no instalador.
