# AURORA IPTV Desktop 0.6.0 beta 8

## Debian — atualização pelo próprio aplicativo
- O AURORA encontra o pacote .deb da versão mais nova no GitHub Releases, sem navegar ao site.
- Baixa o pacote completo internamente, com progresso, tamanho exato e validação SHA-256.
- Na instalação Debian padrão, um auxiliar externo aguarda o fechamento do AURORA, solicita autenticação administrativa via PolicyKit (pkexec apt-get install) e reabre o aplicativo.
- Quando PolicyKit não está disponível ou a edição é portátil, abre o arquivo .deb já baixado no gerenciador gráfico de pacotes do Linux.
- Registros de diagnóstico ficam em ~/.cache/aurora-iptv/updates; não armazenamos senhas nem playlists.
- Uma autorização de administrador pode ser solicitada pelo sistema, mas não há necessidade de acessar GitHub manualmente.

## Windows e Linux — tela cheia
- O botão deixa de usar QVideoWidget.setFullScreen(), que podia congelar a imagem, manter o áudio ou prender a interface.
- A janela principal é ampliada sem desconectar/recriar o componente de vídeo.
- O botão "Sair da tela cheia", Esc ou F11 restauram os painéis, a janela e os controles.
- Mantém atualizador silencioso do Windows, favoritos e playlist.

**Teste:** no Linux beta.7 o atualizador antigo ainda abre o GitHub: instale esta beta.8 manualmente uma vez para ativar o novo mecanismo. A próxima beta.9 servirá para testar atualização beta.8 -> beta.9 dentro do AURORA. No Windows, atualize beta.7 -> beta.8 no menu.
