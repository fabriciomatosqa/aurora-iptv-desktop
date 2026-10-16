# Auditoria de paridade: AURORA IPTV Android → Desktop

## Referência

Código-base Android: [fabriciomatosqa/iptv-player](https://github.com/fabriciomatosqa/iptv-player).

Esta documentação registra diferenças técnicas reais para orientar a migração. O Desktop é Python/PySide6/SQLite; o Android é Kotlin/Compose/ExoPlayer. **Não converter APK para .exe**. Não modificar o repositório Android.

## Regras já incorporadas ou adaptadas

| No Android | No Desktop | Observação |
| --- | --- | --- |
| Playlist.kt / classifyContent | android_rules.py + core.py | Mesma hierarquia de hints, endpoints /live/, /movie/, /series/, episódios, grupos e extensões |
| Playlist.kt / M3uParser | core.py | Streaming em lotes; parser tolera campos antes e depois da vírgula, aspas simples e duplas, tvg-id, typeHint |
| ProviderApi.kt | provider.py + catalog.py | Consulta *opcional* à mesma origem Xtream por categoria oficial e capas das séries; uso de tamanhos máximos |
| Series.kt / seriesIdentity | android_rules.py + catalog.py | SxxExx, 2x13, Temporada 02 Ep 11; remove etiquetas de qualidade e agrupa por título |
| MovieCategories.kt | android_rules.py + catalog.py | Normalização de gêneros, recentes, 4K e categorias especiais |
| ContentRules.kt | android_rules.py | Normalização e sinalização de conteúdo adulto; parse de confrontos exige indícios de futebol |
| Guide.kt / GuideModels.kt | catalog.py | XMLTV/GZIP, IDs e nomes, horários locais, replay/live, associação de canais e retenção de partidas |
| PlaylistRepository.kt | core.py + catalog.py | SQLite com conteúdo, favoritos por filme e série, watch progress, playlists múltiplas, paginação por scroll |
| AuroraTheme.kt | modern.py e assets AutoFill | Claro, escuro e automático, bandeira visual Aurora, área de vídeo, logotipo |
| FootballScreen.kt | modern.py | Agenda XMLTV e fallback de canais esportivos, data/hora e indicação de reprise |
| UI de navegação do Android | modern.py | Classes/subclasses/conteúdo e player; mouse, teclado, telas grandes |
| Instalação e atualizações | build_windows.ps1 / build_linux.sh | Mesmo AppId no Windows, mesmo pacote DEB no Linux, SQLite fora da pasta instalada |

## Recursos Android ainda não equivalentes

| Recurso | Situação Desktop | Próxima abordagem |
| --- | --- | --- |
| FotMob/ESPN, placares, estados LIVE/HALFTIME/FINISHED e reconciliação de horários | **Ainda ausente** | Reaproveitar parsers FotMobScores.kt, FootballScores.kt, FootballScoreRepository.kt, com cache e limites |
| Logos dos times e competições | **Parcial** | Resolver equipes exatamente, sem atribuições de imagens aproximadas |
| EPG dos demais canais (Agora / Próximo) | **Parcial** | Indexar guia por canal para mostrar programação ao vivo |
| Sinopses de filmes, séries e episódios por Xtream | **Ausente** | Portar SynopsisRepository.kt e cache com correspondência por ID |
| Catálogo completo de capas para animes | **Parcial** | Portar ArtworkResolver.kt + Kitsu com comparação exata e limites |
| Metadados mais amplos de provider (ids de VOD) | **Parcial** | Associar streams por IDs sem expor credenciais |
| Controles avançados de áudio, legendas e faixas | **Parcial** | Estudar APIs de trilhas do Qt Multimedia ou player alternativo |
| Recuperação de playback após erro e codecs | **Parcial** | Teste real no PC, ajustar backends/mecanismos de fallback |
| Classificação indicativa e PIN parental | **Ausente** | Portar proteção de conteúdo sensível sem expor credenciais |
| Idiomas suportados no Android | **Ausente** | Traduções Qt e seleção de idioma |
| ETag, If-Modified-Since e importação diária aditiva | **Ainda simplificado** | Tornar atualização incremental sem apagar itens fora de guia |
| Arquivos temporários/cache resistentes a quedas | **Parcial** | Validar atomicidade, migrações e testes de força-interrupção |
| Grid visual e fichas de conteúdo mais detalhadas | **Parcial** | Aproveitar organização de telas MainActivity.kt e SynopsisScreen.kt |

## Observações de segurança e confiabilidade

- O aplicativo não inclui playlists nem credenciais; nunca publicar URLs privadas no repositório.
- A consulta de categorias e cartazes Xtream é feita no **mesmo host da playlist**, como no Android. Capas podem vir de um CDN indicado pelo próprio provedor.
- As URLs dos conteúdos são a identidade para preservar favoritos e progresso, mesmo durante migrações de classificação.
- O SQLite do usuário permanece na pasta de dados do sistema, separada do instalador; evitar qualquer drop sem backup.
- Não presumir que a API de metadados, XMLTV ou codecs vai estar disponível em todo provedor.
- A agenda de futebol não deve inventar horários, gols, times nem relacionar canais que não sejam da playlist.
- Testes Qt *offscreen* e compilações CI não substituem testes de uso real com Windows e Linux.

## Próximo ciclo

1. Consolidar a migração de classificação e categorias, validando com playlist grande e dados já cadastrados.
2. Portar resultados FotMob/ESPN, parser de EPG geral e correspondência de canais sem falsos jogos.
3. Portar sinopses/metadados avançados, área de detalhes e controles de faixas.
4. Evoluir layout para o mesmo nível de organização e legibilidade do Android, preservando componentes próprios do Desktop.
5. Testar em Windows e Linux reais e disponibilizar instaladores para atualizar por cima da versão anterior.
