# AURORA IPTV Desktop 0.6.0 beta 3

Correcao do fluxo de atualizacao silenciosa no Windows:

- Remove "Historico de versoes" do menu Atualizacoes (os Releases antigos permanecem preservados no GitHub).
- Ao aprovar uma atualizacao: baixa todo o instalador, verifica SHA-256, fecha o AURORA, aguarda a saida do processo, instala sem assistente e reabre a nova versao automaticamente.
- Usa um auxiliar PowerShell separado da pasta instalada para nao bloquear a substituicao do executavel.
- Grava status e log na pasta de atualizacoes para diagnosticar falhas; apresenta o resultado quando o AURORA reabre.
- Mantem as playlists, favoritos e configuracoes locais.
- E uma versao beta: avisos de seguranca do Windows nao podem ser ignorados automaticamente.

Como a beta 2 tem problema no atualizador, instale a beta 3 uma vez pelo GitHub. Teste a atualizacao beta 3 -> beta 4 pelo proprio aplicativo quando a proxima beta estiver disponivel.
