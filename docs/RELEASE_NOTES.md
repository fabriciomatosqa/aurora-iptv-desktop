# AURORA IPTV Desktop 0.6.0-beta.13

## Correções prioritárias
- Corrige a regressão de ícones SVG deformados na beta.12: o QtSvg agora desenha em um retângulo lógico explicitamente dimensionado, evitando o corte em telas de alta densidade. Testes verificam os pixels renderizados, não apenas a validade do SVG.
- Devolve os ícones de Início, TV, Filmes, Séries, Futebol, Favoritos e Configurações ao tamanho correto. Botões menores do EPG também foram corrigidos.
- Botão compacto Atualizar no cabeçalho da agenda. Configuração da fonte EPG permanece na área Configurações.

## Futebol
- Exige partida com dois adversários identificados; não usa a lista genérica de canais esportivos como agenda. Os canais continuam disponíveis em Ao vivo.
- Categorias FIFA, Brasileirão, Libertadores, Sul-Americana e ligas estrangeiras que de fato existam no XMLTV, sem abas vazias.
- Cards com competição, times, dia da semana e mês por extenso, horário local HH:mm, canal e indicador REPRISE quando informado.
- Procura por nome de equipe, mantendo filtro de campeonato. Atualização do XMLTV não interrompe a reprodução e procura preservar busca, categoria e rolagem.
- Quando a fonte XMLTV oferece uma imagem de evento, ela pode ser exibida. Não há imagens fictícias nem certeza indevida de ser o escudo oficial.

## Navegação e sinopses
- Registra contexto de navegação antes de entrar em episódios, podendo voltar à categoria, pesquisa e rolagem de origem.
- Aceita descrição/sinopse em tags de M3U: `description`, `tvg-description`, `synopsis`, `plot`, `summary`, entre outras.
- Armazena sinopse no SQLite com migração segura; mostra texto em janela rolável ou "Sinopse não disponível."
- Preserva playlists, favoritos, progresso, player em tela cheia e atualização automática Windows/Debian.

**Limitação conhecida:** placares/minutos em tempo real e logos oficiais de equipes/competições só poderão ser fornecidos por uma API esportiva confiável/autorizada com identificadores corretos. Ainda não estão integrados nesta versão; não são simulados.

**Atualização:** o app beta.12 deve reconhecer a beta.13 através do sistema de Atualizações existente. Após instalar, teste os SVGs, os botões EPG, o retorno das séries e a janela de sinopse.
