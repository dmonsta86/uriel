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

> **Notice**: Ce document est une traduction révisée par IA (AI_SECOND_PASS_REVIEWED). Note visuelle : L'image ci-dessus est la version originale anglaise (ENGLISH_FALLBACK). Les corrections de locuteurs natifs sont les bienvenues.

<!-- URIEL:SECTION:mission:START -->
### Développement et consolidation de recherche open-source et local

> **Votre IDÉE est-elle assez solide pour survivre à la forge ?**
>
> Un examen équitable pour l'idée. Un test rigoureux pour les preuves.

The Forge of Uriel permet de transformer les questions initiales et les projets existants en travaux de recherche structurés, réutilisables et prêts pour la soumission.

Il vérifie les données avant l'analyse, trace les affirmations importantes jusqu'aux preuves directes, préserve les contradictions et les limites, expose les cadrages trompeurs et les conclusions non étayées, et transforme les vérifications échouées en voies concrètes de réparation et de soumission.

Il n'est pas conçu pour rendre la recherche plus convaincante. Il est conçu pour montrer exactement quelle est la solidité de la recherche—et ce qui la rendrait encore plus solide.

```text
Interpret generously.
Test rigorously.
Report honestly.
```

---

<!-- URIEL:SECTION:status:START -->
## Limite de version actuelle

The Forge of Uriel **1.0.0-rc2** est une version candidate publique d'un ensemble d'outils de développement et de consolidation de recherche open-source et local.

```text
uriel --version
# uriel 1.0.0rc2
```

---

<!-- URIEL:SECTION:difference:START -->
## Ce qui le rend différent

La plupart des outils de recherche gèrent une seule couche : recherche documentaire, rédaction, statistiques, citations, reproductibilité ou révision.

The Forge of Uriel est conçu pour relier toute la chaîne.

### Donner à l'idée son examen le plus équitable

Une mauvaise articulation n'est pas la preuve d'une pensée pauvre. Uriel préserve la question d'origine, clarifie la version testable la plus solide, enregistre les interprétations concurrentes, identifie les hypothèses cachées et demande quelles preuves réfuteraient l'idée.

### Vérifier les données avant de tirer des conclusions

La Porte 0 empêche un résultat dépendant des données de recevoir une autorité tant que la génération exacte du jeu de données n'a pas passé les vérifications d'identité, de tri, de normalisation, de réconciliation et de péremption.

Avant cela, la réponse honnête est :

> **Le résultat n'est pas encore connu.**

### Traiter les conclusions comme des affirmations, non comme une autorité héritée

Une conclusion publiée, un auteur prestigieux, un modèle confiant ou une longue bibliographie ne remplacent pas les preuves.

Uriel demande :

```text
What exactly is being claimed?
Which artifact supports it?
Where is the supporting datapoint?
What contradicts it?
What assumptions does it depend on?
What remains unknown?
What would change the result?
```

### Défier le travail terminé

Les Trois Portes testent la clarté, les preuves et l'intégrité contradictoire. Uriel recherche les contre-preuves omises, les dénominateurs cachés, la sur-généralisation, les excès causaux, les erreurs de contrôle, les fuites, les hypothèses fragiles, les sources périmées et le langage de résumé qui dépasse le résultat sous-jacent.

### Réparer au lieu de simplement critiquer

Une vérification échouée ne doit pas se terminer par un rejet vague.

Uriel enregistre ce qui reste utile, identifie la réparation la plus petite et la plus honnête, sélectionne la prochaine étape la plus solide, prépare ce qui peut l'être en toute sécurité et énonce la condition exacte pour une nouvelle vérification.

---

<!-- URIEL:SECTION:intellectual-honesty:START -->
## La recherche ne doit pas être gagnée par le cadrage

Deux défaillances affaiblissent à plusieurs reprises la recherche :

1. les contre-preuves, les résultats nuls, les limites ou les points de données embarrassants disparaissent de l'histoire finale ; et
2. la conclusion devient plus large ou plus certaine que ce que les preuves sous-jacentes étayent.

Uriel rend ces points durables. Il enregistre ce qui a été testé, ce qui a échoué, ce qui a été omis et ce qui reste incertain.

---

<!-- URIEL:SECTION:quick-start:START -->
## Démarrage rapide

Initialisez un espace de travail de preuves à la racine de votre projet :

```text
uriel init
uriel status
uriel verify
```

---

<!-- URIEL:SECTION:data-readiness:START -->
## Préparation des données (Porte 0)

Avant d'analyser des données ou de tirer des conclusions, exécutez les vérifications de préparation des données :

Si la Porte 0 échoue, l'analyse en aval est bloquée jusqu'à ce que l'intégrité des données soit restaurée.

```text
uriel readiness
```

---

<!-- URIEL:SECTION:gates:START -->
## Les Trois Portes

### Porte 1 — Portée et langage des affirmations

Évalue si les affirmations centrales sont délimitées avec précision, si la terminologie est cohérente et si les excès causaux ou sur-généralisés sont éliminés.

### Porte 2 — Préparation des données et preuves directes

Exige que chaque affirmation matérielle soit étayée par des preuves directes et traçables et des générations de données vérifiées.

### Porte 3 — Robustesse adversariale et limites

Expose les explications concurrentes, les biais de cadrage, les contre-preuves omises et les limites d'applicabilité.

---

<!-- URIEL:SECTION:blessing:START -->
## La Bénédiction d'Uriel

La Bénédiction d'Uriel (*The Blessing of Uriel*) est un certificat d'audit signé et lié par adressage de contenu (`.ublessing`).

Il indique qu'un dossier de recherche a franchi avec succès les trois portes selon des règles déterministes strictes. Une Bénédiction certifie que les preuves ont été vérifiées ; elle n'accorde pas d'autorité divine et ne remplace pas l'évaluation par les pairs.

```text
refuted
impossible
```

---

<!-- URIEL:SECTION:ai:START -->
## Utiliser Uriel avec ou sans IA

### Note du mainteneur

The Forge of Uriel a été développé avec une utilisation intensive de GPT-5.6 Sol en mode `ultra`, que le mainteneur recommande pour ses analyses de recherche à long horizon et ses tests contradictoires approfondis.

Il s'agit d'un rapport d'expérience, non d'une dépendance, d'une intégration exclusive, d'un aval de confidentialité ou d'un substitut à la vérification déterministe. D'autres systèmes d'IA capables peuvent être utilisés.

### Une IA compatible

Une IA compatible peut assister à clarifier, organiser, rédiger et critiquer.

Elle ne peut pas :

```text
mark Data Readiness PASS
pass an integrity gate
change publication authority
override a deterministic failure
issue a Blessing
```

---

<!-- URIEL:SECTION:privacy:START -->
## Sécurité et confidentialité

Uriel est conçu autour de :

```text
read-only defaults
exact-root confinement
explicit consent
verified managed copies
immutable generations
```

---

<!-- URIEL:SECTION:trials:START -->
## Les Épreuves de la Forge

Les Épreuves de la Forge sont des démonstrations de référence reproductibles des capacités de vérification de preuves et de réparation d'Uriel.

Consultez [`docs/FORGE_TRIALS.md`](docs/FORGE_TRIALS.md) et [`benchmarks/forge_trials/synthetic-001/`](benchmarks/forge_trials/synthetic-001/).

---

<!-- URIEL:SECTION:community:START -->
## Contributions

Les contributions améliorant la précision, la portabilité, l'accessibilité, la sécurité, la documentation, les traductions et les flux de travail sont les bienvenues.

Commencez par :

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SUPPORT.md`](SUPPORT.md)
- [`SECURITY.md`](SECURITY.md)

---

<!-- URIEL:SECTION:limitations:START -->
## Limites connues

The Forge of Uriel est conçu pour faire respecter l'honnêteté intellectuelle et la lignée des preuves, mais il a des limites définies :

- Uriel ne peut pas inventer de données manquantes ni fournir de mesures de laboratoire.
- Les lentilles IA sont consultatives et n'ont aucune autorité sur les décisions déterministes des portes.
- Une Porte franchie ou une Bénédiction délivrée certifie le traçage des preuves ; ce n'est pas une garantie d'acceptation dans une revue ni de consensus entre pairs.

---

## Citation and License

Les métadonnées de citation sont fournies dans [`CITATION.cff`](CITATION.cff). Licence MIT dans [`LICENSE`](LICENSE).
