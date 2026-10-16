# AURORA IPTV Desktop 0.6.0 beta 5

Atualização importante do instalador automático Windows.

## Falha encontrada e corrigida
O diálogo QProgressDialog de download era fechado com close(), que pode disparar o evento canceled(). Como o código interpretava isso como cancelamento do usuário, descartava o instalador já verificado e deixava o AURORA aberto na versão anterior.

## Novo comportamento
- Ao autorizar, baixa o EXE inteiro do GitHub Releases, mostra MB recebidos e valida bytes + SHA-256.
- A barra fica em 99% até a integridade ser confirmada, só então mostra 100%.
- Ao finalizar o download, desativa o botão Cancelar, oculta o diálogo sem emitir canceled e aciona o auxiliar externo.
- O auxiliar espera o aplicativo encerrar, executa Inno Setup /VERYSILENT e reabre o AURORA.
- O arquivo update-debug.log na pasta LOCALAPPDATA/AURORA IPTV/updates informa cada fase e a duração real de download, sem URLs privadas.
- Erros de download e integridade são informados explicitamente; sem iniciar instalação de arquivo inválido.
- O histórico não aparece no menu, mas Releases antigos continuam preservados.

Esta beta serve de base de teste. Instale a beta 5 manualmente apenas uma vez; depois teste beta 5 para beta 6 dentro do aplicativo. Os testes automatizados não dispensam confirmação com seu Windows.
