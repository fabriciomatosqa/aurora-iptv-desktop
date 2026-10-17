# AURORA IPTV — Desktop 0.6.0-171026.03

Player IPTV para **Windows e Linux** em PySide6/Qt Multimedia e SQLite. Repositório independente do [AURORA IPTV Android](https://github.com/fabriciomatosqa/iptv-player). **Nenhum conteúdo, playlist ou credencial incluídos.**

## Padrão de versões e atualização automática

O formato oficial voltou a ser `vMAJOR.MINOR.PATCH-DDMMAA.NN`. Exemplo:
`v0.6.0-171026.01` identifica a primeira publicação de **17/10/2026**;
no mesmo dia, use `.02`, `.03` etc. No dia seguinte, a sequência volta para `.01`.
O GitHub Releases, o instalador e a interface usam a mesma versão central de
`aurora_desktop/__init__.py`. Tags antigas `v0.6.0-beta.N` continuam reconhecidas.

Para não interromper instalações beta antigas, a beta.15 serve como versão
de transição, permitindo descobrir as novas tags datadas. Cada publicação
depende de aprovação dos testes Windows e Linux e de instaladores com SHA-256.

## v0.6.0-beta.14 — SVGs do player, filtros combinados e EPG

- Ícones de player, volume, tela cheia, favoritos e demais controles convertidos para SVG Qt de alta densidade.
- Pesquisa dentro de um campeonato ou gênero preserva o filtro selecionado.
- EPG usa engrenagem correta nas Configurações, barra de atualização indeterminada e botões desabilitados enquanto o guia carrega.
- O marcador verde de **AO VIVO conforme EPG** pisca apenas quando a programação identifica a transmissão dentro do horário atual; isso não confirma a imagem reproduzida.
- Ampliação dos testes automáticos em Windows e Linux.

**Ainda pendente:** placares/minutos em tempo real e escudos oficiais. Uma integração confiável e com direitos de uso adequados será necessária; não há dados esportivos fictícios.

## v0.6.0-beta.15 — banner panorâmico, player avançado, PiP e catalogação

- **Banner:** imagem principal inteira com extensão lateral refletida para ultrawide, sem zoom excessivo.
- **Player:** HUD em tela cheia com botões SVG centrais, 3–5 s de visibilidade, áudio/legendas disponíveis, proporção ajustar/preencher/esticar, velocidade de VOD e atalhos.
- **PiP:** janela independente redimensionável (Windows e Linux), um só player e áudio, retorno sem reiniciar a URL; modo sempre no topo quando o compositor permitir.
- **Catálogo:** classificação por metadados e caminho, seção interna para itens incertos, correção manual por item persistida e reclassificação incremental sem duplicações.
- Limites de proporções fixas e de sistemas gráficos estão registrados em [notas desta versão](docs/RELEASE_NOTES.md).

## v0.6.0-beta.14 — fontes esportivas aproveitadas do Android

- **Placar e minuto de partida:** ESPN consultada fora da interface; atualização enquanto a agenda está aberta (60 s), sem enviar URLs ou credenciais de playlists.
- **Cards com três imagens:** logotipo da competição e escudos separados das duas equipes, carregados de forma assíncrona com fallback vetorial.
- **Seleções:** CBF, AFA, US Soccer e RFEF, com referências usadas no Android e logotipo FIFA quando o jogo corresponde a seleções. Outras federações dependem de imagens obtidas e identificadas com segurança.
- **Sem resultados falsos:** exige identidade confiável de ambas as equipes, campeonato e data. Não inventa 0 X 0, placar, horário ou escudo.
- **Jogo x transmissão:** placar ao vivo não significa que o canal está transmitindo; a programação do canal continua sendo informada apenas pelo EPG.
- **Configurações → Guia de futebol:** opção para desativar consultas externas e imagens esportivas.
- **Regressões resolvidas:** ícones SVG, pesquisa preservando a categoria selecionada, botões compactos e progresso do EPG, histórico e sinopses.
- Consulte [fontes e condições de uso](docs/SPORTS_DATA_SOURCES.md).

**Atenção para comercialização:** os provedores e titulares dos escudos possuem regras próprias. A TheSportsDB exige plano pago para distribuição nas lojas, e logos de clubes/seleções podem demandar autorização. O código implementado é uma integração técnica beta, não uma licença comercial.

## v0.6.0-beta.13 — correção SVG, Futebol, histórico e sinopses

- **Correção definitiva dos SVGs incompletos**: o renderizador QtSvg usa agora o viewport lógico explícito no pixmap de alta densidade. O ícone preenche sua área normal em Windows/Linux. Testes percorrem os pixels dos ícones para detectar cortes.
- Menu lateral e ações do EPG utilizam imagens vetoriais nítidas; o ícone dourado de Favoritos volta a aparecer.
- **Futebol sem canais genéricos misturados**: agenda só mostra partidas identificadas com dois adversários e canal correspondente. Quando não há EPG, canais esportivos continuam em Ao vivo.
- Novo botão compacto Atualizar perto do título da agenda, com desativação e feedback enquanto atualiza; Configurar EPG permanece em Configurações → Guia.
- Categorias priorizam FIFA, Brasileirão, Libertadores e Sul-Americana, sem criar abas vazias; demais ligas são exibidas pelo nome informado no EPG.
- Cards apresentam competição, confrontos, data em português, horário local de 24 h, canal e identificação de reprise. Imagens de evento só são usadas quando o próprio XMLTV fornecer uma URL válida.
- Busca parcial por equipe e preservação de campeonato/pesquisa/rolagem após atualização do EPG.
- Histórico de navegação salva categoria, busca e rolagem ao entrar em episódios e restaura ao Voltar.
- Sinopse rolável para filmes, séries e episódios extraída dos metadados M3U, com fallback **Sinopse não disponível**. Migração SQLite preserva favoritos e progresso.
- Tela cheia, atualização silenciosa Windows e instalação Debian com permissões mantidas.

**Limitação:** placares/minutos em tempo real e escudos oficiais de todos os times **não são prometidos nesta beta**. Exigem uma fonte esportiva autorizada e o mapeamento correto das equipes. Nenhum placar é inventado.

## v0.6.0-beta.12 — preferências integradas e ícones SVG

- O menu superior Aparência / Playlists / Atualizações foi removido e **todas as opções migraram para Configurações**.
- Configurações traz quatro seções na navegação por categorias: Playlists (playlist ativa, adicionar URL, importar M3U, atualizar e editar pela lista), Aparência (sistema/escuro/claro), Atualizações (versão instalada, canal estável/beta e verificar novas versões) e Guia Futebol (configurar e atualizar EPG).
- A checagem automática continua acontecendo na abertura, e a atualização interna Windows/Linux não foi alterada.
- Banner da aurora percorre **toda a largura** do topo, com arte mais aparente e menos elementos competindo no canto direito.
- Menu lateral com altura ligeiramente maior, ícones genuinamente **SVG vetoriais** e cores/espessura uniformes.
- Botões inferiores de navegação, importar e atualizar também receberam SVG, substituindo símbolos de texto.
- Mensagem "Luzes da aurora, seu universo" removida. A versão `DESKTOP / v0.6.0-beta.12` aparece no canto inferior direito da barra lateral, em lugar do antigo rótulo superior.

## v0.6.0-beta.11 — player imersivo e topo inspirado no Aurora Utils

- **Tela cheia sem bordas:** a janela inteira vira o player; menus, painéis, margens e barras de ações normais desaparecem. O renderizador de vídeo permanece o mesmo para evitar congelamento da imagem.
- **Controles em overlay:** barra de progresso, play/pause, favorito, volume e saída da tela cheia ficam sobre o vídeo; não ocupam uma faixa abaixo da imagem.
- **Ocultação progressiva:** após 3 s sem movimento do mouse os controles começam a desaparecer; aos 5 s ficam totalmente ocultos. Mova o mouse para trazê-los de volta.
- **Ícones vetoriais:** play, pause (sem “Ⅱ”), alto-falante, expandir/sair e a estrela Aurora nos controles de progresso e volume.
- **Ultrawide:** na tela cheia o vídeo pode ser ampliado com recorte proporcional para eliminar barras laterais pretas. Ao voltar, recupera a proporção original.
- **Novo topo AURORA:** referência visual do Aurora Utils, com imagem da aurora de ponta a ponta, logo maior e título em degradê ciano/azul/roxo.
- **Atalhos:** Esc e F11 saem do modo tela cheia. Nenhuma alteração na base de playlists, favoritos, EPG, atualizador Windows ou atualizador Debian.

Atualize de beta.10 para beta.11 pelo menu **Atualizações**. O aplicativo deve instalar e reabrir normalmente, como antes.

## v0.6.0-beta.10 — novo topo Aurora integrado

- Banner principal **de ponta a ponta** na área superior, sem seletor de playlist ocupando espaço ao lado.
- Imagem aurora recortada sem distorção, cantos suaves, sobreposição em degradê para boa leitura e detalhes de brilho em ciano/roxo; acompanha a largura da janela.
- Hierarquia visual refinada: identidade AURORA / IPTV, subtítulo e identificação discreta da versão beta, diretamente sobre o banner.
- **Playlist ativa movida para Configurações → Playlists**, preservando a mesma instância do seletor, os dados e a lógica de mudança entre bibliotecas.
- A troca de playlist dentro das Configurações não fecha a página nem interrompe o fluxo de gerenciamento.
- Testes Qt de cabeçalho responsivo e de troca de playlist, sem alterações ao motor de reprodução ou ao sistema de atualização Windows/Linux.

Atualize da beta.9 pelo menu **Atualizações** do AURORA; ele deve baixar, instalar e reabrir automaticamente como nas versões anteriores. Os dados de playlist, favoritos e retomada continuam na pasta do usuário.

## v0.6.0-beta.9 — teste de atualização integrada Debian

- Atualização de teste **beta.8 → beta.9** via download do .deb diretamente no AURORA.
- O GitHub Actions baixa um pacote Debian **real** das versões anteriores e valida tamanho completo, formato e SHA-256.
- Se a autenticação PolicyKit for recusada ou indisponível, o AURORA oferece abrir o arquivo .deb já baixado no instalador gráfico local, sem acessar o GitHub.
- Corrige a tela cheia tanto no Windows quanto no Linux sem criar outra superfície de vídeo. Sair: Esc, F11 ou botão.

## v0.6.0-beta.8 — atualizações Debian e tela cheia sem travar

- Debian: detecta o pacote `.deb` correto no GitHub Releases, baixa dentro do AURORA com tamanho e SHA-256 verificados, solicita autenticação PolicyKit e instala após fechar o app; em seguida reabre automaticamente.
- Sistemas sem PolicyKit ou instalações portáteis: o AURORA abre o pacote `.deb` baixado no gerenciador de pacotes local, sem precisar acessar o GitHub.
- Windows: mantém atualização silenciosa comprovada.
- Windows e Linux: a tela cheia expande o **aplicativo**, não cria outra janela de `QVideoWidget`; Esc, F11 e um botão visível permitem voltar ao normal.
- Testes Qt automatizados garantem que o mesmo player seja mantido e que o modo tela cheia seja reversível.
- A migração inicial da beta.7 para beta.8 no **Debian** pode exigir instalar o arquivo manualmente uma última vez, pois a beta.7 não tem o novo instalador. O teste completo será beta.8 → beta.9.

## v0.6.0-beta.7 — identidade visual Aurora

- Menu lateral com ícones vetoriais nítidos de casa, TV ao vivo, cinema, séries, futebol, Favoritos (estrela amarela) e Configurações.
- Removidas as faixas pretas indesejadas de títulos, subtítulos e barras por meio de uma folha de estilos unificada.
- Painéis azul-petróleo, estados de seleção/hover mais suaves, barras e botões visualmente consistentes.
- Capas de fallback por tipo de mídia e player adaptado a temas claro/escuro.
- Testes automatizados da interface e manutenção do atualizador silencioso corrigido.

**Para atualizar da beta.6:** dentro do programa, use Atualizações → Verificar atualizações agora → Atualizar agora. Ele deverá fechar, instalar silenciosamente e reabrir com a beta.7.

## Atualizações online e controle de versões

**Baixe as versões oficiais em [GitHub Releases](https://github.com/fabriciomatosqa/aurora-iptv-desktop/releases).**

Para testar o atualizador corrigido e a transferência integral verificada por SHA-256: instale a beta.5 por cima da versão atual apenas uma vez. Depois teste beta.5 → beta.6 no menu Atualizações, sem assistente de instalação. O aplicativo deverá baixar e verificar o EXE completo, fechar, instalar silenciosamente e abrir novamente. O progresso agora mostra os MB transferidos, e o registro local fica em `%LOCALAPPDATA%\\AURORA IPTV\\updates\\update-debug.log`.
No Windows:
1. Abra Atualizações > Verificar atualizações agora. O sistema também verifica automaticamente, em intervalos de 24 h.
2. Confira a versão instalada e a mais recente. Clique em Atualizar agora.
3. O AURORA baixa o instalador oficial, valida o SHA-256 e encerra a aplicação.
4. Um auxiliar separado aguarda o fechamento do AURORA, instala com /VERYSILENT e reabre o aplicativo. Confira a nova versão na barra de título e no menu Atualizações.

A atualização substitui o aplicativo no mesmo local, sem desinstalar manualmente; playlists e favoritos permanecem na pasta de dados do usuário. O processo nunca instala algo sem o clique de confirmação. Alertas de segurança do próprio Windows (como SmartScreen) não podem ser evitados pelo aplicativo.

O menu permite escolher canal Estável ou Beta e estável. As versões publicadas atualmente são betas; nenhuma versão antiga foi declarada estável sem validação. Releases estáveis exigem aprovação explícita. As versões anteriores permanecem disponíveis no histórico, com arquivos e hashes.

No Linux, a detecção funciona, mas a instalação DEB pode exigir permissões de administrador. Por isso, o aplicativo abre o Release oficial e não tenta atualizar o pacote do sistema silenciosamente.

## Versão 0.5.0 — estabilidade e correções gerais

Esta versão foi feita após uma auditoria geral do repositório. Consulte [a auditoria e suas limitações](docs/AUDIT_0_5.md).

- Futebol: somente partidas associadas a canais reais da playlist; remove jogos há mais de 1h encerrados, evita duplicatas e exclui outras modalidades esportivas (como futebol americano).
- Playlist: atualização aditiva, preservando itens anteriores quando novos conteúdos chegam; processo de download/importação continua atômico.
- Categorias: migração SQLite v5 e reclassificação em segundo plano, para não bloquear a janela durante listas grandes.
- Séries: cartazes oficiais consultados apenas para itens visíveis; rolagem por lote.
- Continuar assistindo: episódios recentes agora iniciam reprodução, sem retornar indevidamente ao catálogo.
- Reprodução: evita sobrescrever progresso de conteúdo concluído, melhora explicação de falhas de codec/rede/acesso.
- Busca: procura dentro da classe inteira, não apenas subgrupo previamente selecionado.
- Aparência: tela de espera com Aurora no lugar do painel preto.
- Testes adicionados para esses fluxos no Windows e Linux.

**Aviso importante:** não há ainda compatibilidade completa com todos os codecs, nem placares em tempo real/escudos no nível do Android. A versão é beta e exige teste em PC real.

## Versão 0.4.0 — classificação e identidade visual

- Corrige playlists M3U com atributos EXTINF depois da vírgula (o título deixa de exibir textos `tvg-logo=`).
- Reclassifica entradas antigas mantendo endereço da playlist, favoritos e progresso.
- Ao vivo: redes e canais (Globo, Band, SporTV etc.) como subcategorias.
- Filmes e séries: gêneros como ação, terror, romance e comédia como subcategorias; fallback de grupos do provedor.
- Melhora tipografia, dimensão da janela, cartões, cabeçalho com aurora, painéis e temas.
- Futebol: quando não há partidas no XMLTV, mostra canais esportivos reais sem horários fictícios; busca EPG Xtream quando a playlist oferece os dados.
- O instalador atualiza a versão anterior na mesma pasta e preserva o catálogo SQLite.
- Depois de instalar, abra a playlist e confira os agrupamentos. Se sua fonte tiver alterado categorias, use **Atualizar playlist** para reler os metadados.

## Versão 0.2.0 — alterações

- **Três colunas**: navegação, categorias e títulos; player à direita.
- **Ao vivo**: a segunda coluna agrupa versões dos canais (Globo, SBT, ESPN e outros).
- **Filmes**: gêneros como Ação, Comédia, Terror, além dos grupos da própria lista.
- **Séries**: grupos e plataformas identificados no M3U, sem inventar a origem quando não informada.
- **Rolagem infinita** com lotes de 60 títulos, sem botões de próxima página.
- **Logos e cartazes** da própria playlist (tvg-logo), com carregamento assíncrono e cache limitado.
- **Futebol**: partidas, horários e canais fornecidos pelo guia XMLTV da lista; sem partidas ou horários inventados.
- **Visual Aurora** com o logo e o banner oficiais do projeto [AURORA AutoFill](https://github.com/fabriciomatosqa/AURORA-AutoFill).
- **Migração de dados da 0.1**: playlists, favoritos e posições são preservados no banco local.

## Download e atualização

Acesse [GitHub Actions: compilar Desktop](https://github.com/fabriciomatosqa/aurora-iptv-desktop/actions/workflows/desktop-build.yml). Selecione a execução **concluída com sucesso** da versão 0.2 e, na parte inferior, em Artifacts, baixe:

- **AURORA-IPTV-Windows-Setup**: instalador .exe. Execute por cima da versão anterior, na mesma pasta, sem desinstalar. O AppId do Inno Setup não mudou e a base local permanece em %LOCALAPPDATA%/AURORA IPTV.
- **AURORA-IPTV-Linux**: .deb atualiza o pacote de mesmo nome aurora-iptv; inclui também uma distribuição portátil .tar.gz. Os dados locais permanecem em ~/.local/share/aurora-iptv.

O instalador Windows pode solicitar o fechamento do aplicativo para substituir os executáveis. Os builds são testes de compilação, não equivalem a um teste final de reprodução real com seu provedor.

## Futebol

1. Escolha sua playlist e clique em Futebol.
2. O sistema tenta obter o endereço XMLTV informado no cabeçalho M3U (atributos x-tvg-url ou url-tvg).
3. Se não houver um, clique em Configurar EPG e informe a URL XMLTV da sua playlist.
4. Clique em Atualizar EPG Futebol para buscar a agenda.
5. Dê duplo clique num confronto com canal associado para assistir.

O EPG pode ser um XML ou XML.GZ e os horários são convertidos para o horário local do computador. Nesta beta, partidas precisam ter confronto identificável no XMLTV e o canal precisa ter o mesmo tvg-id. Ainda não há placares ESPN/FotMob da versão Android.

## Recursos mantidos

Múltiplas playlists, busca, favoritos de canais/filmes/séries inteiras, retomada de filmes e episódios, vídeo em tela cheia e temas claro/escuro/automático. O suporte a vídeo depende dos codecs e do Qt Multimedia do sistema.

## Executar pelo código

Requer Python 3.12 ou compatível.

Windows PowerShell:

~~~powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
~~~

Linux:

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
~~~

Testes de catálogo:

~~~bash
python -m compileall -q aurora_desktop tests run.py
python -m pip install -r requirements.txt pytest
python -m pytest tests -q
~~~

Os scripts de compilação baixam o logo, o ícone e o banner do AutoFill usando um commit GitHub fixo e os embutem nos instaladores. Inno Setup 6 é exigido para compilar o .exe instalador.

## Privacidade e limitações

URLs e eventuais credenciais embutidas nas playlists são armazenadas **localmente no SQLite, sem criptografia**. Não envie listas privadas, bancos de dados ou URLs com tokens para o GitHub. Esta beta ainda não possui EPG completo por canal, placares ao vivo, cartazes por metadados externos, sinopses, controle parental nem todas as traduções da edição Android. Use playlists de sua responsabilidade.
