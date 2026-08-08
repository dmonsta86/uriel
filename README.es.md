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

> **Notice**: Este documento es una traducción revisada por IA (AI_SECOND_PASS_REVIEWED). Nota visual: La imagen superior es la versión original en inglés (ENGLISH_FALLBACK). Correcciones de hablantes nativos son bienvenidas.

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

The Forge of Uriel **1.0.0-rc2** es una versión candidata pública de un kit de herramientas de desarrollo y blindaje de investigación de código abierto y local.

```text
uriel --version
# uriel 1.0.0rc2
```

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

Inicializa un espacio de trabajo de evidencia en la raíz de tu proyecto:

```text
uriel init
uriel status
uriel verify
```

---

<!-- URIEL:SECTION:data-readiness:START -->
## Preparación de datos (Puerta 0)

Antes de analizar datos o sacar conclusiones, ejecuta las comprobaciones de Preparación de Datos:

Si la Puerta 0 falla, el análisis posterior se bloquea hasta que se restaure la integridad de los datos.

```text
uriel readiness
```

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

La Bendición de Uriel (*The Blessing of Uriel*) es un certificado de auditoría firmado y vinculado criptográficamente por contenido (`.ublessing`).

Indica que un paquete de investigación ha superado las tres puertas bajo reglas deterministas estrictas. Una Bendición certifica que la evidencia fue verificada; no otorga autoridad divina ni sustituye la revisión por pares.

```text
refuted
impossible
```

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

Las Pruebas de la Forja son demostraciones de referencia reproducibles de las capacidades de comprobación de evidencia y reparación de Uriel.

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
- Las lentes de IA son consultivas y no tienen autoridad sobre las decisiones deterministas de las puertas.
- Una Puerta superada o una Bendición emitida me certifica el rastreo de evidencia; no es una garantía de aceptación en revistas ni de consenso entre pares.

---

## Citation and License

Los metadatos de citación se proporcionan en [`CITATION.cff`](CITATION.cff). Licencia MIT en [`LICENSE`](LICENSE).
