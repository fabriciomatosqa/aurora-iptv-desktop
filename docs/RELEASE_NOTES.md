# AURORA IPTV Desktop 0.6.0-beta.14

## Acabamento visual e SVGs
- Todos os ícones presentes na interface moderna, inclusive controles de play/pause, favoritos, áudio, tela cheia, banner e placeholders, usam o renderizador QtSvg com correção HiDPI introduzida na beta.13.
- A opção Configurar EPG usa engrenagem, com paleta adequada aos temas claro e escuro.
- A barra de progresso compacta no cabeçalho da agenda comunica a atualização do guia sem inventar porcentagens. Ambos os botões de atualização ficam desabilitados durante a consulta.

## Futebol e busca
- Corrige o problema em que a busca removia o filtro do campeonato selecionado. A mesma correção se aplica a gêneros de Filmes e Séries.
- Mostra um ponto verde pulsante somente durante a faixa de horário de transmissões sinalizadas como ao vivo pelo XMLTV; não afirma que o vídeo está transmitindo efetivamente a partida.
- Preserva as correções da beta.13: confrontos reais associados a canais, sem canais genéricos como partidas; campeonatos disponíveis, busca por time, reprises quando identificadas, horário local HH:mm, retorno de navegação e sinopses quando há metadados.

## Qualidade e compatibilidade
- Testes de regressão específicos para filtros combinados, SVGs, configuração do EPG, carregamento e indicação de ao vivo.
- Validação por Pull Request em Windows e Linux, sem publicação automática antes da integração.
- Mantém playlists M3U/M3U8, banco SQLite, favoritos, progresso, continuar assistindo, player em tela cheia e atualização online.

**Limitações conhecidas:** placares e minutos reais, confirmação independente de que a transmissão do canal está ao vivo, e os escudos/logotipos oficiais de equipes e campeonatos continuam dependentes de integração com fonte esportiva licenciada e identificadores exatos. Esses dados não são inventados. A imagem fornecida pelo próprio XMLTV pode continuar a ser mostrada.

**Atualização:** a partir da beta.13, use Configurações → Atualizações quando a beta.14 estiver publicada. A instalação mantém o banco de dados do usuário.
