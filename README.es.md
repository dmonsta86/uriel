<p align="center">
  <img
    src="docs/assets/i18n/es/uriel-forge-hero.png"
    alt="La Forja de Uriel presenta a un investigador-herrero sin alas, atento y dispuesto a ayudar, que somete una idea a una prueba rigurosa entre símbolos de preparación de datos, ordenamiento, evidencia, contraevidencia, auditoría, reparación y presentación."
    width="100%"
  >
</p>

<p align="center">
  <a href="https://github.com/dmonsta86/uriel/actions/workflows/ci.yml" title="Estado de CI del último commit del repositorio">
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

> **Aviso**: Esta documentación tiene una segunda revisión asistida por IA (AI_SECOND_PASS_REVIEWED). El póster es una variante localizada revisada por IA (LOCALIZED_AI_REVIEWED), pero su texto visible aún requiere revisión de un hablante nativo (AI_ASSISTED_REQUIRES_NATIVE_REVIEW). Se agradecen las correcciones.

<!-- URIEL:SECTION:mission:START -->
### Desarrollo y blindaje de investigación de código abierto y local

> **¿Es tu IDEA lo suficientemente fuerte para sobrevivir a la forja?**
>
> Un examen justo para la idea. Una prueba rigurosa para la evidencia.

The Forge of Uriel ayuda a transformar preguntas preliminares y proyectos existentes en trabajos de investigación estructurados, reproducibles y listos para su presentación.

Verifica los datos antes del análisis, rastrea afirmaciones importantes hasta la evidencia directa, preserva contradicciones y limitaciones, expone encuadres engañosos y conclusiones no respaldadas, y convierte las comprobaciones fallidas en rutas concretas de reparación y presentación.

No está diseñado para que la investigación suene más fuerte. Está diseñado para mostrar exactamente qué tan fuerte es la investigación y qué la haría aún más fuerte.

```text
Interpret generously.
Test rigorously.
Report honestly.
```

---

<!-- URIEL:SECTION:status:START -->
## Límite de lanzamiento actual

The Forge of Uriel **v1.0.0-rc2** es la última versión candidata pública etiquetada; `main` puede contener mantenimiento revisado posterior a esa etiqueta y anterior a la siguiente versión. El núcleo determinista del proyecto y el empaquetado están publicados. Data Readiness y las Tres Puertas están en beta. Data Desk, Forge operativo, entregas a IA y paquetes Blessing siguen siendo experimentales.

Este es un software beta público, no una infraestructura que deba imponerse para publicar. Aún necesita pruebas más amplias en distintos ámbitos, evidencia de usabilidad y una revisión de seguridad independiente. Consulta el [estado exacto de capacidades](docs/CAPABILITY_STATUS.md), las [limitaciones conocidas](docs/LIMITATIONS.md) y la [hoja de ruta pública](docs/ROADMAP.md).

```text
uriel --version
# uriel 1.0.0rc2
```

La versión anterior identifica el paquete instalado; las afirmaciones sobre una versión se vinculan a la etiqueta o al commit exactos que se prueban. La insignia de CI informa sobre el estado del flujo más reciente del repositorio y es solo informativa: no sustituye la comprobación local de publicación ni demuestra que esta copia exacta haya pasado CI.

---

<!-- URIEL:SECTION:difference:START -->
## Qué lo hace diferente

La mayoría de las herramientas de investigación manejan una sola capa: búsqueda bibliográfica, redacción, estadística, citas, reproducibilidad o revisión.

The Forge of Uriel está construido para conectar toda la cadena.

### Dar a la idea su examen más justo

Una mala articulación no es evidencia de un pensamiento deficiente. Uriel preserva la pregunta original, aclara la versión comprobable más sólida, registra interpretaciones competidoras, identifica suposiciones ocultas y pregunta qué evidencia refutaría la idea.

### Verificar los datos antes de sacar conclusiones

La Puerta 0 impide que un resultado dependiente de datos reciba autoridad hasta que la generación exacta del conjunto de datos haya pasado las comprobaciones de identidad, ordenación, normalización, reconciliación y obsolescencia.

Antes de eso, la respuesta honesta es:

> **El resultado aún no se conoce.**

### Tratar las conclusiones como afirmaciones, no como autoridad heredada

Una conclusión publicada, un autor prestigioso, un modelo seguro o una larga bibliografía no sustituyen a la evidencia.

Uriel pregunta:

```text
What exactly is being claimed?
Which artifact supports it?
Where is the supporting datapoint?
What contradicts it?
What assumptions does it depend on?
What remains unknown?
What would change the result?
```

### Desafiar el trabajo terminado

Las Tres Puertas evalúan la claridad, la evidencia y la integridad adversarial. Uriel busca contraevidencia omitida, denominadores ocultos, sobregeneralizaciones, saltos causales, desajustes de control, filtraciones, suposiciones frágiles, fuentes obsoletas y lenguaje de resumen que supere el resultado subyacente.

### Reparar en lugar de solo criticar

Una comprobación fallida no debe terminar con un rechazo vago.

Uriel registra lo que sigue siendo útil, identifica la reparación más pequeña y honesta, selecciona el siguiente paso más sólido, prepara lo que se puede preparar de forma segura y establece la condición exacta para la reevaluación.

---

<!-- URIEL:SECTION:intellectual-honesty:START -->
## La investigación no debe ganarse mediante el encuadre

Dos fallos debilitan repetidamente la investigación:

1. la contraevidencia, los resultados nulos, las limitaciones o los puntos de datos incómodos desaparecen de la historia final; y
2. la conclusión se vuelve más amplia o más segura de lo que respalda la evidencia subyacente.

Uriel hace que esos puntos sean duraderos. Registra lo que se probó, lo que falló, lo que se omitió y lo que sigue siendo incierto.

---

<!-- URIEL:SECTION:quick-start:START -->
## Inicio rápido

Desde una copia del repositorio, instala sin dependencias de ejecución ni una
compilación aislada que necesite red:

```text
python -m pip install --no-deps --no-build-isolation .
uriel start --root ../my-study --kind new_idea --title "My study" --question "What would change my conclusion?"
uriel status --root ../my-study
uriel verify --root ../my-study
```

Paquete de distribución: `uriel-research`. Módulo importable de Python y
comando CLI: `uriel`.

Para la ruta de un solo archivo sin instalación, consulta
[`docs/GETTING_STARTED_FREE.md`](docs/GETTING_STARTED_FREE.md).

Para probar la función opcional de texto exacto, consulta la [guía del Registro Verbatim de Investigación](docs/RESEARCH_VERBATIM_LEDGER.md). Está DESACTIVADA de forma predeterminada y nunca captura texto en segundo plano.

### Probar una instalación

Desde una copia del repositorio, ejecuta la suite enfocada y el accesorio Forge determinista incluido:

```text
python -m pytest -q
python scripts/check_forge_trial.py
```

Después de instalar la rueda, puedes ejecutar la prueba rápida instalada del Registro Verbatim con `python scripts/smoke_installed_verbatim_ledger.py --executable PATH_TO_URIEL` y la prueba rápida instalada de Forge con `python scripts/smoke_installed_forge.py --executable PATH_TO_URIEL`.

---

<!-- URIEL:SECTION:data-readiness:START -->
## Preparación de datos (Puerta 0)

En la rama canónica `main`, el flujo local experimental `uriel data` puede planificar y sellar CSV, TSV, JSON, JSONL, texto y Markdown en UTF-8; crear perfiles y generaciones estructurales inmutables; previsualizar diferencias; preservar cada registro durante la reconciliación; y volver a analizar y verificar de forma independiente el vínculo con los datos brutos. No ejecuta fórmulas, no adivina unidades ni tipos semánticos, no crea hallazgos científicos y no otorga autoridad de la Puerta 0. La Puerta 0 comienza solo cuando declaras explícitamente la identidad de los registros para una generación exacta.

Después de que `uriel data inspect` devuelva el identificador de generación, crea y comprueba su SortSpec vinculado a esa generación:

```text
uriel readiness init-sort-spec --root ../my-study --generation <GENERATION_ID> --keys id
uriel readiness check --root ../my-study --generation <GENERATION_ID>
uriel readiness status --root ../my-study --generation <GENERATION_ID>
```

El recibo v2 vincula el linaje bruto, las versiones del analizador y de la política, los identificadores estables de columnas, el orden, las reglas de duplicados y nulos, la reconciliación, el plan de análisis y el SortSpec activo exacto. Un estado ausente, obsoleto, alterado o ambiguo bloquea el análisis posterior. Si existe más de un SortSpec, selecciona explícitamente su ruta exacta.

Los paquetes de generación destinados a IA requieren un recibo PASS y filas y columnas específicas para la tarea. Tienen límites de 1.000 filas y 1 MiB, permiten redactar valores y no poseen autoridad sobre puertas, publicación, hallazgos ni Blessings. Cada paquete declara un modo consultivo de solo lectura: prohíbe red, shell y escrituras en el paquete o proyecto, y limita la salida solicitada a 128 KiB y 15 minutos.

---

<!-- URIEL:SECTION:forge-forward:START -->
## Continuar una ejecución incompleta de Forge

Los comandos experimentales de Forge operan en rutas exactas direccionadas por contenido, nunca en una ejecución mutable "latest":

```text
uriel forge continue --root ../my-study --snapshot <EXACT_SNAPSHOT> --request artifacts/forge-forward.json
uriel forge verify-continuation --root ../my-study --packet <EXACT_CONTINUATION>
uriel forge export --root ../my-study --snapshot <EXACT_SNAPSHOT> --destination exports/review-copy
uriel forge verify-export --root ../my-study --manifest exports/review-copy/manifest.json --snapshot <EXACT_SNAPSHOT>
```

Los paquetes de continuación permanecen privados bajo el estado ignorado `.uriel/forge/`. Las exportaciones son directorios nuevos que contienen únicamente metadatos estructurales generados y alias. No copian cuerpos de evidencia, IDs de proyecto/ejecución, rutas privadas, credenciales, URLs privadas ni nombres no relacionados. Cada verificador vuelve a leer la fuente exacta, recalcula hashes y clasificaciones, rechaza archivos o enlaces adicionales y notifica cero autoridad de Gate, publicación, verificador, Bendición o Alas Ganadas.

Consulte el [Método Forge](docs/FORGE_METHOD.md) para conocer la forma de solicitud cerrada, la regla de puntuación, la derivación de bloqueadores y los límites de denegación.

---

<!-- URIEL:SECTION:gates:START -->
## Las Tres Puertas

### Puerta 1 — Alcance y Lenguaje de Afirmaciones

Evalúa si las afirmaciones centrales están delimitadas con precisión, la terminología es consistente y se eliminan los saltos causales o sobregeneralizados.

### Puerta 2 — Preparación de Datos y Evidencia Directa

Requiere que cada afirmación material esté respaldada por evidencia directa y rastreable y generaciones de datos verificadas.

### Puerta 3 — Robustez Adversarial y Limitaciones

Expone explicaciones competidoras, sesgos de encuadre, contraevidencia omitida y límites de aplicabilidad.

---

<!-- URIEL:SECTION:blessing:START -->
## La Bendición de Uriel

La Bendición de Uriel es un paquete experimental de atestación direccionado
por contenido. Vincula una generación exacta del proyecto con las decisiones de
las puertas, los recibos, las limitaciones y la recomputación del verificador.

Significa que esos predicados registrados se cumplieron para esos artefactos
exactos. No constituye validación científica independiente, firma criptográfica
del autor, revisión por pares ni prueba de que las mediciones sean verdaderas.

---

<!-- URIEL:SECTION:ai:START -->
## Usa Uriel con o sin IA

### Nota del mantenedor

The Forge of Uriel se desarrolló con el uso extensivo de GPT-5.6 Sol en modo `ultra`, el cual el mantenedor recomienda para sus pasadas de investigación de largo horizonte y pruebas adversariales más profundas.

Eso es un informe de experiencia, no una dependencia, integración exclusiva, respaldo de privacidad, garantía o sustituto de la verificación determinista. Se pueden utilizar otros sistemas de IA capaces.

### Una IA compatible

Una IA compatible puede ayudar a aclarar, organizar, redactar y criticar.

No puede:

```text
mark Data Readiness PASS
pass an integrity gate
change publication authority
override a deterministic failure
issue a Blessing
```

---

<!-- URIEL:SECTION:privacy:START -->
## Seguridad y privacidad

Uriel está diseñado en torno a:

```text
read-only defaults
exact-root confinement
explicit consent
verified managed copies
immutable generations
```

---

<!-- URIEL:SECTION:trials:START -->
## Las Pruebas de la Forja

La prueba sintética incluida es un conjunto reproducible con 24 problemas
sellados en la clave de respuestas y una rúbrica de 100 puntos. La comprobación
de lanzamiento recalcula el resumen limpio y valida el conjunto; no afirma que
Uriel haya detectado un problema sin un informe ciego posteriormente adjudicado.

```text
python scripts/check_forge_trial.py
```

El método Forge describe el flujo de trabajo público. Su núcleo experimental
local de ejecuciones, estados y verificación ya está disponible:

```text
uriel forge init --root PROJECT --request INIT.json
uriel forge transition --root PROJECT --snapshot EXACT.json --to-state SCOPED --rationale "Scope reviewed"
uriel forge verify --root PROJECT --snapshot EXACT.json
```

Escribe instantáneas privadas e inmutables y no concede autoridad superior. El
exportador saneado y la capa general de prueba de bloqueos/Próximo Movimiento
siguen planificados.

Consulta [`docs/FORGE_TRIALS.md`](docs/FORGE_TRIALS.md) y [`benchmarks/forge_trials/synthetic-001/`](benchmarks/forge_trials/synthetic-001/).

---

<!-- URIEL:SECTION:community:START -->
## Contribuciones

Las contribuciones que mejoren la precisión, portabilidad, accesibilidad, seguridad, documentación, traducciones y flujos de trabajo son bienvenidas.

Comienza con:

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SUPPORT.md`](SUPPORT.md)
- [`SECURITY.md`](SECURITY.md)

---

<!-- URIEL:SECTION:limitations:START -->
## Limitaciones conocidas

The Forge of Uriel está construido para hacer cumplir la honestidad intelectual y la linaje de evidencia, pero tiene límites definidos:

- Uriel no puede inventar datos faltantes ni suministrar mediciones de laboratorio.
- Data Desk informa observaciones estructurales y léxicas acotadas; no es un motor estadístico, un validador semántico ni un sustituto de la inspección de las mediciones y los métodos de origen.
- Las lentes de IA son consultivas y no tienen autoridad sobre las decisiones deterministas de las puertas.
- Una Puerta o Bendición experimental informa que los predicados registrados por Uriel se cumplieron para artefactos exactos. No establece validez de medición, verdad, aceptación editorial ni consenso entre pares.

---

## Citation and License

Los metadatos de citación se proporcionan en [`CITATION.cff`](CITATION.cff). Licencia MIT en [`LICENSE`](LICENSE).
