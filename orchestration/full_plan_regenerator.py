from typing import Any, Dict, List, Optional, Tuple

from orchestration.section_bundle_generator import generate_sections_bundle
from orchestration.section_specs import SECTION_SPECS, should_include_section


_FEEDBACK_TEMPLATE = """
USER FEEDBACK (user-authored edits to specific sections — TREAT AS HARD ANCHORS):
{edits_text}

Instructions for this full-plan regeneration:
- Where the user has provided replacement blocks for a section, incorporate their
  exact wording and structural intent into that section's output.
- Where the user left a steering comment, apply it to the relevant section's tone,
  emphasis, or content.
- When other sections reference topics the user just changed, update those
  references to stay coherent with the new wording / direction.
- Do NOT undo the user's changes or paraphrase them away.
""".strip()


def _strip_images(blocks):
    """Drop image blocks (which can carry massive base64 data URIs) before
    serializing edits into the LLM prompt."""
    return [b for b in (blocks or []) if (b or {}).get("type") != "image"]


def _format_edit(section_id: str, edit: Dict[str, Any]) -> str:
    blocks_text_only = _strip_images(edit.get("blocks") or [])
    blocks_repr = repr(blocks_text_only)
    comment = (edit.get("user_comment") or "").strip()
    parts = [f'- Section "{section_id}":']
    if blocks_repr and blocks_repr != "[]":
        parts.append(f"  User-typed blocks (authoritative): {blocks_repr}")
    if comment:
        parts.append(f"  User comment: {comment}")
    return "\n".join(parts)


def regenerate_full_plan(
    *,
    concept: Dict[str, Any],
    existing_sections: List[Dict[str, Any]],
    pending_edits: Dict[str, Any],
    model_name: Optional[str] = None,
    chunk_size: int = 4,
    max_output_tokens: int = 8000,
    deleted_section_ids: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Regenerate all applicable sections using pending_edits as strong context.

    Sections whose id appears in `deleted_section_ids` are skipped entirely —
    they remain absent from the output.

    Returns (new_sections, used_edit_section_ids).
    """
    concept_with_feedback = dict(concept or {})
    used_edit_ids: List[str] = sorted(pending_edits.keys()) if pending_edits else []
    deleted_set = set(deleted_section_ids or [])

    if pending_edits:
        edits_text = "\n".join(
            _format_edit(sid, pending_edits[sid]) for sid in used_edit_ids
        )
        concept_with_feedback["__user_feedback__"] = _FEEDBACK_TEMPLATE.format(
            edits_text=edits_text
        )

    included_specs = [s for s in SECTION_SPECS if should_include_section(s, concept)]
    included_specs.sort(key=lambda s: s.get("order", 0))
    # Skip any section the user has explicitly deleted.
    if deleted_set:
        included_specs = [s for s in included_specs if s.get("id") not in deleted_set]

    new_sections: List[Dict[str, Any]] = []
    chunks = [
        included_specs[i : i + chunk_size]
        for i in range(0, len(included_specs), chunk_size)
    ]
    for idx, specs_chunk in enumerate(chunks):
        include_assumptions = (idx == len(chunks) - 1)
        bundle = generate_sections_bundle(
            concept=concept_with_feedback,
            section_specs=specs_chunk,
            include_assumptions=include_assumptions,
            model_name=model_name or "gpt-5.4-nano-2026-03-17",
            max_output_tokens=max_output_tokens,
            generate_images=False,
        )
        new_sections.extend(bundle.get("sections") or [])

    return new_sections, used_edit_ids
