# AURORA IPTV Desktop 0.6.0-beta.15

## Banner ultrawide
- Fundo panorâmico composto: imagem original sem corte central, com extensão atmosférica lateral e gradientes harmonizados. Largura completa sem distorção ou zoom forçado e sem recalcular arquivos durante o resize.

## Reprodução
- Tela cheia mantém o QMediaPlayer e a saída primária; HUD dividido em comandos superiores, centrais e inferiores, com recolhimento suave entre 3 e 5 segundos.
- Controles de avançar/voltar 10s apenas para VOD realmente navegável; áudio e legendas apenas com faixas retornadas pelo Qt; velocidade do player sob demanda, indicador de carregamento e atalhos F/M/setas com proteção a campos de texto.
- Proporção disponível no QVideoWidget: Original/Ajustar à tela, Preencher e Esticar. As proporções fixas 4:3, 16:9, 2:1 e 21:9 **ainda dependem de um renderizador próprio** e não são oferecidas como botões fictícios.
- Picture-in-Picture abre janela independente, redimensionável, com Always on Top opcional, controles de áudio e retorno. Usa o **mesmo QMediaPlayer**, alterando apenas o alvo de vídeo; o backend Qt pode introduzir uma breve renegociação na troca de superfície em determinados sistemas.

## Biblioteca e dados
- Prioridade: tipo explícito, metadados da categoria do provedor, URL e marcações de episódios, grupo/EPG e somente depois regras genéricas.
- Entradas ambíguas vão à nova seção “Não classificados”, sem serem apresentadas como TV.
- Correção manual de tipo pelo menu de contexto, salva por URL na tabela `classification_overrides` e restaurada após reimportação; preserva favoritos, histórico, progresso e arquivos M3U originais.
- Migração aditiva de classificação v6; processamento por lotes, sem alterar as chaves do conteúdo.

## Verificação e limitações
- Testes para catálogo sem duplicação, migração, SVG, banner, controle PiP, HUD e compatibilidade de chamadas Qt em GitHub Actions Windows e Linux.
- A integração e o comportamento final dependem dos codecs, plugins Qt Multimedia, driver de vídeo, gerenciador de janelas e permissões X11/Wayland. A opção “Sempre no topo” não pode sobrepor restrições impostas pelo compositor.
- A versão publicada não altera o conteúdo nem as credenciais das playlists.

