# AURORA IPTV Desktop 0.6.0 beta 1

Esta versão inicia o sistema de **atualização pelo GitHub Releases**:

- O aplicativo apresenta a versão instalada na janela e no menu Atualizações.
- Verifica novas versões automaticamente no lançamento (com intervalo de 24 horas) e permite consulta manual.
- Permite escolher entre canal **Estável** ou **Beta + Estável**.
- No Windows instalado, após clicar em **Atualizar agora**, baixa, verifica SHA-256, inicia o instalador Inno Setup em modo silencioso e fecha o aplicativo. **Sem assistente de Avançar, sem desinstalar manualmente.**
- Reaproveita o mesmo identificador de instalação para preservar dados do usuário.
- No Linux, apresenta a versão disponível e abre a página oficial de download, pois instalações DEB podem exigir permissão administrativa.
- Builds Windows e Linux passam a publicar artefatos no GitHub Releases após os testes concluírem com sucesso.
- Releases e tags anteriores não são sobrescritos; as versões de teste são marcadas como pre-release.
- Versões estáveis exigem aprovação explícita via workflow manual.
- Metadados de versão do aplicativo Windows e do pacote DEB usam a mesma fonte central.

**Observações:** a migração inicial da versão 0.5 para a 0.6 exige uma única instalação manual; a 0.5 ainda não possui o atualizador integrado. O Windows pode exibir alertas de segurança do próprio sistema (SmartScreen/antivírus), que não podem ser ignorados pelo aplicativo.

Esta é uma versão **beta**. Ela não corrige todas as limitações anteriores de reprodução, metadados e futebol.
