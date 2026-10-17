# AURORA IPTV Desktop v0.6.0-171026.01

Esta é a primeira versão que retoma o padrão **v0.6.0-DDMMAA.NN**.
`171026` significa 17/10/2026 e `.01` é a primeira publicação do dia.
No mesmo dia as próximas versões serão `.02`, `.03` etc; amanhã a sequência recomeça em `.01`.

O atualizador preserva as verificações GitHub Releases, o botão ao lado da versão,
a verificação SHA-256 e a confirmação da instalação. A beta.15 publicada antes
desta versão oferece a ponte de compatibilidade para as instalações beta.14,
que só reconheciam tags `beta.N`. No Linux, o pacote de atualização tem
o nome `aurora-iptv_0.6.0-date20261017.01_amd64.deb`: a data ISO no
pacote é necessária para garantir a ordem das versões no sistema Debian.

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

## Atualizações e experiência da interface
- Correção da consulta automática: a beta.14 registrava um prazo de 24h mesmo antes de terminar uma consulta, podendo perder versões publicadas durante o dia.
- A partir desta versão, as verificações bem-sucedidas têm intervalo de até 30 minutos; falhas de conexão permitem uma nova tentativa depois de cinco minutos, sem bloquear por 24h.
- Enquanto o aplicativo estiver aberto, uma verificação automática é agendada a cada 30 minutos. A escolha de canal Beta/Estável é respeitada.
- Novo botão SVG no rodapé, imediatamente à direita da versão, para verificar manualmente atualizações sem abrir Configurações.
- Ícone da ação **Atualizar playlist** com contraste alto em fundo verde/turquesa.
- O painel do player passa a mostrar a sinopse ou descrição disponível do item selecionado quando não houver vídeo em execução. Falta de sinopse é indicada explicitamente; nenhum resumo é fabricado.
- O vídeo e PiP em execução não são substituídos pela sinopse ao navegar; a visualização de resumo retorna ao fechar ou terminar a reprodução.

**Diagnóstico da transição beta.14 → beta.15:** não havia versão beta.15 publicada em GitHub Releases no momento da inspeção. Compilações candidatas do PR não são consideradas versões instaláveis. O aplicativo só pode oferecer uma nova versão depois que o Release com seus instaladores verificados estiver publicado.

## Qualidade e compatibilidade
- Testes automáticos Linux/Windows abrangendo PiP, fullscreen, proporção, banner e migração de catálogo.
- Preservam-se as implementações da beta.14: EPG, futebol, placares quando disponíveis, reprodução, sinopses, atualizações e preferências.

**Aviso**: recursos de áudio/legenda dependem das faixas expostas pelo backend multimídia. Não é possível garantir PiP sempre no topo em todos os compositores Wayland nem forçar proporções arbitrárias em QVideoWidget sem mudar o renderizador.
