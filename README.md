# AURORA IPTV — Desktop 0.4.0 beta

Player IPTV para **Windows e Linux** em PySide6/Qt Multimedia e SQLite. Repositório independente do [AURORA IPTV Android](https://github.com/fabriciomatosqa/iptv-player). **Nenhum conteúdo, playlist ou credencial incluídos.**

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
