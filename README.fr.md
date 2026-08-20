<p align="center">
  <img
    src="docs/assets/i18n/fr/uriel-forge-hero.png"
    alt="La Forge d’Uriel montre un chercheur-forgeron sans ailes, vigilant et bienveillant, qui éprouve une idée au milieu de la préparation des données, du traçage des preuves, des contre-preuves, des trois portes, des corrections et de la soumission."
    width="100%"
  >
</p>

<p align="center">
  <a href="https://github.com/dmonsta86/uriel/actions/workflows/ci.yml" title="État de la CI pour le dernier commit du dépôt">
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

> **Avis** : Cette documentation a fait l’objet d’une seconde révision assistée par IA (AI_SECOND_PASS_REVIEWED). L’affiche est une variante localisée révisée par IA (LOCALIZED_AI_REVIEWED), mais son texte visible doit encore être revu par une personne de langue maternelle (AI_ASSISTED_REQUIRES_NATIVE_REVIEW). Les corrections sont les bienvenues.

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

The Forge of Uriel **v1.0.0-rc2** est la dernière version candidate publique étiquetée ; `main` peut contenir une maintenance révisée après cette étiquette et avant la prochaine version. Le cœur déterministe du projet et le paquetage sont livrés. Data Readiness et les Trois Portes sont en bêta. Data Desk, le Forge opérationnel, les transmissions à l'IA et les paquets Blessing restent expérimentaux.

Il s'agit d'un logiciel bêta public, et non d'une infrastructure à imposer pour la publication. Il nécessite encore des essais dans davantage de domaines, des éléments d'utilisabilité et un examen de sécurité indépendant. Consultez l'[état exact des capacités](docs/CAPABILITY_STATUS.md), les [limites connues](docs/LIMITATIONS.md) et la [feuille de route publique](docs/ROADMAP.md).

```text
uriel --version
# uriel 1.0.0rc2
```

La version ci-dessus identifie le paquet installé ; les affirmations de version se rapportent à l'étiquette ou au commit exact testé. Le badge CI indique l'état du dernier workflow du dépôt à titre informatif : il ne remplace pas le contrôle local de publication et ne prouve pas que ce checkout exact a passé la CI.

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

Depuis une copie du dépôt, installez sans dépendances d'exécution ni
construction isolée nécessitant le réseau :

```text
python -m pip install --no-deps --no-build-isolation .
uriel start --root ../my-study --kind new_idea --title "My study" --question "What would change my conclusion?"
uriel status --root ../my-study
uriel verify --root ../my-study
```

Paquet de distribution : `uriel-research`. Import Python et commande CLI :
`uriel`.

Pour la version autonome sans installation, consultez
[`docs/GETTING_STARTED_FREE.md`](docs/GETTING_STARTED_FREE.md).

Pour essayer la fonction optionnelle de texte exact, consultez le [guide du Registre Verbatim de recherche](docs/RESEARCH_VERBATIM_LEDGER.md). Elle est DÉSACTIVÉE par défaut et ne capture jamais de texte en arrière-plan.

### Tester une installation

Depuis un checkout, exécutez la suite ciblée et le fixture Forge déterministe fourni :

```text
python -m pytest -q
python scripts/check_forge_trial.py
```

Après installation de la wheel, le smoke test installé du Registre Verbatim se lance avec `python scripts/smoke_installed_verbatim_ledger.py --executable PATH_TO_URIEL`, et le smoke test Forge installé avec `python scripts/smoke_installed_forge.py --executable PATH_TO_URIEL`.

---

<!-- URIEL:SECTION:data-readiness:START -->
## Préparation des données (Porte 0)

Sur la branche canonique `main`, le flux local expérimental `uriel data` peut planifier et sceller des fichiers CSV, TSV, JSON, JSONL, texte et Markdown en UTF-8 ; créer des profils structurels et des générations immuables ; prévisualiser les écarts ; préserver chaque enregistrement pendant la réconciliation ; puis réanalyser et vérifier indépendamment le lien avec les données brutes. Il n'exécute aucune formule, ne devine ni unité ni type sémantique, ne crée aucun résultat scientifique et n'accorde aucune autorité à la Porte 0. La Porte 0 ne commence qu'après la déclaration explicite de l'identité des enregistrements pour une génération exacte.

Après que `uriel data inspect` a renvoyé l'identifiant de génération, créez et vérifiez son SortSpec lié à cette génération :

```text
uriel readiness init-sort-spec --root ../my-study --generation <GENERATION_ID> --keys id
uriel readiness check --root ../my-study --generation <GENERATION_ID>
uriel readiness status --root ../my-study --generation <GENERATION_ID>
```

Le reçu v2 lie la lignée brute, les versions de l'analyseur et de la politique, les identifiants de colonnes stables, l'ordre, les règles relatives aux doublons et aux valeurs nulles, la réconciliation, le plan d'analyse et le SortSpec actif exact. Un état absent, périmé, altéré ou ambigu bloque l'analyse en aval. Si plusieurs SortSpecs existent, sélectionnez explicitement le chemin exact.

Les paquets de génération destinés à l'IA exigent un reçu PASS ainsi que les lignes et colonnes nécessaires à la tâche. Ils sont limités à 1 000 lignes et 1 Mio, prennent en charge la rédaction des valeurs et n'ont aucune autorité sur les portes, la publication, les résultats ou les Blessings. Chaque paquet impose un mode consultatif en lecture seule : réseau, shell et écritures dans le paquet ou le projet sont interdits, avec une sortie demandée limitée à 128 Kio et 15 minutes.

---

<!-- URIEL:SECTION:forge-forward:START -->
## Continuer une exécution Forge incomplète

Les commandes expérimentales Forge opèrent sur des chemins exacts adressés par contenu, jamais sur une exécution mutable "latest":

```text
uriel forge continue --root ../my-study --snapshot <EXACT_SNAPSHOT> --request artifacts/forge-forward.json
uriel forge verify-continuation --root ../my-study --packet <EXACT_CONTINUATION>
uriel forge export --root ../my-study --snapshot <EXACT_SNAPSHOT> --destination exports/review-copy
uriel forge verify-export --root ../my-study --manifest exports/review-copy/manifest.json --snapshot <EXACT_SNAPSHOT>
```

Les paquets de continuation restent privés sous l'état ignoré `.uriel/forge/`. Les exportations sont de nouveaux répertoires contenant uniquement des métadonnées structurelles générées et des alias. Ils ne copient pas les corps de preuves, les identifiants de projet/d'exécution, les chemins privés, les identifiants, les URL privées ou les noms non liés. Chaque vérificateur relit la source exacte, recalcule les hachages et les classements, rejette les fichiers ou liens supplémentaires et ne signale aucune autorité de Gate, de publication, de vérificateur, de Bénédiction ou d'Ailes Gagnées.

Consultez le [Méthode Forge](docs/FORGE_METHOD.md) pour la forme de demande fermée, la règle de score, la dérivation des bloqueurs et les limites de refus.

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

La Bénédiction d'Uriel est un paquet expérimental d'attestation adressé par
contenu. Elle lie une génération exacte du projet aux décisions enregistrées
des portes, aux reçus, aux limites et au recalcul du vérificateur.

Elle signifie que ces prédicats enregistrés ont réussi pour ces artefacts
précis. Ce n'est ni une validation scientifique indépendante, ni une signature
cryptographique de l'auteur, ni une évaluation par les pairs, ni une preuve de
la véracité des mesures.

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

L'épreuve synthétique fournie est un jeu reproductible comportant 24 problèmes
scellés dans le corrigé et une grille de 100 points. Le contrôle de publication
recalcule le résumé nettoyé et valide le jeu ; il n'affirme pas qu'Uriel a
détecté un problème sans rapport aveugle ensuite évalué.

```text
python scripts/check_forge_trial.py
```

La méthode Forge décrit le flux public. Son noyau local expérimental de cycles,
d'états et de vérification est maintenant disponible :

```text
uriel forge init --root PROJECT --request INIT.json
uriel forge transition --root PROJECT --snapshot EXACT.json --to-state SCOPED --rationale "Scope reviewed"
uriel forge verify --root PROJECT --snapshot EXACT.json
```

Il écrit des instantanés privés immuables et n'accorde aucune autorité en amont.
L'exporteur assaini et la couche générale de preuve de blocage/prochaine action
restent planifiés.

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
- Data Desk rapporte des observations structurelles et lexicales bornées ; ce n'est ni un moteur statistique, ni un validateur sémantique, ni un substitut à l'examen des mesures et méthodes sources.
- Les lentilles IA sont consultatives et n'ont aucune autorité sur les décisions déterministes des portes.
- Une Porte ou Bénédiction expérimentale indique que les prédicats enregistrés par Uriel ont réussi pour des artefacts précis. Elle n'établit ni validité des mesures, ni vérité, ni acceptation éditoriale, ni consensus.

---

## Citation and License

Les métadonnées de citation sont fournies dans [`CITATION.cff`](CITATION.cff). Licence MIT dans [`LICENSE`](LICENSE).
