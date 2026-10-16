# AURORA IPTV Desktop 0.6.0 beta 6

Beta destinada a testar a atualização online da v0.6.0-beta.5 para a v0.6.0-beta.6.

- A beta 5 corrigiu o problema da janela de progresso Qt que cancelava a operação ao finalizar o download.
- O aplicativo mostra os MB transferidos e verifica o tamanho exato e SHA-256 antes de executar o instalador.
- Após a única autorização, o auxiliar externo aguarda o AURORA encerrar, instala com /VERYSILENT e reabre a nova versão.
- O GitHub Actions testa o download real de um instalador Windows de mais de 40 MB publicado no Releases, sua integridade e a instalação silenciosa.
- O registro local de depuração fica em %LOCALAPPDATA%/AURORA IPTV/updates/update-debug.log, sem playlists ou credenciais.

Para testar: instale a beta 5 por cima da versão atual uma única vez. Abra Atualizações > Verificar atualizações agora e autorize a beta 6. Aguarde o fechamento, a instalação silenciosa e a reabertura automática.

Esta beta não altera a biblioteca IPTV.
