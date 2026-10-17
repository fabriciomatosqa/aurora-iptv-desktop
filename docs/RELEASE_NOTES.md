# AURORA IPTV Desktop 0.6.0-beta.11 — Player imersivo e visual Aurora Utils

### Tela cheia
- Elimina bordas, painel, menu e controles externos; o vídeo ocupa toda a janela fullscreen (modo expandir com recorte proporcional em monitores ultrawide).
- O **mesmo** QVideoWidget permanece conectado ao QMediaPlayer, sem reparenting ou segunda saída de vídeo, preservando a continuidade da imagem e do áudio.
- Overlay translúcido sobre o próprio player contém título, barra de progresso, Play/Pause, Favoritar, volume e Sair da tela cheia.
- Ao deixar o mouse parado por 3 segundos, o overlay começa a desaparecer em animação suave. No quinto segundo desaparece totalmente. Movimentar o mouse mostra os controles imediatamente.
- Esc ou F11 restauram a janela; os controles também oferecem botão de saída visível.
- Ícones vetoriais Play, Pause, volume e estrela de quatro pontas Aurora (na posição da reprodução e no controle de volume). Corrigido o antigo texto “Ⅱ Pausar”.

### Cabeçalho Aurora
- Referência visual do Aurora Utils: banner fotográfico de ponta a ponta, logotipo grande à esquerda, tipografia personalizada com degradê aurora, informação de versão e slogan na direita.
- A barra de navegação inicia abaixo do banner, valorizando a imagem.

### Compatibilidade
- Testes Qt automatizados de fullscreen/overlay, duração da animação, ícones e layout em Windows/Linux.
- Atualização automática e silenciosa Windows e atualização Debian com autorização administrativa mantidas.
- Playlists, favoritos, progresso, categorias e EPG não foram alterados.

**Como testar:** na beta.10, selecione Atualizações → Verificar atualizações agora → Atualizar agora; após reiniciar na beta.11, reproduza um vídeo e clique Tela cheia. Aguarde cinco segundos sem mexer o mouse e então mova-o; confirme o desaparecimento e o retorno dos controles, e depois saia com Esc.

Versão beta: a composição de vídeo com controles em sobreposição depende do backend de vídeo Qt e do gerenciador de janelas. Verifique também em seu Windows e Linux reais.
