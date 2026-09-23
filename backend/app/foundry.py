"""Azure AI Foundry integration with intelligent local study fallback engine."""

from __future__ import annotations

import base64
import io
import json
import logging
import random
import re
from typing import TYPE_CHECKING, Optional

from pypdf import PdfReader
from .config import (
    AZURE_AI_AGENT_NAME,
    AZURE_AI_AGENT_VERSION,
    AZURE_AI_API_KEY,
    AZURE_MODEL_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    IS_AZURE_CONFIGURED,
)

if TYPE_CHECKING:
    from fastapi import UploadFile

logger = logging.getLogger(__name__)

# Token / length guardrails
MAX_TEXT_CHARS = 100_000  # keep prompts within reasonable limits
MAX_SENTENCES_FOR_FALLBACK = 400


class FoundryClient:
    """Calls Azure AI Foundry Responses API when configured, or uses smart study analysis."""

    def __init__(self) -> None:
        self.azure_ready = False
        if IS_AZURE_CONFIGURED:
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    base_url=AZURE_OPENAI_ENDPOINT,
                    api_key="placeholder",
                    default_headers={"api-key": AZURE_AI_API_KEY},
                )
                self.azure_ready = True
                logger.info("FoundryClient initialized with Azure AI Foundry endpoint: %s", AZURE_OPENAI_ENDPOINT)
            except Exception as exc:
                logger.warning("Failed to initialize Azure OpenAI client: %s. Using local engine.", exc)
        else:
            logger.info("FoundryClient running with smart local study document intelligence.")

    def upload_pdf(self, upload_file: UploadFile, file_bytes: Optional[bytes] = None) -> str:
        """Read PDF bytes, base64-encode, return as JSON payload."""
        filename = upload_file.filename or "notes.pdf"
        raw_bytes = file_bytes if file_bytes is not None else upload_file.file.read()
        b64 = base64.b64encode(raw_bytes).decode("utf-8")
        logger.info("Processed %s (%d bytes)", filename, len(raw_bytes))
        return json.dumps({
            "filename": filename,
            "data_uri": f"data:application/pdf;base64,{b64}",
            "raw_base64": b64,
        })

    def delete_file(self, file_id: str) -> None:
        """No-op — inline base64 needs no cleanup."""
        pass

    def run_study_agent(self, file_id: str, action: str) -> dict:
        """Execute study agent on the document."""
        file_info = json.loads(file_id)

        # Extract text up-front so we can always feed document content to the model/fallback.
        filename, extracted_text = _extract_pdf_text(file_info)
        file_info["extracted_text"] = extracted_text  # keep for fallback reuse

        # 1. Try Azure AI Foundry if configured
        if self.azure_ready:
            prompt = self._build_prompt(action, filename, extracted_text)
            try:
                response = self.client.responses.create(
                    model=AZURE_MODEL_DEPLOYMENT,
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_file",
                                    "filename": filename,
                                    "file_data": file_info["data_uri"],
                                },
                                {"type": "input_text", "text": prompt},
                            ],
                        }
                    ],
                    extra_body={
                        "agent_reference": {
                            "name": AZURE_AI_AGENT_NAME,
                            "version": AZURE_AI_AGENT_VERSION,
                            "type": "agent_reference",
                        },
                    },
                    timeout=180,
                )
                logger.info("Azure response received for action=%s", action)
                output_text = getattr(response, "output_text", None)
                if not output_text and hasattr(response, "choices") and response.choices:
                    output_text = response.choices[0].message.content
                res_dict = self._extract_json(output_text)
                if isinstance(res_dict, dict):
                    res_dict = _normalize_summary_response(res_dict)
                return res_dict
            except Exception as exc:
                logger.warning("Azure Agent call failed (%s). Falling back to local study analyzer.", exc)

        # 2. Local intelligent PDF analyzer fallback
        return self._run_local_study_engine(file_info, action)

    def _run_local_study_engine(self, file_info: dict, action: str) -> dict:
        """Extract text from PDF and generate structured summary or MCQs."""
        filename = file_info.get("filename", "notes.pdf")
        extracted_text = file_info.get("extracted_text", "")

        if not extracted_text:
            extracted_text = f"Study material from {filename}. Includes key definitions, concepts, and principles."

        lines = [re.sub(r'\s+', ' ', line).strip() for line in extracted_text.splitlines() if line.strip()]
        sentences = _split_sentences(extracted_text)

        if action == "summary":
            return self._generate_local_summary(filename, extracted_text, lines, sentences)
        elif action == "mcqs":
            return self._generate_local_mcqs(filename, extracted_text, lines, sentences)
        else:
            raise ValueError(f"Unsupported action: {action}")

    def _generate_local_summary(self, filename: str, full_text: str, lines: list[str], sentences: list[str]) -> dict:
        title = _infer_title(filename, lines)

        # Build a genuinely document-derived overview by chunking sentences.
        chunks = _chunk_sentences(sentences, chunk_size=6)
        overview_blocks = []

        # Block 1: concise topic overview derived from the first meaningful chunk.
        overview_text = " ".join(chunks[0][:4]) if chunks else f"This document covers the core principles of {title}."
        overview_blocks.append({
            "heading": f"{title} Overview",
            "content": f"**{title}** — {overview_text}",
            "bullet_points": [],
            "numbered_points": [],
        })

        # Block 2: "Why It Matters" from sentences signalling purpose/importance.
        why_bullets = []
        purpose_keywords = ["allows", "enables", "provides", "used to", "used for", "importance", "purpose", "foundation", "benefit", "helps", "ensures", "supports"]
        for s in sentences:
            s_low = s.lower()
            if any(k in s_low for k in purpose_keywords):
                clean_s = s.strip()
                if 20 < len(clean_s) < 200 and clean_s not in why_bullets:
                    why_bullets.append(clean_s)
                if len(why_bullets) >= 4:
                    break
        if len(why_bullets) < 2:
            why_bullets = [f"Establishes the foundational principles of **{title}**.", "Provides structured concepts for practical application."]
        overview_blocks.append({
            "heading": "Why It Matters",
            "content": "",
            "bullet_points": why_bullets,
            "numbered_points": [],
        })

        # Block 3: Key Concepts & Principles — extract definitions from the text.
        concept_bullets = _extract_definitions(sentences, title)
        if len(concept_bullets) < 3:
            concept_bullets += [f"**{title}**: The primary subject introduced in the document."]
        overview_blocks.append({
            "heading": "Key Concepts & Principles",
            "content": "",
            "bullet_points": concept_bullets[:6],
            "numbered_points": [],
        })

        # Block 4: Structural hierarchy / steps if present.
        step_items = _extract_steps(sentences)
        if step_items:
            overview_blocks.append({
                "heading": "Structural Hierarchy & Process Flow",
                "content": "",
                "bullet_points": [],
                "numbered_points": step_items[:10],
            })

        main_summary = _overview_blocks_to_markdown(overview_blocks)

        # Detailed sections from heading-like lines, or chunked sentences.
        sections = _build_sections(lines, sentences)

        # Key points: pick the most informative sentences/lines.
        key_points = _extract_key_points(lines, sentences, title)

        # Key terms: extract glossary entries from the document.
        key_terms = _extract_key_terms(full_text, sentences, title)

        # Study tips.
        study_tips = [
            f"Create a mind-map of the key sections in '{title}' to visualise relationships between topics.",
            "Use active recall: cover your notes and try to recite each section heading and its main idea.",
            "Generate your own MCQs from the Key Terms glossary and test yourself without looking at the definitions.",
            "Relate each section to a real-world application or example to anchor abstract concepts in memory.",
            "Spaced repetition: review this summary after 1 day, 3 days, and 7 days for maximum retention.",
            "Focus extra time on any Key Terms with definitions longer than two sentences — they indicate complex concepts.",
        ]

        return {
            "summary": main_summary,
            "overview_blocks": overview_blocks,
            "sections": sections,
            "key_points": key_points,
            "key_terms": key_terms,
            "study_tips": study_tips,
            "mcqs": [],
        }

    def _generate_local_mcqs(self, filename: str, full_text: str, lines: list[str], sentences: list[str]) -> dict:
        title = _infer_title(filename, lines)
        mcqs: list[dict] = []

        # Strategy 1: definition-based questions.
        definitions = _extract_definition_pairs(sentences)
        random.shuffle(definitions)
        for term, definition in definitions:
            if len(mcqs) >= 5:
                break
            # Build distractors from other terms.
            other_terms = [t for t, _ in definitions if t.lower() != term.lower()]
            distractors = _make_distractors(term, definition, other_terms)
            options = [definition] + distractors[:3]
            random.shuffle(options)
            mcqs.append({
                "question": f"Which of the following best describes **{term}**?",
                "options": options,
                "correct_answer": definition,
                "explanation": f"According to the document, **{term}** {definition.lower()}.",
            })

        # Strategy 2: factual cloze from informative sentences.
        facts = _extract_facts(sentences)
        random.shuffle(facts)
        for fact in facts:
            if len(mcqs) >= 5:
                break
            q, options, correct, explanation = _build_fact_mcq(fact, sentences)
            if q:
                mcqs.append({
                    "question": q,
                    "options": options,
                    "correct_answer": correct,
                    "explanation": explanation,
                })

        # Strategy 3: generic but document-titled fallback questions.
        fallbacks = [
            {
                "question": f"What is the primary focus of '{title}' as described in the document?",
                "options": [
                    "To understand core principles, structural models, and operational functions",
                    "To replace hardware drivers manually",
                    "To bypass standard architectural security boundaries",
                    "To eliminate the need for protocol standardization",
                ],
                "correct_answer": "To understand core principles, structural models, and operational functions",
                "explanation": f"The document presents {title} as a framework for understanding foundational architectures and workflows.",
            },
            {
                "question": f"Which active-recall strategy is most effective when studying '{title}'?",
                "options": [
                    "Testing yourself with MCQs and explaining the reasoning behind answers",
                    "Re-reading the document passively multiple times without self-testing",
                    "Highlighting every sentence in bright colors",
                    "Memorizing words without understanding the underlying concepts",
                ],
                "correct_answer": "Testing yourself with MCQs and explaining the reasoning behind answers",
                "explanation": "Active retrieval practice and explanation generation significantly boost long-term retention.",
            },
        ]
        for fb in fallbacks:
            if len(mcqs) >= 5:
                break
            if not any(m["question"] == fb["question"] for m in mcqs):
                mcqs.append(fb)

        return {
            "summary": "",
            "overview_blocks": [],
            "sections": [],
            "key_points": [],
            "key_terms": [],
            "study_tips": [],
            "mcqs": mcqs[:5],
        }

    def _build_prompt(self, action: str, filename: str, document_text: str) -> str:
        # Truncate intelligently: keep whole sentences up to the limit.
        trimmed_text = _truncate_text(document_text, MAX_TEXT_CHARS)

        base_instruction = (
            "You are a precise study assistant. You have been given a PDF document. "
            "ALL of your answers MUST be based STRICTLY on the content of that document. "
            "Do NOT use outside knowledge. If the document does not contain enough information "
            "for a particular item, infer it conservatively from the text or mark it as not covered. "
            "Return ONLY a valid JSON object with no markdown fences and no extra text.\n\n"
            f"Document filename: {filename}\n"
            "Extracted document text follows (may be truncated to fit):\n"
            "---BEGIN DOCUMENT---\n"
            f"{trimmed_text}\n"
            "---END DOCUMENT---\n\n"
        )

        if action == "summary":
            return (
                base_instruction
                + "Task: Produce a structured summary of the document above. Use this exact JSON schema:\n"
                "{\n"
                '  "overview_blocks": [\n'
                '    {\n'
                '      "heading": "Meaningful dynamic heading (e.g. \'<Topic> Overview\', \'Why It Matters\', \'Key Concepts & Principles\', \'Structural Hierarchy & Process Flow\')",'
                '      "content": "Short readable paragraph with **bold** on core terms (1-3 sentences), or empty if block is list-only.",'
                '      "bullet_points": ["Bullet items for concepts, reasons, or multi-faceted points (use **bold** for keywords/terms)"],'
                '      "numbered_points": ["Numbered items if explaining sequential steps, processes, layers, or hierarchy (leave empty otherwise)"]'
                '    }\n'
                '  ],\n'
                '  "summary": "Full formatted Markdown string combining all overview_blocks with ### headings, **bold** terms, bullet points, and numbered steps for backward compatibility.",\n'
                '  "sections": [\n'
                '    {"title": "Section heading extracted or inferred from the content",'
                '     "content": "A detailed paragraph (4-8 sentences) elaborating on this specific topic, including definitions, mechanisms, examples, and significance."}\n'
                '  ],\n'
                '  "key_points": ["Concise actionable bullet — at least 8, up to 12"],\n'
                '  "key_terms": [{"term": "Technical term", "definition": "Clear, precise definition of the term as used in this material"}],\n'
                '  "study_tips": ["Concrete exam/revision tip — provide at least 4"]\n'
                "}\n\n"
                "Requirements:\n"
                "(1) Base every heading, fact, definition, and example on the document text above.\n"
                "(2) overview_blocks must divide the introductory overview into 3-4 structured blocks with dynamic headings. Keep paragraphs short (1-3 sentences). Use bullet points where list-like. Use numbered lists where steps/processes/layers exist. Bold key terms.\n"
                "(3) sections must cover ALL major topics for the Detailed Breakdown — minimum 3 sections, ideally 5-7.\n"
                "(4) key_points must have 8-12 bullets for Core Takeaways.\n"
                "(5) key_terms must have at least 6 glossary entries drawn from the document.\n"
                "(6) study_tips must have at least 4 concrete tips.\n"
                "Do not truncate. Cover all topics in the document."
            )
        if action == "mcqs":
            return (
                base_instruction
                + "Task: Generate 5 multiple-choice questions based ONLY on the document above. "
                "Each question must have 4 options and one clearly correct answer. "
                "Mix easy, medium, and hard difficulty. "
                "Return ONLY this JSON schema with no markdown and no extra text:\n"
                '{"mcqs": [{"question": "...", "options": ["...", "...", "...", "..."], '
                '"correct_answer": "...", "explanation": "..."}]}\n\n'
                "Requirements:\n"
                "- Every question, correct answer, and explanation must be directly supported by the document text.\n"
                "- Distractors must be plausible but clearly wrong based on the document.\n"
                "- Include a mix of definitions, factual recall, and conceptual understanding.\n"
                "- If the document is short, still produce exactly 5 questions using all available content."
            )
        raise ValueError(f"Unsupported action: {action}")

    def _extract_json(self, text: str) -> dict:
        """Extract the JSON payload from response text."""
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()

        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            text = text[first_brace : last_brace + 1]

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Could not parse JSON from response: %s", text[:500])
            raise RuntimeError(f"Agent did not return valid JSON: {text[:200]}") from exc


# ─────────────────────────────── Helpers ───────────────────────────────


def _extract_pdf_text(file_info: dict) -> tuple[str, str]:
    """Decode base64 PDF and extract text with pypdf."""
    filename = file_info.get("filename", "notes.pdf")
    raw_b64 = file_info.get("raw_base64", "")
    extracted_text = ""
    if raw_b64:
        try:
            raw_bytes = base64.b64decode(raw_b64)
            reader = PdfReader(io.BytesIO(raw_bytes))
            pages_text = []
            for p in reader.pages:
                t = p.extract_text()
                if t:
                    pages_text.append(t.strip())
            extracted_text = "\n\n".join(pages_text).strip()
        except Exception as exc:
            logger.warning("PDF extraction error: %s", exc)
    return filename, extracted_text


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, cleaning whitespace."""
    raw = re.split(r'(?<=[.!?])\s+|\n+', text)
    return [re.sub(r'\s+', ' ', s).strip() for s in raw if len(s.strip()) > 8]


def _truncate_text(text: str, max_chars: int) -> str:
    """Trim text at sentence boundaries so we don't exceed the model context."""
    if len(text) <= max_chars:
        return text
    # Find the last sentence boundary before the limit.
    cutoff = text.rfind(". ", 0, max_chars)
    if cutoff == -1:
        cutoff = text.rfind("\n", 0, max_chars)
    if cutoff == -1:
        cutoff = max_chars
    return text[:cutoff] + "\n[Document truncated for length.]"


def _normalize_summary_response(res_dict: dict) -> dict:
    """Ensure summary field is populated from overview_blocks if missing."""
    if "overview_blocks" in res_dict and (not res_dict.get("summary") or not isinstance(res_dict["summary"], str) or res_dict["summary"].strip() == ""):
        res_dict["summary"] = _overview_blocks_to_markdown(res_dict.get("overview_blocks", []))
    return res_dict


def _overview_blocks_to_markdown(blocks: list) -> str:
    """Convert overview blocks to markdown summary string."""
    parts = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("heading"):
            parts.append(f"### {block['heading']}")
        if block.get("content"):
            parts.append(block["content"])
        for b in block.get("bullet_points", []):
            parts.append(f"• {b}")
        for idx, num_item in enumerate(block.get("numbered_points", []), 1):
            parts.append(f"{idx}. {num_item}")
        parts.append("")
    return "\n\n".join(p for p in parts if p).strip()


def _infer_title(filename: str, lines: list[str]) -> str:
    """Infer document title from first line or filename."""
    if lines:
        first = lines[0].strip()
        if 3 < len(first) < 120:
            return first
    return filename.replace(".pdf", "").replace("_", " ").title()


def _chunk_sentences(sentences: list[str], chunk_size: int = 6) -> list[list[str]]:
    """Group sentences into chunks for section/overview synthesis."""
    return [sentences[i:i + chunk_size] for i in range(0, len(sentences), chunk_size)]


def _extract_definitions(sentences: list[str], title: str) -> list[str]:
    """Pull definition-style sentences from the text."""
    bullets = []
    title_lower = title.lower()
    for s in sentences:
        if s.lower().startswith("page ") or s.strip().lower() == title_lower:
            continue
        if re.search(r'\blayer\s*\d+|\bstep\s*\d+', s, re.I):
            continue
        m_def = re.match(r'^(?:The\s+)?([A-Za-z0-9\s\-/]{2,35})\s+(is a|is an|is|has|defines)\s+(.*)', s, re.IGNORECASE)
        if m_def:
            term_name = m_def.group(1).strip()
            verb = m_def.group(2).strip().lower()
            term_desc = m_def.group(3).strip().rstrip(".")
            if 4 < len(term_desc) < 180 and term_name.lower() != title_lower:
                prefix = f"{verb.capitalize()} " if verb in ["has", "defines"] else ""
                bullets.append(f"**{term_name}**: {prefix}{term_desc.capitalize()}.")
        elif any(k in s.lower() for k in [" is a ", " is an ", " refers to ", " defined as "]):
            parts = re.split(r'\b(is a|is an|refers to|defined as)\b', s, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 3 and 3 < len(parts[0].strip()) < 40:
                bullets.append(f"**{parts[0].strip()}**: {parts[1].capitalize()} {parts[2].strip().rstrip('.')}.")
        if len(bullets) >= 6:
            break
    return bullets


def _extract_steps(sentences: list[str]) -> list[str]:
    """Look for numbered steps, layers, phases, or stages."""
    items = []
    for s in sentences:
        clauses = re.split(r'[,;]|\band\b', s) if any(k in s.lower() for k in ["layer", "step", "phase", "stage"]) else [s]
        for cl in clauses:
            m = re.search(r'\b(layer\s*\d+|step\s*\d+|phase\s*\d+|stage\s*\d+)\b\s*(?:is|:|-)?\s*(.*?)$', cl, re.IGNORECASE)
            if m:
                lbl = m.group(1).title()
                desc = m.group(2).strip().rstrip(".")
                items.append(f"**{lbl}**: {desc}" if desc else f"**{lbl}**")
            if len(items) >= 10:
                break
        if len(items) >= 10:
            break
    return items


def _build_sections(lines: list[str], sentences: list[str]) -> list[dict]:
    """Build detailed sections from headings or sentence chunks."""
    heading_indices = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (
            5 < len(stripped) <= 80
            and not stripped.endswith(".")
            and not stripped.endswith(",")
            and (stripped[0].isupper() or stripped[0].isdigit())
            and i > 0
        ):
            heading_indices.append(i)

    sections = []
    for idx, h_idx in enumerate(heading_indices[:7]):
        section_title = lines[h_idx].lstrip("0123456789. ").strip()
        next_h = heading_indices[idx + 1] if idx + 1 < len(heading_indices) else len(lines)
        body_lines = [l for l in lines[h_idx + 1 : next_h] if len(l) > 20]
        body = " ".join(body_lines[:12])
        if len(body) < 30:
            body = " ".join(sentences[h_idx : h_idx + 5]) if h_idx < len(sentences) else ""
        if section_title and len(body) > 20:
            sections.append({"title": section_title, "content": body})

    if not sections:
        chunks = _chunk_sentences(sentences, chunk_size=max(3, len(sentences) // 5))
        generic_titles = [
            "Introduction & Overview",
            "Core Concepts & Definitions",
            "Key Mechanisms & Processes",
            "Applications & Examples",
            "Summary & Review",
        ]
        for i, g_title in enumerate(generic_titles):
            if i < len(chunks) and chunks[i]:
                sections.append({"title": g_title, "content": " ".join(chunks[i])})

    return sections


def _extract_key_points(lines: list[str], sentences: list[str], title: str) -> list[str]:
    """Extract concise key takeaways from the document."""
    key_points = []
    for line in lines[1:]:
        if len(line) > 15 and not line.lower().startswith("page "):
            clean_p = line.lstrip("-*•0123456789. ").strip()
            if clean_p and clean_p not in key_points and len(clean_p) > 15:
                key_points.append(clean_p)
        if len(key_points) >= 12:
            break

    if len(key_points) < 6:
        for s in sentences:
            clean_s = s.strip()
            if clean_s and clean_s not in key_points and len(clean_s) > 20:
                key_points.append(clean_s)
            if len(key_points) >= 10:
                break

    if not key_points:
        key_points = [
            f"Core foundations and taxonomy outlined in {title}.",
            "Standard operational mechanisms and protocol hierarchy explained.",
            "Practical implementation considerations and system architecture covered.",
            "Key definitions and terminology introduced for exam readiness.",
            "Conceptual models and frameworks presented for structured understanding.",
        ]
    return key_points


def _extract_key_terms(full_text: str, sentences: list[str], title: str) -> list[dict]:
    """Extract glossary terms and definitions from the document."""
    key_terms = []
    term_pattern = re.compile(r'^([A-Z][A-Za-z/ ]{2,40})[:\-–—]\s*(.{15,})', re.MULTILINE)
    for match in term_pattern.finditer(full_text):
        term = match.group(1).strip()
        defn = match.group(2).strip().split(".")[0] + "."
        if len(term) < 50 and len(defn) > 15 and len(key_terms) < 12:
            key_terms.append({"term": term, "definition": defn})

    if len(key_terms) < 4:
        cap_pattern = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4})\b')
        seen_terms = {t["term"] for t in key_terms}
        for match in cap_pattern.finditer(full_text):
            phrase = match.group(1)
            if phrase not in seen_terms and len(phrase) > 6:
                for sent in sentences:
                    if phrase in sent and len(sent) > 20:
                        key_terms.append({"term": phrase, "definition": sent.strip()})
                        seen_terms.add(phrase)
                        break
            if len(key_terms) >= 8:
                break

    if not key_terms:
        key_terms = [
            {"term": title, "definition": "The primary subject of this study document, covering foundational principles and applications."},
            {"term": "Protocol", "definition": "A set of rules and conventions that govern communication between systems."},
            {"term": "Architecture", "definition": "The structured design and organisation of a system's components and their relationships."},
        ]
    return key_terms


def _extract_definition_pairs(sentences: list[str]) -> list[tuple[str, str]]:
    """Return (term, definition) pairs for MCQ distractor generation."""
    pairs = []
    seen = set()
    for s in sentences:
        m = re.match(r'^(?:The\s+)?([A-Za-z0-9\s\-/]{2,35})\s+(is a|is an|is|has|defines)\s+(.*)', s, re.IGNORECASE)
        if m:
            term = m.group(1).strip()
            desc = m.group(3).strip().rstrip(".")
            if term.lower() not in seen and 10 < len(desc) < 200:
                pairs.append((term, desc))
                seen.add(term.lower())
        elif " is a " in s.lower() or " is an " in s.lower():
            parts = re.split(r'\b(is a|is an)\b', s, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 3 and 3 < len(parts[0].strip()) < 40:
                term = parts[0].strip()
                desc = f"{parts[1]} {parts[2].strip().rstrip('.')}"
                if term.lower() not in seen and 10 < len(desc) < 200:
                    pairs.append((term, desc))
                    seen.add(term.lower())
    return pairs


def _make_distractors(term: str, definition: str, other_terms: list[str]) -> list[str]:
    """Build plausible wrong definitions for a term."""
    distractors = []
    # Use definitions of other terms as distractors.
    for other in other_terms:
        if other.lower() != term.lower() and len(distractors) < 3:
            distractors.append(f"is {other.lower()} rather than {term.lower()}")
    # Generic distractors.
    distractors += [
        f"has no relationship with {term.lower()}",
        "is not mentioned or described in the document",
        "is a process that occurs independently of the document topic",
    ]
    return distractors


def _extract_facts(sentences: list[str]) -> list[str]:
    """Pull factual statements that can be turned into MCQs."""
    facts = []
    fact_keywords = ["is", "are", "has", "have", "defines", "means", "consists", "contains", "requires", "uses"]
    for s in sentences:
        s_low = s.lower()
        if any(k in s_low for k in fact_keywords) and len(s) > 25:
            facts.append(s)
    return facts


def _build_fact_mcq(fact: str, sentences: list[str]) -> tuple[Optional[str], list[str], str, str]:
    """Turn a factual sentence into a 4-option MCQ."""
    # Try to find a numeric or named entity to replace.
    match = re.search(r'\b(\d+)\b', fact)
    if match:
        target = match.group(1)
        question = re.sub(r'\b' + re.escape(target) + r'\b', "______", fact, count=1)
        correct = target
        # Collect other numbers from the document as distractors.
        other_numbers = list(set(re.findall(r'\b\d+\b', " ".join(sentences))))
        other_numbers = [n for n in other_numbers if n != target]
        random.shuffle(other_numbers)
        options = [correct] + other_numbers[:3]
        while len(options) < 4:
            options.append(str(random.randint(1, 20)))
        random.shuffle(options)
        return question, options, correct, f"The document states: {fact}"

    # Try to blank out the last noun phrase / key term.
    words = fact.split()
    if len(words) >= 5:
        target = words[-1].rstrip(".")
        if target.lower() in {"it", "they", "them", "this", "that"}:
            target = words[-2] if len(words) >= 6 else target
        question = " ".join(words[:-1]) + " ______."
        correct = target
        # Pick distractors from other ending words in sentences.
        other_ends = [s.split()[-1].rstrip(".") for s in sentences if s != fact and len(s.split()) > 3]
        other_ends = [w for w in other_ends if w.lower() != correct.lower() and len(w) > 2]
        random.shuffle(other_ends)
        options = [correct] + other_ends[:3]
        while len(options) < 4:
            options.append("unknown")
        random.shuffle(options)
        return question, options, correct, f"The document states: {fact}"

    return None, [], "", ""
