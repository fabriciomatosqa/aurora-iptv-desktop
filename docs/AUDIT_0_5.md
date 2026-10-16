# Auditoria funcional v0.5.0

Esta revisão inspecionou o parser M3U, SQLite, integração com provedor, player Qt, navegação PySide6, imagens, futebol/EPG, scripts de instaladores e testes de regressão. Android consultado apenas como referência; não modificado.

## Corrigido

- Futebol: filtrar partidas sem canal realmente existente, remover eventos após 1 hora do final, corrigir consulta SQL no SQLite, descartar futebol americano e evitar cards duplicados.
- Catálogo: atualização aditiva e atômica das playlists no Desktop, sem remover títulos ausentes temporariamente; reclassificação versão 5 preservando favoritos e retomada.
- Performance: classificação em thread separada, consulta de capas apenas da página necessária, busca esportiva em todo o catálogo.
- Navegação: continuar assistindo abre episódio recente, busca textual global dentro da classe.
- Player: evitar sobrescrever posição após término e diferenciar erros de rede, codec e acesso.
- Aparência: tela Aurora de espera antes de selecionar transmissão.
- Testes: casos de playlist parcialmente alterada, canal associado, partidas expiradas, modalidades erradas e navegação Qt.

## Pendências identificadas

- Placar ao vivo e escudos de Futebol ainda não têm paridade com Android/FotMob/ESPN.
- Codecs e cabeçalhos especiais do streaming dependem do backend Qt; necessários testes com streams reais no Windows/Linux.
- Controle parental PIN, idiomas, telas de sinopses e faixas avançadas de legenda/áudio continuam incompletos.
- Imagens ainda dependem de URLs do provedor e cache em memória; falta cache em disco e recuperação avançada.
- Importação aditiva pode reter itens permanentemente removidos do servidor; falta política de remoção com consentimento.
- É necessário ensaio com playlist real extensa, telas de diferentes DPI e instalação sobre versões anteriores.
- Os testes automatizados demonstram funções e abertura de interface, mas não substituem verificação manual de playback.

## Entrega

O banco do usuário fica fora da pasta do instalador. O Windows mantém o AppId Inno Setup e o Linux mantém o nome do pacote DEB. Não alteramos o projeto Android nem incluímos playlists, senhas ou tokens no repositório.

Só tratar a release como instalável após ambos os jobs do GitHub Actions finalizarem com sucesso.
