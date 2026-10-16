# ✦ AURORA IPTV — Desktop 0.1.0 beta

Aplicativo IPTV para **Windows e Linux**, com interface inspirada nas auroras boreais. É um projeto independente do [AURORA IPTV Android](https://github.com/fabriciomatosqa/iptv-player), sem emulador e sem página web. Não contém listas, filmes, canais ou credenciais.

## Recursos iniciais

- Importação de listas **M3U** via HTTP/HTTPS ou arquivo local, com múltiplas playlists.
- Download em fluxo e importação incremental em **SQLite**, com paginação para catálogos grandes.
- Navegação por **Ao vivo**, **Filmes** e **Séries**, busca e agrupamento dos episódios.
- Favoritos por canal, filme e série inteira, separados por playlist.
- Últimos conteúdos e retomada de reprodução em filmes e episódios.
- Player integrado Qt Multimedia, controles, volume e tela cheia.
- Temas **claro**, **escuro** e **conforme o sistema**; interface redimensionável.
- Importação em thread separada. Falhas preservam o catálogo anterior.

Esta é uma **beta**: nem todos os recursos da edição Android 1.10.0 foram portados.

## Onde baixar o instalador

Abra a aba **[Actions](https://github.com/fabriciomatosqa/aurora-iptv-desktop/actions/workflows/desktop-build.yml)** e escolha uma execução **concluída com sucesso** do workflow **AURORA IPTV Desktop - builds**.

Na parte inferior da execução, em **Artifacts**, baixe:

- **AURORA-IPTV-Windows-Setup** — instalador .exe para Windows.
- **AURORA-IPTV-Linux** — pacote .deb e distribuição portátil .tar.gz.

O GitHub pode exigir login para baixar os Artifacts. Enquanto a execução não concluir com sucesso, **não há instalador validado para download**. Os pacotes são produzidos em Windows e Ubuntu independentes. Teste a reprodução em computadores reais antes de tratar a versão como estável.

## Executar pelo código

Use **Python 3.12** (ou uma versão compatível).

**Windows (PowerShell):**

~~~powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
~~~

**Linux:**

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
~~~

No Linux, Qt Multimedia pode precisar das bibliotecas Qt/FFmpeg apropriadas à distribuição. Nem todo servidor ou codec funciona nativamente com Qt Multimedia.

Para gerar os instaladores localmente, execute o script build_windows.ps1 no Windows com Inno Setup 6 instalado ou build_linux.sh em Debian/Ubuntu.

## Como usar

1. Abra **Configurações** e clique em **Adicionar URL M3U** ou **Importar arquivo local**.
2. Escolha a lista no seletor da parte superior.
3. Em **Ao vivo / Filmes / Séries**, dê duplo clique no conteúdo desejado.
4. Em Favoritos, marque o filme, canal ou série inteira.
5. Em **Configurações**, clique com o botão direito em uma playlist para editar, ativar ou excluir.
6. Selecione o tema em **Configurações → Aparência**.

## Privacidade

As URLs das playlists e tokens inseridos são salvos **localmente, sem criptografia**, no SQLite (não são enviados para este repositório). No Windows, o banco fica em LOCALAPPDATA/AURORA IPTV/catalog.db; no Linux, em ~/.local/share/aurora-iptv/catalog.db (salvo configuração XDG).

Nunca publique bancos de dados, listas privadas, senhas ou URLs com tokens no GitHub, issues ou logs. O arquivo .gitignore protege os arquivos locais de playlist e bancos mais comuns.

## Testes e limitações

~~~bash
python -m pip install -r requirements.txt pytest
python -m pytest tests -q
~~~

O núcleo M3U/SQLite possui testes para parser, séries, favoritos, retomada, playlists isoladas, preservação após erro e paginação.

**Ainda faltam:** validação visual e de reprodução em Windows/Linux reais; EPG/XMLTV, futebol e placares, sinopses, cartazes, controle parental, traduções e atualizações automáticas. Esses módulos serão adicionados gradualmente.

## Estrutura

~~~text
aurora_desktop/core.py       Parser M3U, SQLite, favoritos e retomada
aurora_desktop/app.py        Interface, player, playlists e temas
tests/test_core.py           Testes automatizados
run.py                       Entrada da aplicação
build_windows.ps1            Empacotamento Windows via PyInstaller
installer_windows.iss        Instalador via Inno Setup
build_linux.sh               Empacotamento Linux .deb e .tar.gz
.github/workflows/           Compilação Windows/Ubuntu no GitHub Actions
~~~
