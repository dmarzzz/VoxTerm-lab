"""WER (Word Error Rate) scoring via jiwer.

Computes corpus-level aggregate WER (standard: total errors / total words)
plus per-sample breakdowns. Always uses sentence-list mode (not concatenated
strings) per jiwer best practices.

Powered by: jiwer (https://github.com/jitsi/jiwer)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import jiwer


# Text normalization: lowercase, strip punctuation, collapse whitespace.
# LibriSpeech references are uppercase with no punctuation except apostrophes.
# Whisper/Qwen3 output has mixed case and punctuation.
NORMALIZE = jiwer.Compose([
    jiwer.ToLowerCase(),
    jiwer.RemovePunctuation(),
    jiwer.RemoveMultipleSpaces(),
    jiwer.Strip(),
    jiwer.ReduceToListOfListOfWords(),
])


@dataclass
class SampleWER:
    """Per-sample WER result."""
    id: str
    wer: float
    substitutions: int
    insertions: int
    deletions: int
    hits: int
    ref_words: int
    hyp_words: int
    reference: str
    hypothesis: str


@dataclass
class AggregateWER:
    """Corpus-level WER result."""
    wer: float
    substitutions: int
    insertions: int
    deletions: int
    hits: int
    total_ref_words: int
    num_samples: int
    samples: list[SampleWER]


def score_wer(
    references: list[str],
    hypotheses: list[str],
    ids: list[str] | None = None,
) -> AggregateWER:
    """Compute WER over paired reference/hypothesis lists.

    Args:
        references: Ground truth transcripts
        hypotheses: Model output transcripts
        ids: Optional sample identifiers

    Returns:
        AggregateWER with corpus-level and per-sample results
    """
    if len(references) != len(hypotheses):
        raise ValueError(
            f"Length mismatch: {len(references)} refs vs {len(hypotheses)} hyps"
        )
    if not references:
        raise ValueError("Empty input")

    if ids is None:
        ids = [str(i) for i in range(len(references))]

    # Per-sample scoring
    samples = []
    for i, (ref, hyp, sid) in enumerate(zip(references, hypotheses, ids)):
        # Handle empty reference or hypothesis
        if not ref.strip() and not hyp.strip():
            samples.append(SampleWER(
                id=sid, wer=0.0,
                substitutions=0, insertions=0, deletions=0, hits=0,
                ref_words=0, hyp_words=0,
                reference=ref, hypothesis=hyp,
            ))
            continue

        if not ref.strip():
            hyp_word_count = len(hyp.split())
            samples.append(SampleWER(
                id=sid, wer=float("inf"),
                substitutions=0, insertions=hyp_word_count, deletions=0, hits=0,
                ref_words=0, hyp_words=hyp_word_count,
                reference=ref, hypothesis=hyp,
            ))
            continue

        out = jiwer.process_words(
            ref, hyp,
            reference_transform=NORMALIZE,
            hypothesis_transform=NORMALIZE,
        )
        ref_word_count = out.substitutions + out.deletions + out.hits
        hyp_word_count = out.substitutions + out.insertions + out.hits

        samples.append(SampleWER(
            id=sid,
            wer=out.wer,
            substitutions=out.substitutions,
            insertions=out.insertions,
            deletions=out.deletions,
            hits=out.hits,
            ref_words=ref_word_count,
            hyp_words=hyp_word_count,
            reference=ref,
            hypothesis=hyp,
        ))

    # Corpus-level aggregate (standard: sum all errors / sum all ref words)
    # Filter out samples with no reference words for aggregate
    valid_refs = [r for r, s in zip(references, samples) if s.ref_words > 0]
    valid_hyps = [h for h, s in zip(hypotheses, samples) if s.ref_words > 0]

    if valid_refs:
        agg = jiwer.process_words(
            valid_refs, valid_hyps,
            reference_transform=NORMALIZE,
            hypothesis_transform=NORMALIZE,
        )
        aggregate_wer = agg.wer
        total_subs = agg.substitutions
        total_ins = agg.insertions
        total_del = agg.deletions
        total_hits = agg.hits
    else:
        aggregate_wer = 0.0
        total_subs = total_ins = total_del = total_hits = 0

    total_ref_words = sum(s.ref_words for s in samples)

    return AggregateWER(
        wer=aggregate_wer,
        substitutions=total_subs,
        insertions=total_ins,
        deletions=total_del,
        hits=total_hits,
        total_ref_words=total_ref_words,
        num_samples=len(samples),
        samples=samples,
    )


def wer_to_dict(result: AggregateWER) -> dict:
    """Convert AggregateWER to a JSON-serializable dict."""
    d = asdict(result)
    # Truncate per-sample ref/hyp text to keep JSON manageable
    for s in d["samples"]:
        s["reference"] = s["reference"][:200]
        s["hypothesis"] = s["hypothesis"][:200]
    return d
