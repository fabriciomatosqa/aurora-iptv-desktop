# AURORA IPTV Desktop 0.6.0 beta 9 — Teste de atualização Debian integrada

Esta beta permite testar o novo fluxo da beta.8 para beta.9, sem precisar acessar o GitHub dentro do aplicativo.

- O AURORA consulta Releases, identifica o .deb de arquitetura amd64, baixa todo o arquivo com progresso e valida tamanho e SHA-256.
- Após autorização do usuário, o aplicativo fecha, um auxiliar externo espera o processo encerrar e solicita privilégios do Debian através do PolicyKit para executar apt-get install do arquivo local.
- O auxiliar reabre o AURORA depois da atualização. O sistema poderá solicitar senha administrativa.
- Caso a autorização PolicyKit falhe, o aplicativo oferece abrir o .deb já baixado no gerenciador de pacotes gráfico, sem visitar o GitHub.
- CI testa o download de um .deb REAL de release anterior, com verificação completa, além dos testes de interface e atualização simulada.
- Tela cheia corrigida em Windows e Linux: o vídeo não é desconectado ao maximizar; Esc, F11 e botão saem da tela cheia.
- Preserva banco, listas, favoritos, progresso e o atualizador silencioso do Windows.

Para testar no Debian: instale beta.8 manualmente por cima da beta.7 uma única vez. Abra Atualizações, escolha Beta e estável, verifique beta.9, autorize e aguarde. O sistema pode solicitar autorização administrativa. Depois o app deve reabrir na beta.9.

Os testes de CI não reproduzem o ambiente PolicyKit e o driver de vídeo de todos os computadores: valide no Debian real.
