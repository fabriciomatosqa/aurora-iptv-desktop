# AURORA IPTV Desktop 0.6.0-beta.14

## Futebol: placares reais e escudos adaptados do Android
- Integra consultas assíncronas ao placar público disponibilizado pela ESPN, usando apenas campeonato e data, sem compartilhar URLs de playlists ou credenciais.
- Atualiza os resultados enquanto a agenda Futebol está visível, com ciclo de 60 segundos e limite de consultas concorrentes; mantém as partidas carregadas, filtros e posição de rolagem.
- Cruza nome exato das duas equipes, competição e data antes de mostrar placar ou minuto. Partidas com identificação ambígua permanecem sem resultado.
- Adiciona cards com logotipo de competição, escudos separados de mandante e visitante, placar/tempo quando confirmados, canal de transmissão e horário local.
- Para seleções, reaproveita quatro URLs de escudos já usadas no Android (Brasil/CBF, Argentina/AFA, EUA/US Soccer, Espanha/RFEF), com identificação FIFA na competição.
- Mostra o estado do jogo separadamente do estado da transmissão no XMLTV. Nunca afirma que um canal está transmitindo um jogo simplesmente porque ele está acontecendo.
- Em falhas de conexão ou dados indisponíveis, mantém os dados existentes, preserva o catálogo e informa estados ausentes ou desatualizados, sem inventar jogos.
- Em Configurações → Guia de futebol, há opção para ativar/desativar as consultas online de placares e imagens esportivas.

## Interface e regressões
- Padroniza ícones de vídeo, áudio, fullscreen, Favoritos e navegação no mesmo renderizador SVG HiDPI.
- Preserva a categoria e o campeonato ao fazer buscas.
- Padroniza a engrenagem de Configurar EPG, adiciona progresso indeterminado e impede múltiplas atualizações simultâneas.
- Mantém os ajustes da beta.13: partidas identificadas no XMLTV, reprises sinalizadas, horários HH:mm, navegação por histórico e sinopses quando disponíveis.

## Testes e distribuição
- Testes determinísticos para identidade de clubes e seleções, ausência de placares fictícios, fontes HTTPS permitidas, consultas limitadas, privacidade das playlists e atualização dos cards sem perda da seleção.
- Builds Windows e Linux por GitHub Actions; instaladores são publicados após a integração e somente se os testes dos dois sistemas passarem.
- Preserva SQLite, múltiplas playlists, favoritos, progresso, player e checagem de atualização.

**Condições de uso:** o recurso consulta endpoints públicos utilizados no projeto Android, mas isso não é uma licença de exploração comercial. TheSportsDB exige uma assinatura paga para aplicativos publicados em lojas e uma assinatura não transfere direitos sobre os escudos de terceiros. As marcas/logotipos de clubes, confederações e campeonatos também exigem verificação de direitos antes de vender ou distribuir comercialmente o aplicativo. Veja docs/SPORTS_DATA_SOURCES.md.

**Limites técnicos:** nenhuma API confirma automaticamente o conteúdo efetivo do stream IPTV. O aviso de transmissão vem do XMLTV; o placar vem do provedor esportivo. Nem toda competição, jogo ou federação dispõe de imagens e resultados verificáveis.
