<div dir="rtl">

<p align="center">
  <img
    src="docs/assets/i18n/ar/uriel-forge-hero.png"
    alt="يُظهر مِصهَر أوريئيل باحثًا حدّادًا بلا أجنحة، يقظًا ومتعاونًا، يختبر فكرة بحثية وسط رموز جاهزية البيانات والترتيب الحتمي وتتبع الأدلة والأدلة المخالفة والبوابات الثلاث والإصلاح والتقديم والتحقق."
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

> **تنبيه**: خضعت هذه الوثيقة لمراجعة ثانية بمساعدة الذكاء الاصطناعي (AI_SECOND_PASS_REVIEWED). الملصق إصدار موطّن راجعه الذكاء الاصطناعي (LOCALIZED_AI_REVIEWED)، لكن نصه المرئي ما زال يحتاج إلى مراجعة متحدث أصلي (AI_ASSISTED_REQUIRES_NATIVE_REVIEW). نرحب بالتصحيحات.

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

ثبّت من نسخة المستودع من دون تبعيات تشغيل أو بناء معزول يحتاج إلى الشبكة:

```text
python -m pip install --no-deps --no-build-isolation .
uriel start --root ../my-study --kind new_idea --title "My study" --question "What would change my conclusion?"
uriel status --root ../my-study
uriel verify --root ../my-study
```

اسم حزمة التوزيع: `uriel-research`. واسم الاستيراد في Python وأمر CLI:
`uriel`.

لمسار الملف الواحد بلا تثبيت، راجع
[`docs/GETTING_STARTED_FREE.md`](docs/GETTING_STARTED_FREE.md).

---

<!-- URIEL:SECTION:data-readiness:START -->
## جاهزية البيانات (البوابة 0)

في فرع `main` المعتمد، يستطيع مسار `uriel data` المحلي التجريبي تخطيط ملفات CSV وTSV وJSON وJSONL والنص وMarkdown بترميز UTF-8 وختمها؛ وإنشاء ملفات تعريف بنيوية وأجيال غير قابلة للتغيير؛ ومعاينة الفروق؛ والحفاظ على كل سجل أثناء المطابقة؛ وإعادة تحليل الارتباط بالبيانات الخام والتحقق منه بصورة مستقلة. وهو لا ينفذ الصيغ، ولا يخمّن الوحدات أو الأنواع الدلالية، ولا ينشئ نتائج علمية، ولا يمنح صلاحية البوابة 0. ولا تبدأ البوابة 0 إلا بعد أن تصرّح صراحةً بهوية السجلات لجيل محدد بدقة.

بعد أن يعيد `uriel data inspect` معرّف الجيل، أنشئ SortSpec المرتبط بذلك الجيل وافحصه:

```text
uriel readiness init-sort-spec --root ../my-study --generation <GENERATION_ID> --keys id
uriel readiness check --root ../my-study --generation <GENERATION_ID>
uriel readiness status --root ../my-study --generation <GENERATION_ID>
```

يربط إيصال v2 سلالة البيانات الخام، وإصدارات المحلل والسياسة، ومعرّفات الأعمدة الثابتة، والترتيب، وقواعد التكرار والقيم الخالية، والمطابقة، وخطة التحليل، وSortSpec النشط المحدد. وتحظر الحالة المفقودة أو القديمة أو المعدّلة أو الملتبسة التحليل اللاحق. وإذا وُجد أكثر من SortSpec، فحدّد مساره الدقيق صراحةً.

تتطلب حزم الأجيال الموجّهة إلى الذكاء الاصطناعي إيصال PASS وصفوفًا وأعمدةً لازمة للمهمة. ويبلغ حدها الأقصى 1,000 صف و1 MiB، وتدعم حجب القيم، ولا تملك أي صلاحية على البوابات أو النشر أو النتائج أو Blessings. وتعلن كل حزمة وضعًا استشاريًا للقراءة فقط: تُمنع الشبكة وshell والكتابة في الحزمة أو المشروع، ويُحدّ الإخراج المطلوب إلى 128 KiB و15 دقيقة.

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

بركة أوريل حزمة إثبات تجريبية موجّهة بالمحتوى. تربط نسخة محددة تمامًا من
المشروع بقرارات البوابات المسجلة والإيصالات والقيود وإعادة حساب المتحقق المستقل.

تعني أن الشروط المسجلة نجحت لتلك الملفات المرتبطة تحديدًا. وليست تحققًا علميًا
مستقلًا، أو توقيعًا تشفيريًا للمؤلف، أو مراجعة أقران، أو دليلًا على صحة القياسات.

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

التجربة الاصطناعية المرفقة حزمة قابلة للتكرار تضم 24 مشكلة مختومة في مفتاح
الإجابة ومقياس تحكيم من 100 نقطة. يعيد فحص الإصدار حساب الملخص النظيف ويتحقق
من سلامة الحزمة؛ ولا يدّعي أن Uriel اكتشف مشكلة ما لم يُقدَّم تقرير أعمى ويُحكَّم.

```text
python scripts/check_forge_trial.py
```

تصف Forge Method سير العمل العام. وأصبحت نواتها التجريبية المحلية للتشغيل
والحالات والتحقق متاحة الآن:

```text
uriel forge init --root PROJECT --request INIT.json
uriel forge transition --root PROJECT --snapshot EXACT.json --to-state SCOPED --rationale "Scope reviewed"
uriel forge verify --root PROJECT --snapshot EXACT.json
```

تكتب لقطات خاصة غير قابلة للتغيير ولا تمنح أي صلاحية للأنظمة الأعلى. ولا يزال
المُصدِّر المنقّح ومسار إثبات العوائق/الخطوة التالية العام مخططًا لهما.

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
- لا يعرض Data Desk سوى ملاحظات بنيوية ومعجمية محدودة؛ فهو ليس محركًا إحصائيًا أو مدققًا دلاليًا ولا بديلًا عن فحص القياسات والأساليب الأصلية.
- عدسات الذكاء الاصطناعي استشارية ولا تملك سلطة على قرارات البوابات الحتمية.
- لا تفيد البوابة أو البركة التجريبية إلا بأن شروط Uriel المسجلة نجحت للملفات المرتبطة تحديدًا؛ ولا تثبت صلاحية القياس أو الحقيقة أو القبول في مجلة أو إجماع الأقران.

---

## Citation and License

بيانات الاقتباس متوفرة في [`CITATION.cff`](CITATION.cff). الترخيص MIT في [`LICENSE`](LICENSE).


</div>
