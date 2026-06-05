# Decisão de Marca — Nome do Produto

> **Data:** 2026-06-05 · **Status:** decidido (aguarda confirmação de domínio/INPI pelo dono)
> **Tipo:** decisão de produto/marketing (não-código). Governança: **G-03 — não versionado por agente; o dono commita.**

## 1. Decisão

- **Nome primário (marca):** **Oikonos**
- **Nome secundário (reserva + domínio descritivo/SEO):** **CasaIgreja**

Substituem o placeholder **"Comunhão"** usado no protótipo da landing.

## 2. Contexto

SaaS de gestão de igrejas **pt-BR, transdenominacional**, com marca **Terracota & Âmbar** (calor, comunidade, acolhimento — *não* "tech frio"). Concorrentes (InChurch, Eklesia) usam **verde/teal** e nomes ligados a "church/ekklesia" — a nossa identidade foge disso de propósito. O nome precisava equilibrar: **calor/comunidade + profundidade teológica + simplicidade pt-BR + marca evocativa/protegível**, com **`.com.br` livre** como filtro decisivo.

## 3. Por que Oikonos

- **Significado = o produto.** Do grego *oîkos* (casa/lar) + *oikonómos* (mordomo/administrador da casa) → raiz de "economia"/"ecumênico". Significa **administrar a "casa"/família da fé** — exatamente o que o software faz. Soma **gestão + lar/acolhimento** num só conceito.
- **Casa com a marca.** *Casa/lar* dialoga com Terracota (mesa, hospitalidade, comunidade) e é **transdenominacional** (sem imagem de denominação específica).
- **Brandável e único.** Abstrato como Notion/Slack/Asana — a categoria entra na **tagline**, não no nome. Fácil de proteger.
- **`.com.br` livre** (verificado no RDAP do registro.br em 2026-06-05).

## 4. Por que CasaIgreja como segundo

- **Tradução transparente do conceito** (oîkos = casa). Se Oikonos for abstrato demais para alguém, CasaIgreja explica na hora.
- **Papel duplo:** (a) **reserva** caso Oikonos tenha conflito de marca no INPI; (b) **domínio descritivo/SEO** (`casaigreja.com.br`, livre) apontando para a marca — captura buscas por "casa igreja sistema/gestão".
- pt-BR nativo, fácil de falar/escrever. Ressalva: "Igreja" é genérico (e estreita o transdenominacional) — por isso é **companheiro descritivo**, não a marca principal.

## 5. Avaliação que sustentou a escolha (resumo)

Filtro de disponibilidade `.com.br` (RDAP registro.br, 2026-06-05):

| Verificado | Resultado |
|---|---|
| **Oikonos, CasaIgreja** | ✅ LIVRES |
| Diakonis, Ministrae, Templaris | ✅ livres (descartados por mérito — ver abaixo) |
| Celestra, koinonia, oikos, ágape, comunhão, conviva, congrega, sodalis, communio, vínea, grei | ❌ registrados |

**Insight:** no Brasil, toda palavra cristã "óbvia" já está registrada (ágape pertence a uma editora; comunhão/koinonia tomados). Disponibilidade vive em **nomes cunhados** — daí Oikonos.

Descarte dos demais candidatos do dono:
- **Diakonis** (serviço/ministério): forte, mas menos caloroso e com o mesmo "k". Bom 3º.
- **Ministrae**: pronúncia ambígua em pt-BR ("ministré/ministrai?") → atrito no boca-a-boca e ao ditar o domínio.
- **Templaris**: evoca **Cavaleiros Templários** (cruzada/militante/medieval-católico) — colide com "acolhimento + transdenominacional".
- **Celestra**: `.com.br` já registrado + leitura "cosmética/wellness".

## 6. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| "k" de Oikonos → erro de grafia ("oiconos") | Fixar a grafia no **wordmark**; registrar defensivas (`oiconos.com.br`, `appoikonos.com.br`); tagline reforça |
| Abstração (leigo não liga ao "igreja") | **Tagline** descritiva + `casaigreja.com.br` como ponte de SEO/clareza |
| **Marca registrada (INPI)** — domínio livre ≠ marca livre | **Dono deve checar INPI** antes de investir no nome (eu não tenho acesso) |
| Disponibilidade muda a cada minuto | **Dono confirma no registro.br** e registra os domínios o quanto antes |

## 7. Rollout quando adotado (vira plano de implementação)

1. **Registrar** `oikonos.com.br` (+ `casaigreja.com.br` e defensivas) no registro.br; **checar/registrar marca no INPI**.
2. **Definir a tagline** (ex.: "*A casa da sua igreja*" / "*Gestão para a sua comunidade de fé*") — decisão de produto.
3. **Substituir o placeholder "Comunhão"** em `referencias/prototipos/landing_terracota_v1.html` e onde aparecer nos docs.
4. **Atualizar os docs** que citam "nome do produto não decidido" (SPRINTS 6.5 §decisões; PRD §nome; OPEN_DECISIONS se virar OD).
5. **Wordmark / logo** com a grafia fixa → entra na **Sprint 6.5** (design system; `Church.logo` é o logo da igreja, não o do produto — o do produto é da marca/landing).
6. (Opcional) Registrar como **OD** em `OPEN_DECISIONS.md` para rastreabilidade.

## 8. Itens em aberto (decisão do dono)

- Papel exato do CasaIgreja: só reserva, ou também domínio descritivo ativo (redirect/landing de SEO)?
- ✅ **Marca verbal final** — **TRAVADA** (ver §10): hero *"Organize a igreja, fortaleça o ministério."* + descritor *"Mordomia, gestão e cuidado."* + sub-tagline funcional + manifesto + campanha.
- Confirmação INPI + registro dos domínios.

## 9. História da marca — por que Oikonos

> Texto-base para o "sobre a marca" (landing, pitch, onboarding). Ancorado no que o sistema faz.

**Oikonos** vem do grego **οἶκος (*oîkos*)** — *casa, lar, família* — e de **οἰκονόμος (*oikonómos*)**, o **mordomo da casa**: aquele a quem se confia o cuidado do lar e de cada um que vive nele. Dessa raiz nascem as palavras *economia* (a "ordem da casa") e *ecumênico* (a casa comum).

No Novo Testamento, a "casa de Deus" não é o prédio — é o **povo**, a **família da fé**. E a igreja sempre teve quem cuidasse dessa casa: acolher, organizar, lembrar dos nomes, cuidar de quem precisa.

**Oikonos é o mordomo digital da casa da fé.** Ele ajuda o líder a fazer o que a igreja sempre fez — só que com zelo e sem o peso da planilha:

- **cuidar das pessoas** (cadastro com consentimento e respeito aos dados — LGPD é cuidar de quem confiou em você);
- **manter as comunidades e células** vivas e conectadas;
- **organizar ministérios, encontros e a presença** de cada um;
- **montar escalas** sem sobrecarregar ninguém;
- **zelar pelas finanças com mordomia** (dízimos, ofertas, lançamentos e saldo — *honrar o que é de Deus*);
- **enxergar a casa inteira** num só lugar (o painel).

Não por acaso: o Oikonos **nasceu de uma necessidade financeira**. Por isso a **mordomia dos recursos** está no coração do produto **desde o MVP** (financeiro básico, Sprint 6.7) — não como acessório. É o lastro real do nome (*oikonómos* = o administrador) e do manifesto ("Honramos o que é de Deus").

E porque é "casa", é de **todos**: Oikonos é **transdenominacional** — *oîkos* é família, não denominação. Cada igreja tem a **sua própria casa** na plataforma (dados isolados, só seus). A identidade visual reforça o nome: **terracota e âmbar** — o barro, a mesa, o calor do lar.

> **Nota de uso (importante):** "casa" é o coração da **história** (etimologia), **não da promessa de venda**. No subconsciente brasileiro, "casa" pode evocar o que **não** se organiza — por isso o **slogan lidera com "organizar"** (§10), e a história usa o estereótipo a favor: *o mordomo que põe a casa em ordem*.

> **Em uma frase:** *Oikonos organiza a casa de Deus para que o líder fortaleça o ministério.*

## 10. Marca — arquitetura verbal (DECISÃO TRAVADA, para o lançamento)

> **Timing:** o **MVP/piloto Athos NÃO tem divulgação de marca** (convite direto). A marca verbal é do **lançamento público**, depois das Sprints 8 (Financeiro) e 9 (WhatsApp) — quando o produto já entrega tudo. Por isso pode liderar com os diferenciais reais sem super-prometer.

**Voz de marca em camadas — cada peça com sua função:**

| Peça | Texto | Onde usa |
|---|---|---|
| **Nome** | **Oikonos** | tudo |
| **Tagline (hero)** | **"Organize a igreja, fortaleça o ministério."** | topo da landing, anúncios, capa |
| **Descritor (pilares)** | *Mordomia, gestão e cuidado.* | sob o hero, navbar, rodapé |
| **Sub-tagline (funcional)** | *Pessoas, finanças e comunicação — tudo em ordem, num só lugar.* | hero secundário, meta/SEO |
| **Manifesto / credo** | *Administramos com propósito. Cuidamos com amor. Honramos o que é de Deus.* | "sobre/missão", vídeo, onboarding |
| **Campanha** | *Menos planilha, mais pastoreio.* | mídia, e-mail, social |

**Por que o hero é "Organize a igreja, fortaleça o ministério":** é uma promessa de **resultado** (converte melhor que lista de valores); **lidera com "organizar"** (ordem — evita a associação negativa "casa = bagunça" no subconsciente brasileiro, ainda mais com o financeiro em jogo); amarra o **meio** (organizar/admin) ao **fim** (fortalecer o ministério, anti-"virar gerente"); clareza imediata, sem ambiguidade. "Casa" (*oikos*) fica **na história da marca (§9)**, não na promessa.

**Mapeamento × dor de mercado:**

| Linha | Dores |
|---|---|
| "Organize a igreja" | #2 (medo da bagunça/curva) · #1/#7 (sai do Excel) · antídoto do estereótipo |
| "fortaleça o ministério" | o "porquê" — a administração serve ao pastoreio |
| "Mordomia, gestão e cuidado" | #1 (mordomia = recursos/financeiro) · #4 (cuidado/LGPD) · diz a categoria |
| "Pessoas, finanças e comunicação… num só lugar" | #1 financeiro · #5 WhatsApp · #6 unificado |
| "Honramos o que é de Deus" (manifesto) | financeiro/mordomia, de forma reverente |
| "Menos planilha, mais pastoreio" | #1/#7 · linguagem do pastor |

**Pitch de 30s (lançamento):**
> "No Brasil, a igreja vive corrida e a planilha some. **Oikonos** — do grego *oikonómos*, o mordomo que **põe a casa em ordem** — **organiza a sua igreja para você fortalecer o ministério**: pessoas, comunidades, finanças e comunicação no WhatsApp, **tudo num só lugar**, simples no celular e seguro de verdade (LGPD desde o primeiro dia). Administramos com propósito, cuidamos com amor e honramos o que é de Deus. **Menos planilha, mais pastoreio.**"

**Regra de honestidade (vendas/landing):** só comunicar o que o **lançamento** entrega. Financeiro **básico já é MVP** (Sprint 6.7); financeiro avançado (Sprint 8) e WhatsApp/Evolution (Sprint 9) entram no discurso quando construídos — o que, por timing, coincide com o lançamento. **Itens ainda em decisão** (app do membro, **doação online**, preço OD-001, suporte de migração) **não** entram no discurso até resolvidos.
