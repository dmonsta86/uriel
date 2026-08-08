<p align="center">
  <img
    src="docs/assets/the-forge-of-uriel/hero.png"
    alt="The Forge of Uriel"
    width="100%"
  >
</p>

<p align="center">
  <a href="https://github.com/dmonsta86/uriel/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/dmonsta86/uriel/actions/workflows/ci.yml/badge.svg">
  </a>
  <img alt="Status: public beta" src="https://img.shields.io/badge/status-public%20beta-f59e0b">
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-3776AB">
  <a href="LICENSE">
    <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-22c55e">
  </a>
  <img alt="Runtime dependencies: zero" src="https://img.shields.io/badge/runtime%20dependencies-0-0f766e">
</p>

<p align="center">
  🌐 <strong>Languages:</strong>
  <a href="README.md">English</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.pt-BR.md">Português (Brasil)</a> |
  <a href="README.zh-Hans.md">简体中文</a> |
  <a href="README.ar.md">العربية</a> |
  <a href="README.hi.md">हिन्दी</a> |
  <a href="README.ja.md">日本語</a>
</p>

# The Forge of Uriel

> **Notice**: Este documento é uma tradução revisada por IA (AI_SECOND_PASS_REVIEWED). Nota visual: A imagem acima é a versão original em inglês (ENGLISH_FALLBACK). Correções de falantes nativos são bem-vindas.

<!-- URIEL:SECTION:mission:START -->
### Desenvolvimento e blindagem de pesquisa de código aberto e local

> **Sua IDEIA é forte o suficiente para sobreviver à forja?**
>
> Um exame justo para a ideia. Um teste rigoroso para a evidência.

O The Forge of Uriel ajuda a transformar perguntas preliminares e projetos existentes em trabalhos de pesquisa estruturados, reproduzíveis e prontos para submissão.

Ele verifica os dados antes da análise, rastreia afirmações importantes até a evidência direta, preserva contradições e limitações, expõe enquadramentos enganosos e conclusões não apoiadas, e converte verificações com falha em caminhos concretos de reparo e submissão.

Ele não foi projetado para fazer a pesquisa parecer mais forte. Ele foi projetado para mostrar exatamente o quão forte a pesquisa é—e o que a tornaria ainda mais forte.

```text
Interpret generously.
Test rigorously.
Report honestly.
```

---

<!-- URIEL:SECTION:status:START -->
## Limite de lançamento atual

O The Forge of Uriel **1.0.0-rc2** é uma versão candidata pública de um conjunto de ferramentas de desenvolvimento e blindagem de pesquisa de código aberto e local.

```text
uriel --version
# uriel 1.0.0rc2
```

---

<!-- URIEL:SECTION:difference:START -->
## O que o torna diferente

A maioria das ferramentas de pesquisa lida com apenas uma camada: pesquisa bibliográfica, redação, estatística, citações, reprodutibilidade ou revisão.

O The Forge of Uriel foi construído para conectar toda a cadeia.

### Dar à ideia seu exame mais justo

Uma articulação deficiente não é evidência de um pensamento fraco. O Uriel preserva a pergunta original, esclarece a versão testável mais sólida, registra interpretações concorrentes, identifica suposições ocultas e pergunta quais evidências refutariam a ideia.

### Verificar os dados antes de tirar conclusões

A Porta 0 impede que um resultado dependente de dados receba autoridade até que a geração exata do conjunto de dados tenha passado por verificações de identidade, ordenação, normalização, reconciliação e obsolescência.

Antes disso, a resposta honesta é:

> **O resultado ainda não é conhecido.**

### Tratar conclusões como afirmações, não autoridade herdada

Uma conclusão publicada, um autor prestigioso, um modelo confiante ou uma longa bibliografia não substituem a evidência.

O Uriel pergunta:

```text
What exactly is being claimed?
Which artifact supports it?
Where is the supporting datapoint?
What contradicts it?
What assumptions does it depend on?
What remains unknown?
What would change the result?
```

### Desafiar o trabalho concluído

As Três Portas testam a clareza, a evidência e a integridade adversarial. O Uriel procura por contra-evidências omitidas, denominadores ocultos, supergeneralização, saltos causais, erros de controle, vazamentos, suposições frágeis, fontes obsoletas e linguagem de resumo que excede o resultado subjacente.

### Reparar em vez de apenas criticar

Uma verificação com falha não deve terminar com uma rejeição vaga.

O Uriel registra o que continua útil, identifica o menor reparo honesto, seleciona o próximo passo mais sólido, prepara o que pode ser preparado com segurança e estabelece a condição exata para a reavaliação.

---

<!-- URIEL:SECTION:intellectual-honesty:START -->
## A pesquisa não deve ser ganha por enquadramento

Duas falhas enfraquecem repetidamente a pesquisa:

1. contra-evidências, resultados nulos, limitações ou pontos de dados embaraçosos desaparecem da história final; e
2. a conclusão torna-se mais ampla ou mais certa do que a evidência subjacente apoia.

O Uriel torna esses pontos duráveis. Ele registra o que foi testado, o que falhou, o que foi omitido e o que permanece incerto.

---

<!-- URIEL:SECTION:quick-start:START -->
## Início Rápido

Inicialize um espaço de trabalho de evidências na raiz do seu projeto:

```text
uriel init
uriel status
uriel verify
```

---

<!-- URIEL:SECTION:data-readiness:START -->
## Prontidão de Dados (Porta 0)

Antes de analisar dados ou tirar conclusões, execute as verificações de Prontidão de Dados:

Se a Porta 0 falhar, a análise posterior será bloqueada até que a integridade dos dados seja restaurada.

```text
uriel readiness
```

---

<!-- URIEL:SECTION:gates:START -->
## As Três Portas

### Porta 1 — Escopo e Linguagem de Afirmações

Avalia se as afirmações centrais estão delimitadas com precisão, se a terminologia é consistente e se os saltos causais ou supergeneralizados são eliminados.

### Porta 2 — Prontidão de Dados e Evidência Direta

Exige que cada afirmação material seja apoiada por evidências diretas e rastreáveis e gerações de dados verificadas.

### Porta 3 — Robustez Adversarial e Limitações

Expõe explicações concorrentes, vieses de enquadramento, contra-evidências omitidas e limites de aplicabilidade.

---

<!-- URIEL:SECTION:blessing:START -->
## A Bênção de Uriel

A Bênção de Uriel (*The Blessing of Uriel*) é um certificado de auditoria assinado e vinculado criptograficamente por conteúdo (`.ublessing`).

Indica que um pacote de pesquisa passou por todas as três portas sob regras determinísticas estritas. Uma Bênção certifica que a evidência foi verificada; ela não concede autoridade divina nem substitui a revisão por pares.

```text
refuted
impossible
```

---

<!-- URIEL:SECTION:ai:START -->
## Use o Uriel com ou sem IA

### Nota do mantenedor

O The Forge of Uriel foi desenvolvido com o uso extensivo do GPT-5.6 Sol no modo `ultra`, recomendado pelo mantenedor para suas análises de pesquisa de longo horizonte e testes adversariais mais profundos.

Este é um relato de experiência, não uma dependência, integração exclusiva, endosso de privacidade, garantia ou substituto para verificação determinística. Outros sistemas de IA capazes podem ser usados.

### Uma IA compatível

Uma IA compatível pode ajudar a esclarecer, organizar, rascunhar e criticar.

Ela não pode:

```text
mark Data Readiness PASS
pass an integrity gate
change publication authority
override a deterministic failure
issue a Blessing
```

---

<!-- URIEL:SECTION:privacy:START -->
## Segurança e Privacidade

O Uriel é projetado com base em:

```text
read-only defaults
exact-root confinement
explicit consent
verified managed copies
immutable generations
```

---

<!-- URIEL:SECTION:trials:START -->
## As Provas da Forja

As Provas da Forja são demonstrações de referência reproduzíveis das capacidades de verificação de evidências e reparo do Uriel.

Consulte [`docs/FORGE_TRIALS.md`](docs/FORGE_TRIALS.md) e [`benchmarks/forge_trials/synthetic-001/`](benchmarks/forge_trials/synthetic-001/).

---

<!-- URIEL:SECTION:community:START -->
## Contribuições

Contribuições que melhorem a precisão, portabilidade, acessibilidade, segurança, documentação, traduções e fluxos de trabalho são bem-vindas.

Comece com:

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SUPPORT.md`](SUPPORT.md)
- [`SECURITY.md`](SECURITY.md)

---

<!-- URIEL:SECTION:limitations:START -->
## Limitações conhecidas

O The Forge of Uriel foi construído para impor a honestidade intelectual e a linhagem de evidências, mas possui limites definidos:

- O Uriel não pode inventar dados ausentes nem fornecer medições de laboratório.
- As lentes de IA são consultivas e não possuem autoridade sobre as decisões determinísticas das portas.
- Uma Porta aprovada ou uma Bênção emitida certifica o rastreamento de evidências; não é uma garantia de aceitação em revistas nem de consenso entre pares.

---

## Citation and License

Os metadados de citação são fornecidos em [`CITATION.cff`](CITATION.cff). Licença MIT em [`LICENSE`](LICENSE).
