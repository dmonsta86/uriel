"""Deterministic manuscript prose lint: assistant residue, filler, and overreach.

The lint looks for wording that predictably weakens a research manuscript:
assistant/chat residue, placeholders, stock filler phrases, unsourced
attributions ("studies show" with no citation), hype, proof language for
empirical results, stacked hedges, and a few structural habits common in
machine-drafted text.  Every rule is a fixed, inspectable pattern.  The lint
does not detect authorship, does not judge whether the science is right, and
will both miss problems and flag innocent wording; findings are review leads
with exact locations and concrete rewrites, never accusations.

Levels:

- ``grave``: never acceptable in a manuscript (assistant residue); always a
  blocker.
- ``submission``: acceptable in a working draft, but must be repaired before a
  submission-profile check passes.
- ``style``: advisory only; counted toward the filler-density measure.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .audit import _FALLACIES

PROSE_LINT_VERSION = "uriel-prose-lint-1.0.0"
LEVELS = ("grave", "submission", "style")
PROSE_SECTION_KINDS = frozenset({"abstract", "introduction", "discussion", "conclusion"})
DENSITY_WARN_PER_1000 = 4.0
DENSITY_BLOCK_PER_1000 = 8.0
DENSITY_MIN_WORDS = 150
EM_DASH_WARN_PER_1000 = 6.0

_I = re.IGNORECASE

_CHATBOT: Sequence[Tuple[re.Pattern, str]] = (
    (re.compile(r"\bas an ai\b", _I), "assistant self-reference"),
    (re.compile(r"\bas a (?:large )?language model\b", _I), "assistant self-reference"),
    (re.compile(r"\bi hope this helps\b", _I), "assistant sign-off"),
    (re.compile(r"\blet me know if\b", _I), "assistant sign-off"),
    (re.compile(r"\bfeel free to\b", _I), "assistant sign-off"),
    (re.compile(r"\bi(?:'d| would) be (?:happy|glad) to\b", _I), "assistant offer"),
    (re.compile(r"\bwould you like me to\b", _I), "assistant offer"),
    (re.compile(r"^[ \t]*(?:certainly|sure|absolutely|of course|great question)[!,.]", _I | re.M), "assistant preamble"),
    (re.compile(r"\bhere(?:'s| is) (?:a|an|the|your) (?:revised|updated|rewritten|polished|improved|draft|refined|final) (?:[\w-]+ )?(?:version|draft|text|section|paragraph|abstract|manuscript)\b", _I), "assistant preamble"),
    (re.compile(r"\bi (?:cannot|can't|am unable to|do not have the ability to) (?:access|browse|verify|view|open)\b", _I), "assistant capability disclaimer"),
    (re.compile(r"\b(?:my|the model's) (?:knowledge|training)(?: data)? cut-?off\b", _I), "assistant capability disclaimer"),
    (re.compile(r"\bregenerate response\b", _I), "chat interface residue"),
    (re.compile(r"\bin this (?:response|reply|answer)\b", _I), "chat framing"),
    (re.compile(r"\[\s*insert\b[^\]]{0,80}\]", _I), "unfilled insertion slot"),
    (re.compile(r"<\s*insert\b[^>]{0,80}>", _I), "unfilled insertion slot"),
)

_PLACEHOLDER: Sequence[Tuple[re.Pattern, str]] = (
    (re.compile(r"\b(?:TODO|TBD|TBA|FIXME|XXX+|PLACEHOLDER|UNKNOWN_REQUIRED|UNCITED_CLAIM|MISSING_ATTACHMENT|UNVERIFIED_REQUIREMENT)\b"), "work marker"),
    (re.compile(r"\blorem ipsum\b", _I), "filler text"),
    (re.compile(r"\[\s*(?:citation needed|citation|cite|ref|refs|reference|source|needs? (?:citation|source))\s*\]", _I), "citation slot"),
    (re.compile(r"\(\s*Author,?\s+(?:Year|\d{4})\s*\)", _I), "citation slot"),
    (re.compile(r"\b(?:Figure|Fig\.|Table|Section|Appendix)\s+(?:X|\?+|N)\b"), "cross-reference slot"),
    (re.compile(r"\b(?:19|20)XX\b"), "date slot"),
    (re.compile(r"\bXX(?:\.X+)?\s*%|\b[nN]\s*=\s*X+\b|\bp\s*[=<]\s*X+\b"), "number slot"),
    (re.compile(r"\?{2,}"), "unresolved marker"),
    (re.compile(r"\b(?:fill (?:this|in)|replace me|example only)\b", _I), "template text"),
)

_STOCK_TELL: Sequence[Tuple[re.Pattern, str]] = (
    (re.compile(r"\bdelv(?:e|es|ed|ing)\s+(?:deep(?:er|ly)?\s+)?into\b", _I), "\"delve into\""),
    (re.compile(r"\btapestr(?:y|ies)\b", _I), "\"tapestry\""),
    (re.compile(r"\b(?:is|are|stands? as|serves? as|remains?) a testament to\b", _I), "\"a testament to\""),
    (re.compile(r"\bin today'?s (?:fast-paced|ever-changing|rapidly (?:changing|evolving)|digital|modern|interconnected) (?:world|landscape|era|age|society)\b", _I), "\"in today's ... world\""),
    (re.compile(r"\bever-(?:evolving|changing) (?:landscape|world|field|nature)\b", _I), "\"ever-evolving landscape\""),
    (re.compile(r"\bin the (?:realm|world|sphere) of\b", _I), "\"in the realm of\""),
    (re.compile(r"\bnavigat(?:e|es|ed|ing) the (?:complex(?:ities)?|intricac(?:y|ies)|(?:complex )?landscape|maze)\b", _I), "\"navigate the complexities\""),
    (re.compile(r"\bunlock(?:s|ed|ing)? the (?:full )?(?:potential|power|secrets?|mysteries)\b", _I), "\"unlock the potential\""),
    (re.compile(r"\bharness(?:es|ed|ing)? the (?:full )?(?:power|potential)\b", _I), "\"harness the power\""),
    (re.compile(r"\bembark(?:s|ed|ing)? on (?:a|an|this|the|our) (?:journey|quest|exploration|endeavou?r)\b", _I), "\"embark on a journey\""),
    (re.compile(r"\b(?:a )?(?:plethora|myriad) of\b", _I), "\"a plethora/myriad of\""),
    (re.compile(r"\bthe intricate (?:interplay|dance|web|tapestry)\b", _I), "\"the intricate interplay\""),
    (re.compile(r"\bit is (?:important|worth|crucial|essential|vital) to (?:note|highlight|emphasi[sz]e|mention|recogni[sz]e) that\b", _I), "\"it is important to note that\""),
    (re.compile(r"\b(?:a|the) (?:double-edged sword|game[- ]changer|silver bullet|north star)\b", _I), "cliche metaphor"),
    (re.compile(r"\bstands? at the (?:intersection|crossroads) of\b", _I), "\"stands at the intersection of\""),
    (re.compile(r"\bnot (?:just|only|merely) (?:a|an) [\w-]+,? but (?:a|an|also)\b", _I), "\"not just X but Y\" construction"),
)

_STYLE_WORDS = re.compile(
    r"\b(?:crucial|pivotal|vital|comprehensive|seamless(?:ly)?|leverag(?:e|es|ed|ing)|utili[sz](?:e|es|ed|ing)|"
    r"foster(?:s|ed|ing)?|holistic|multifaceted|nuanced|intricate|noteworthy|commendable|meticulous(?:ly)?|"
    r"showcas(?:e|es|ed|ing)|streamlin(?:e|es|ed|ing)|elevat(?:e|es|ed|ing)|empower(?:s|ed|ing)?|"
    r"bolster(?:s|ed|ing)?|underscor(?:e|es|ed|ing)|garner(?:s|ed|ing)?|invaluable|realm|landscape|"
    r"shed(?:s|ding)? (?:new )?light on|pave(?:s|d)? the way|at the forefront of|plays? a (?:crucial|pivotal|vital|key) role|"
    r"a deeper understanding|in conclusion|in summary|to summari[sz]e)\b",
    _I,
)

_HYPE = re.compile(
    r"\b(?:groundbreaking|ground-breaking|revolutionary|revolutioni[sz]e[sd]?|paradigm[- ]shift(?:ing)?|"
    r"game[- ]chang(?:er|ing)|cutting[- ]edge|unprecedented|transformative|world[- ]class|trailblazing|"
    r"breakthrough|remarkabl[ey]|astonishing(?:ly)?|unparalleled|first[- ]ever|world'?s first|"
    r"(?:the )?first (?:study |work |paper )?to (?:show|demonstrate|reveal|establish))\b",
    _I,
)

_OVERCLAIM = re.compile(
    r"\b(?:prove[sd]?|proven|proving|prove that|conclusively|definitively|undeniabl[ey]|unquestionabl[ey]|"
    r"indisputabl[ey]|incontrovertibl[ey]|irrefutabl[ey]|beyond (?:any |a )?(?:reasonable |all )?doubt|"
    r"settles? the (?:question|debate|matter)|definitive (?:proof|evidence|answer))\b",
    _I,
)
_PROOF_OK = re.compile(r"\bproo?f[- ]of[- ]concept\b|\b(?:theorem|lemma|proposition|corollary)\b", _I)

_VAGUE_ATTRIBUTION: Sequence[re.Pattern] = (
    re.compile(
        r"(?:\b(?:studies|research|prior work|previous work|the literature|literature|experts|scientists|researchers|scholars)|"
        r"\b(?:growing|mounting|substantial|considerable|extensive|ample|existing|prior|accumulating) (?:body of )?evidence)"
        r"\s+(?:has\s+|have\s+)?(?:consistently\s+|repeatedly\s+|long\s+)?"
        r"(?:shown|show|shows|suggests?|suggested|indicates?|indicated|demonstrated?|demonstrates|agrees?|agreed|believes?|found|finds|confirms?|confirmed)\b",
        _I,
    ),
    re.compile(r"\b(?:many|several|numerous|various|some|most|multiple)\s+(?:prior\s+|previous\s+|recent\s+)?(?:studies|researchers|scientists|experts|authors|scholars|papers|reports)\b", _I),
    re.compile(r"\bit\s+(?:is|has been)\s+(?:widely|well|generally|commonly|universally|increasingly)\s+(?:known|accepted|believed|recogni[sz]ed|established|acknowledged|reported)\b", _I),
    re.compile(r"\b(?:some|many|most|critics|proponents)\s+(?:argue|say|claim|believe|suggest)\b", _I),
)
_CITATION_PRESENT = re.compile(
    r"\[@[^\]]+\]|\{\{dp:[^}]+\}\}|\[\d+(?:\s*[,\u2013-]\s*\d+)*\]|"
    r"\([A-Z][A-Za-z'\-]+(?: (?:et al\.|and|&) ?[A-Z]?[A-Za-z'\-]*)?,? (?:19|20)\d{2}[a-z]?(?:[;,][^)]*)?\)"
)

_HEDGE_PAIR = re.compile(
    r"\b(?:may|might|could|can)\s+(?:potentially|possibly|perhaps|conceivably|arguably)\b|"
    r"\b(?:possibly|potentially|perhaps)\s+(?:may|might|could|suggest|indicate)\b",
    _I,
)
_HEDGE_WORD = re.compile(
    r"\b(?:may|might|could|possibly|potentially|perhaps|arguably|somewhat|seemingly|presumably|conceivably|"
    r"appears? to|seems? to|tends? to|likely)\b",
    _I,
)
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2705\u2728\u274c\u2b50\u2757]")
_TRANSITION_OPENER = re.compile(
    r"^(?:moreover|furthermore|additionally|notably|importantly|interestingly|crucially|overall|ultimately|"
    r"in addition|consequently|indeed)\b",
    _I,
)
_BOLD_LABEL = re.compile(r"\*\*[^*\n]{1,48}:\*\*|__[^_\n]{1,48}:__")
_LIST_LINE = re.compile(r"^\s*(?:[-*+]\s+|\d{1,2}[.)]\s+)")
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_FENCE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.S | re.M)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_URL = re.compile(r"\bhttps?://\S+|\bdoi:\S+", _I)
_MARKUP = re.compile(r"\{\{[^}]*\}\}|\[@[^\]]*\]|\[claim:[^\]]*\]")


def _blank(match: "re.Match[str]") -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def mask_non_prose(text: str) -> str:
    """Blank comments, code, and URLs while keeping every offset and line."""
    masked = _HTML_COMMENT.sub(_blank, text)
    masked = _FENCE.sub(_blank, masked)
    masked = _INLINE_CODE.sub(_blank, masked)
    return _URL.sub(_blank, masked)


def word_count(text: str) -> int:
    return len(_WORD.findall(_MARKUP.sub(" ", mask_non_prose(text))))


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _excerpt(text: str, start: int, end: int, *, pad: int = 0) -> str:
    left = max(0, start - pad)
    right = min(len(text), end + pad)
    return " ".join(text[left:right].split())[:200]


def _sentences(masked: str) -> Iterable[Tuple[int, int, str]]:
    """Yield (start, end, text) for prose sentences, skipping headings/tables/lists markers."""
    offset = 0
    for paragraph in re.split(r"(\n\s*\n)", masked):
        if not paragraph.strip() or paragraph.strip() == "":
            offset += len(paragraph)
            continue
        lines = paragraph.split("\n")
        if all(line.lstrip().startswith(("#", "|")) or not line.strip() for line in lines):
            offset += len(paragraph)
            continue
        position = 0
        for piece in re.split(r"(?<=[.!?])\s+(?=[\"'(\[A-Z0-9])|\n(?=\s*(?:[-*+]|\d{1,2}[.)])\s)|\n(?=\s*#)", paragraph):
            found = paragraph.find(piece, position)
            if found < 0:
                found = position
            position = found + len(piece)
            stripped = piece.strip()
            if not stripped or stripped.startswith(("#", "|")):
                continue
            yield offset + found, offset + found + len(piece), piece
        offset += len(paragraph)


def _issue(code: str, category: str, level: str, text: str, start: int, end: int, message: str, **detail: Any) -> Dict[str, Any]:
    return {
        "code": code,
        "category": category,
        "level": level,
        "line": _line_of(text, start),
        "excerpt": _excerpt(text, start, end, pad=0),
        "message": message,
        "detail": detail,
    }


def lint_text(text: str, *, section_kind: Optional[str] = None) -> Dict[str, Any]:
    """Lint one manuscript text and return located, levelled issues."""
    masked = mask_non_prose(text)
    issues: List[Dict[str, Any]] = []

    for pattern, label in _CHATBOT:
        for match in pattern.finditer(masked):
            issues.append(_issue(
                "ASSISTANT_RESIDUE", "assistant_residue", "grave", masked, match.start(), match.end(),
                "Text addressed to a chat user or describing an assistant ({0}) does not belong in a manuscript.".format(label),
                pattern=label,
            ))
    for pattern, label in _PLACEHOLDER:
        for match in pattern.finditer(masked):
            issues.append(_issue(
                "PLACEHOLDER_TEXT", "placeholder", "submission", masked, match.start(), match.end(),
                "An unfilled {0} remains in the text.".format(label),
                pattern=label,
            ))
    tells = 0
    for pattern, label in _STOCK_TELL:
        for match in pattern.finditer(masked):
            tells += 1
            issues.append(_issue(
                "STOCK_PHRASE", "filler", "submission", masked, match.start(), match.end(),
                "The stock phrase {0} adds no information; state the specific fact or delete the phrase.".format(label),
                pattern=label,
            ))
    for match in _HYPE.finditer(masked):
        issues.append(_issue(
            "HYPE_LANGUAGE", "hype", "submission", masked, match.start(), match.end(),
            "Promotional wording asks the reader to accept importance or novelty instead of showing it.",
            term=match.group(0),
        ))
    style_hits = list(_STYLE_WORDS.finditer(masked))
    for match in style_hits:
        issues.append(_issue(
            "FILLER_WORD", "filler", "style", masked, match.start(), match.end(),
            "This word is overused in machine-drafted text and is usually replaceable by a specific statement.",
            term=match.group(0),
        ))

    transition_count = 0
    previous_opener: Optional[str] = None
    run_length = 0
    for start, end, sentence in _sentences(masked):
        has_citation = bool(_CITATION_PRESENT.search(text[start:end]))
        for pattern in _VAGUE_ATTRIBUTION:
            match = pattern.search(sentence)
            if match and not has_citation:
                issues.append(_issue(
                    "UNSOURCED_ATTRIBUTION", "attribution", "submission", masked,
                    start + match.start(), start + match.end(),
                    "The sentence attributes a finding to unnamed studies, experts, or common knowledge without a citation.",
                    phrase=match.group(0),
                ))
                break
        for match in _OVERCLAIM.finditer(sentence):
            if _PROOF_OK.search(sentence):
                continue
            issues.append(_issue(
                "PROOF_LANGUAGE", "overclaim", "submission", masked,
                start + match.start(), start + match.end(),
                "Empirical results support, contradict, or fail to distinguish hypotheses; they do not prove them.",
                term=match.group(0),
            ))
        pair = _HEDGE_PAIR.search(sentence)
        hedges = len(_HEDGE_WORD.findall(sentence))
        if pair or hedges >= 3:
            anchor = pair or _HEDGE_WORD.search(sentence)
            assert anchor is not None
            issues.append(_issue(
                "HEDGE_STACK", "hedging", "style", masked, start + anchor.start(), start + anchor.end(),
                "Stacked hedges make the claim's actual strength unreadable; state the uncertainty once, precisely.",
                hedge_count=hedges,
            ))
        for name, pattern, explanation in _FALLACIES:
            match = pattern.search(sentence)
            if match:
                issues.append(_issue(
                    "REASONING_PATTERN", "reasoning", "submission", masked,
                    start + match.start(), start + match.end(),
                    explanation, pattern=name,
                ))
        stripped = sentence.strip().lstrip("\"'([")
        if _TRANSITION_OPENER.match(stripped):
            transition_count += 1
        first = stripped.split(" ", 1)[0].strip(",;:").casefold() if stripped else ""
        if first and first == previous_opener:
            run_length += 1
            if run_length == 3:
                issues.append(_issue(
                    "REPETITIVE_OPENER", "rhythm", "style", masked, start, end,
                    "Three or more consecutive sentences open with the same word.",
                    opener=first,
                ))
        else:
            run_length = 1
        previous_opener = first

    for match in _EMOJI.finditer(masked):
        issues.append(_issue(
            "EMOJI", "formatting", "submission", masked, match.start(), match.end(),
            "Pictographs do not belong in manuscript prose.",
        ))
    for match in _BOLD_LABEL.finditer(masked):
        issues.append(_issue(
            "INLINE_BOLD_LABEL", "formatting", "style", masked, match.start(), match.end(),
            "Bold run-in labels inside prose read as slide notes; use a heading or a topic sentence.",
        ))

    words = word_count(text)
    per_k = 1000.0 / words if words else 0.0
    if section_kind in PROSE_SECTION_KINDS:
        list_lines = [m for m in re.finditer(r"(?m)^.*$", masked) if _LIST_LINE.match(m.group(0))]
        if len(list_lines) >= 3:
            first_line = list_lines[0]
            issues.append(_issue(
                "LIST_IN_PROSE_SECTION", "formatting", "style", masked, first_line.start(), first_line.end(),
                "This section is normally continuous argument; a bullet list hides how the points connect.",
                list_lines=len(list_lines),
            ))
    em_dashes = masked.count("\u2014") + len(re.findall(r"\s--\s", masked))
    if words and em_dashes >= 3 and em_dashes * per_k > EM_DASH_WARN_PER_1000:
        first_dash = masked.find("\u2014")
        first_dash = first_dash if first_dash >= 0 else 0
        issues.append(_issue(
            "EM_DASH_DENSITY", "rhythm", "style", masked, first_dash, first_dash + 1,
            "Heavy em-dash use fragments sentences; prefer commas, colons, or separate sentences.",
            count=em_dashes, per_1000_words=round(em_dashes * per_k, 2),
        ))
    if words and transition_count >= 3 and transition_count * per_k > DENSITY_WARN_PER_1000:
        issues.append(_issue(
            "TRANSITION_CHAIN", "rhythm", "style", masked, 0, 0,
            "Many sentences open with stock transitions (Moreover, Furthermore, Notably...); let the logic carry the link.",
            count=transition_count, per_1000_words=round(transition_count * per_k, 2),
        ))

    filler_count = tells + len(style_hits)
    density = round(filler_count * per_k, 2) if words else 0.0
    if words >= DENSITY_MIN_WORDS and density >= DENSITY_WARN_PER_1000:
        level = "submission" if density >= DENSITY_BLOCK_PER_1000 else "style"
        issues.append(_issue(
            "FILLER_DENSITY", "filler", level, masked, 0, 0,
            "Stock phrases and filler words occur {0} times per 1,000 words (advisory at {1}, blocking at {2} for submission).".format(
                density, DENSITY_WARN_PER_1000, DENSITY_BLOCK_PER_1000),
            per_1000_words=density, count=filler_count, words=words,
        ))

    issues.sort(key=lambda row: (row["line"], LEVELS.index(row["level"]), row["code"], row["excerpt"]))
    return {
        "version": PROSE_LINT_VERSION,
        "word_count": words,
        "filler_per_1000_words": density,
        "issue_count": len(issues),
        "counts": {level: sum(1 for row in issues if row["level"] == level) for level in LEVELS},
        "issues": issues,
        "boundaries": {
            "authorship_detected": False,
            "scientific_truth_decided": False,
            "rewrites_performed": 0,
        },
    }


REPAIRS: Dict[str, List[str]] = {
    "ASSISTANT_RESIDUE": [
        "Delete the conversational sentence; a manuscript addresses readers, not a chat user.",
        "Re-read the surrounding paragraph for other pasted assistant output and remove it.",
        "Rewrite the passage yourself from the underlying evidence rather than editing assistant output in place.",
    ],
    "PLACEHOLDER_TEXT": [
        "Replace the slot with the real value, citation, or cross-reference, bound to its source.",
        "Delete the sentence if the information does not exist yet.",
        "Move the open item to the project's reminders and keep it out of the manuscript text.",
    ],
    "STOCK_PHRASE": [
        "Delete the phrase and check whether the sentence still says something specific.",
        "Replace it with the concrete fact, quantity, or comparison it was gesturing at.",
        "Merge the sentence into its neighbour if it only announces what comes next.",
    ],
    "HYPE_LANGUAGE": [
        "Replace the adjective with the measured result that would justify it.",
        "Keep novelty wording only where the recorded prior-work search supports it, and cite that search.",
        "Let readers judge importance from the effect size, scope, and limitations.",
    ],
    "FILLER_WORD": [
        "Use the plainer word (use, important, show, help) or delete it.",
        "Replace the general quality word with the specific property you measured.",
        "Leave it when it is a defined technical term in your field.",
    ],
    "UNSOURCED_ATTRIBUTION": [
        "Cite the specific studies with [@key] references that are held and verified in references.json.",
        "Name the evidence directly (dataset, measurement, or bound datapoint) instead of unnamed authorities.",
        "Delete the attribution and state the claim as your own hypothesis or assumption.",
    ],
    "PROOF_LANGUAGE": [
        "Use 'supports', 'is consistent with', or 'did not detect', and report the exact result.",
        "Keep 'prove' only for a formal mathematical proof and label it as such.",
        "State what alternative explanations remain and what result would overturn the conclusion.",
    ],
    "HEDGE_STACK": [
        "Keep one hedge and attach it to the specific source of uncertainty.",
        "Replace the hedges with the interval, effect size, or sample limitation that creates the uncertainty.",
        "Split speculation into a sentence explicitly labelled as speculation.",
    ],
    "REASONING_PATTERN": [
        "Replace the appeal with the direct evidence for the claim.",
        "Name and address the alternatives the wording excludes.",
        "Narrow the conclusion to what the evidence shows.",
    ],
    "REPETITIVE_OPENER": [
        "Vary sentence structure so each sentence starts with its real subject.",
        "Combine the sentences where they share a subject.",
        "Turn the run into a short table if it is a repeated list of parallel results.",
    ],
    "EMOJI": [
        "Delete the pictograph.",
        "Replace a status symbol with words such as 'passed' or 'not tested'.",
        "Move visual markers into a figure or table legend if they carry meaning.",
    ],
    "INLINE_BOLD_LABEL": [
        "Promote the label to a subsection heading.",
        "Rewrite it as a topic sentence.",
        "Remove the emphasis and keep the plain sentence.",
    ],
    "LIST_IN_PROSE_SECTION": [
        "Rewrite the list as connected paragraphs that state how the points relate.",
        "Move enumerations of parallel items into a table.",
        "Keep a list only for a genuinely sequential procedure, and introduce it with a full sentence.",
    ],
    "EM_DASH_DENSITY": [
        "Replace most em-dashes with commas, parentheses, or colons.",
        "Split long dash-joined sentences into two sentences.",
        "Keep dashes only for a single deliberate aside per paragraph.",
    ],
    "TRANSITION_CHAIN": [
        "Delete stock transitions and let the logical connection show through the content.",
        "Use a specific connective (because, therefore, despite) only where it is true.",
        "Reorder paragraphs so each follows from the previous one.",
    ],
    "FILLER_DENSITY": [
        "Work through the listed filler phrases and delete or replace each with a specific statement.",
        "Rewrite the densest paragraphs from the evidence outward rather than editing word by word.",
        "Ask a human co-author to read the section aloud and cut everything that does not carry information.",
    ],
}


def repairs_for(code: str) -> List[str]:
    return list(REPAIRS.get(code, [
        "Rewrite the passage plainly from the underlying evidence.",
        "Delete the passage if it carries no information.",
        "Ask an independent reader to check the revised wording.",
    ]))


__all__ = [
    "LEVELS",
    "PROSE_LINT_VERSION",
    "PROSE_SECTION_KINDS",
    "REPAIRS",
    "lint_text",
    "mask_non_prose",
    "repairs_for",
    "word_count",
]
