# AURORA IPTV Desktop v0.6.0-beta.15 (candidata)

## Banner ultrawide
- O banner não usa mais crop indiscriminado para cobrir monitores largos. Preserva a imagem ao centro e reflete suas laterais quando há espaço extra, sem mudar sua proporção.
- Mantém toda a largura preenchida, logotipo e textos legíveis, com desenho direto em QPainter.

## Player em tela cheia e controles
- O vídeo passa a iniciar em **Ajustar à tela**, evitando cortar cenas por padrão.
- Controles sobrepostos: retroceder/avançar 10 segundos quando o stream permite seek, reproduzir/pausar, volume, favoritos, proporção, PiP, idiomas de áudio e legendas presentes na mídia, velocidade em mídias sob demanda.
- HUD aparece ao interagir, começa a desaparecer aos 3 s e termina em 5 s; não some enquanto seus menus estão abertos.
- Atalhos Space, F, M, setas e Esc, sem afetar campo de busca.
- Proporção suportada nativamente no Qt Multimedia: ajustar, preencher e esticar. Os modos numéricos 16:9/4:3/2:1/21:9 requerem renderizador que permita forçar pixel aspect ratio e não são anunciados como disponíveis sem suporte.

## Picture-in-Picture
- Janela Qt independente, redimensionável e móvel com Sempre no topo (quando permitido pelo sistema), controles de pausa, som, volume e retorno.
- O **mesmo QMediaPlayer** alterna seu QVideoWidget entre a interface principal e o PiP. Sem segundo stream, player ou áudio; ao retornar, a mídia não é reaberta.
- Wayland pode ignorar sempre no topo; suporte a troca de saída de vídeo depende do backend do Qt e precisa de teste manual nos principais drivers.

## Catálogo e preservação
- Regras de classificação por tipo explícito, caminho, marcadores de episódio, grupo e extensão; conteúdo ambíguo vai para a seção interna **Não classificados**.
- Configurações → Playlists → Revisar conteúdos não classificados, com menu contextual para mover conteúdo para canais, filmes ou séries ou restaurar classificação automática.
- Correções persistem em tabela SQLite própria e sobrevivem à atualização; itens por URL não são duplicados, favoritos/progresso permanecem válidos.
- Reclassificação incremental v6 (lotes de 1200 itens), sem baixar novamente o catálogo original só para migrar.

## Qualidade e compatibilidade
- Testes automáticos Linux/Windows abrangendo PiP, fullscreen, proporção, banner e migração de catálogo.
- Preservam-se as implementações da beta.14: EPG, futebol, placares quando disponíveis, reprodução, sinopses, atualizações e preferências.

**Aviso**: recursos de áudio/legenda dependem das faixas expostas pelo backend multimídia. Não é possível garantir PiP sempre no topo em todos os compositores Wayland nem forçar proporções arbitrárias em QVideoWidget sem mudar o renderizador.
