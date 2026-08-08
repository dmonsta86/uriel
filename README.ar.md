<div dir="rtl">

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

> **Notice**: هذه الوثيقة عبارة عن ترجمة تمت مراجعتها بواسطة الذكاء الاصطناعي (AI_SECOND_PASS_REVIEWED). ملاحظة بصرية: الصورة أعلاه هي النسخة الإنجليزية الأصلية (ENGLISH_FALLBACK). نرحب بتصحيحات المتحدثين الأصليين.

<!-- URIEL:SECTION:mission:START -->
### تطوير وتحصين الأبحاث مفتوحة المصدر والمحلية أولاً

> **هل فكرتك قوية بما يكفي للبقاء على قيد الحياة في المسبك؟**
>
> جلسة استماع عادلة للفكرة. اختبار صارم للأدلة.

يساعد The Forge of Uriel في تحويل الأسئلة الأولية والمشاريع الحالية إلى أبحاث مهيكلة وقابلة للتكرار وجاهزة للتقديم.

يتأكد من البيانات قبل التحليل، ويتتبع الادعاءات الهامة حتى الأدلة المباشرة، ويحفظ التناقضات والقيود، ويكشف التأطير المضلل والاستنتاجات غير المدعومة، ويحول الفحوصات الفاشلة إلى مسارات إصلاح وتقديم ملموسة.

لم يتم تصميمه لجعل البحث يبدو أقوى، بل صُمم ليظهر بدقة مدى قوة البحث وما الذي يجعله أقوى.

```text
Interpret generously.
Test rigorously.
Report honestly.
```

---

<!-- URIEL:SECTION:status:START -->
## حدود الإصدار الحالي

إن The Forge of Uriel **1.0.0-rc2** هو إصدار مرشح عام لمجموعة أدوات تطوير وتحصين الأبحاث مفتوحة المصدر والمحلية أولاً.

```text
uriel --version
# uriel 1.0.0rc2
```

---

<!-- URIEL:SECTION:difference:START -->
## ما الذي يجعله مختلفًا

تتعامل معظم أدوات البحث مع طبقة واحدة: البحث في الأدبيات، الكتابة، الإحصاء، الاقتباسات، القابلية للتكرار، أو المراجعة.

تم بناء The Forge of Uriel لربط السلسلة بأكملها.

### إعطاء الفكرة أعدل جلسة استماع

الصياغة الضعيفة ليست دليلاً على ضعف التفكير. يحفظ Uriel السؤال الأصلي، ويوضح أقوى نسخة قابلة للاختبار، ويسجل التفسيرات المتنافسة، ويوضح الافتراضات الخفية، ويسأل ما هي الأدلة التي قد تدحض الفكرة.

### التحقق من البيانات قبل استخلاص النتائج

تمنع البوابة 0 نتيجة تعتمد على البيانات من الحصول على السلطة حتى تتجاوز عملية إنتاج مجموعة البيانات فحوصات الهوية والتجميع والتطبيع والتسوية والتقادم.

قبل ذلك، تكون الإجابة الصريحة هي:

> **النتيجة لم تُعرف بعد.**

### معاملة الاستنتاجات كادعاءات وليست سلطة موروثة

الاستنتاج المنشور، أو المؤلف المرموق، أو النموذج الواثق، أو قائمة المراجع الطويلة لا تستبدل الأدلة.

يسأل Uriel:

```text
What exactly is being claimed?
Which artifact supports it?
Where is the supporting datapoint?
What contradicts it?
What assumptions does it depend on?
What remains unknown?
What would change the result?
```

### تحدي العمل المكتمل

تختبر البوابات الثلاث الوضوح والأدلة والمتانة التنافسية. يبحث Uriel عن الأدلة المضادة الخفية، والمقامات المخفية، والتعميم المفرط، والتجاوزات السببية، وعدم تطابق الضوابط، والتسريبات، والافتراضات الهشة، والمصادر القديمة، ولغة الملخص التي تتجاوز النتيجة الأساسية.

### الإصلاح بدلاً من مجرد الانتقاد

لا ينبغي أن ينتهي الفحص الفاشل برفض غامض.

يسجل Uriel ما يظل مفيدًا، ويحدد أصغر إصلاح صريح، ويختار أقوى خطوة تالية، ويعد ما يمكن إعداده بأمان، ويحدد الشرط الدقيق لإعادة الفحص.

---

<!-- URIEL:SECTION:intellectual-honesty:START -->
## لا ينبغي أن يكسب البحث بالتأطير

تضعف فجوتان الأبحاث بشكل متكرر:

1. اختفاء الأدلة المضادة، والنتائج الصفرية، والقيود من القصة النهائية؛ و
2. أن يصبح الاستنتاج أوسع أو أكثر يقينًا مما تدعمه الأدلة الأساسية.

يجعل Uriel هذه النقاط دائمة. يسجل ما تم اختباره، وما فشل، وما تم إغفاله، وما يظل غير مؤكد.

---

<!-- URIEL:SECTION:quick-start:START -->
## البدء السريع

قم بتهيئة مساحة عمل الأدلة في جذر مشروعك:

```text
uriel init
uriel status
uriel verify
```

---

<!-- URIEL:SECTION:data-readiness:START -->
## جاهزية البيانات (البوابة 0)

قبل تحليل البيانات أو استخلاص النتائج، قم بتشغيل فحوصات جاهزية البيانات:

إذا فشلت البوابة 0، يتم حظر التحليل اللاحق حتى يتم استعادة نزاهة البيانات.

```text
uriel readiness
```

---

<!-- URIEL:SECTION:gates:START -->
## البوابات الثلاث

### البوابة 1 — النطاق ولغة الادعاءات

تقيم ما إذا كانت الادعاءات الرئيسية محددة بدقة، والمصطلحات متسقة، ويتم التخلص من التجاوزات السببية.

### البوابة 2 — جاهزية البيانات والأدلة المباشرة

تتطلب دعم كل ادعاء جوهري بأدلة مباشرة وقابلة للتتبع وإنتاج بيانات موثوق.

### البوابة 3 — المتانة التنافسية والقيود

تكشف التفسيرات المتنافسة، وانحيازات التأطير، والأدلة المضادة المنسية، وقيود التطبيق.

---

<!-- URIEL:SECTION:blessing:START -->
## بركة أوريل (The Blessing of Uriel)

بركة أوريل (*The Blessing of Uriel*) هي شهادة تدقيق موقعة ومربوطة بالتجزئة المشفرة (`.ublessing`).

وتشير إلى أن حزمة البحث قد اجتازت البوابات الثلاث بنجاح بموجب قواعد حتمية صارمة. تشهد البركة على التحقق من الأدلة؛ ولا تمنح سلطة مطلقة ولا تستبدل مراجعة الأقران.

```text
refuted
impossible
```

---

<!-- URIEL:SECTION:ai:START -->
## استخدم Uriel مع أو بدون الذكاء الاصطناعي

### ملاحظة صانع المشروع

تم تطوير The Forge of Uriel باستخدام مكثف لـ GPT-5.6 Sol في وضع `ultra`.

هذه تقرير تجربة وليست اعتمادًا حصريًا أو بديلًا للتحقق المباشر. يمكن استخدام أنظمة ذكاء اصطناعي أخرى.

### ذكاء اصطناعي متوافق

يمكن للذكاء الاصطناعي المتوافق المساعدة في التوضيح والتنظيم والصياغة والنقد.

ولكنه لا يستطيع:

```text
mark Data Readiness PASS
pass an integrity gate
change publication authority
override a deterministic failure
issue a Blessing
```

---

<!-- URIEL:SECTION:privacy:START -->
## الأمان والخصوصية

تم تصميم Uriel حول المبادئ التالية:

```text
read-only defaults
exact-root confinement
explicit consent
verified managed copies
immutable generations
```

---

<!-- URIEL:SECTION:trials:START -->
## تجارب المسبك (The Forge Trials)

تجارب المسبك هي عروض توضيحية مرجعية قابلة للتكرار لنتائج Uriel.

راجع [`docs/FORGE_TRIALS.md`](docs/FORGE_TRIALS.md) و [`benchmarks/forge_trials/synthetic-001/`](benchmarks/forge_trials/synthetic-001/).

---

<!-- URIEL:SECTION:community:START -->
## المساهمة

نرحب بالمساهمات التي تحسن الدقة والأمان والتوثيق والترجمات.

ابدأ بـ:

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SUPPORT.md`](SUPPORT.md)
- [`SECURITY.md`](SECURITY.md)

---

<!-- URIEL:SECTION:limitations:START -->
## القيود المعروفة

تم بناء The Forge of Uriel لفرض النزاهة الفكرية وتسلسل الأدلة، ولكن له حدود محددة:

- لا يمكن لـ Uriel اختراع بيانات مفقودة أو تقديم قياسات معملية.
- عدسات الذكاء الاصطناعي استشارية ولا تملك سلطة على قرارات البوابات الحتمية.
- اجتياز البوابة أو إصدار البركة يشهد على تتبع الأدلة فقط؛ وليس ضمانًا للقبول في المجلات.

---

## Citation and License

بيانات الاقتباس متوفرة في [`CITATION.cff`](CITATION.cff). الترخيص MIT في [`LICENSE`](LICENSE).


</div>