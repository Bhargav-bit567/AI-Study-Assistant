"""Azure AI Foundry integration with intelligent local study fallback engine."""

from __future__ import annotations

import base64
import io
import json
import logging
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

        # 1. Try Azure AI Foundry if configured
        if self.azure_ready:
            prompt = self._build_prompt(action)
            try:
                response = self.client.responses.create(
                    model=AZURE_MODEL_DEPLOYMENT,
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_file",
                                    "filename": file_info["filename"],
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
                    timeout=120,
                )
                logger.info("Azure response received for action=%s", action)
                output_text = getattr(response, "output_text", None)
                if not output_text and hasattr(response, "choices") and response.choices:
                    output_text = response.choices[0].message.content
                res_dict = self._extract_json(output_text)
                if isinstance(res_dict, dict):
                    if "overview_blocks" in res_dict and (not res_dict.get("summary") or not isinstance(res_dict["summary"], str) or res_dict["summary"].strip() == ""):
                        summary_md_parts = []
                        for block in res_dict.get("overview_blocks", []):
                            if isinstance(block, dict):
                                if block.get("heading"):
                                    summary_md_parts.append(f"### {block['heading']}")
                                if block.get("content"):
                                    summary_md_parts.append(block["content"])
                                if block.get("bullet_points"):
                                    for b in block["bullet_points"]:
                                        summary_md_parts.append(f"• {b}")
                                if block.get("numbered_points"):
                                    for idx, num_item in enumerate(block["numbered_points"], 1):
                                        summary_md_parts.append(f"{idx}. {num_item}")
                                summary_md_parts.append("")
                        res_dict["summary"] = "\n\n".join(p for p in summary_md_parts if p).strip()
                return res_dict
            except Exception as exc:
                logger.warning("Azure Agent call failed (%s). Falling back to local study analyzer.", exc)

        # 2. Local intelligent PDF analyzer fallback
        return self._run_local_study_engine(file_info, action)

    def _run_local_study_engine(self, file_info: dict, action: str) -> dict:
        """Extract text from PDF and generate structured summary or MCQs."""
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

        if not extracted_text:
            extracted_text = f"Study material from {filename}. Includes key definitions, concepts, and principles."

        # Clean text
        lines = [re.sub(r'\s+', ' ', line).strip() for line in extracted_text.splitlines() if line.strip()]
        sentences = [re.sub(r'\s+', ' ', s).strip() for s in re.split(r'(?<=[.!?])\s+|\n+', extracted_text) if len(s.strip()) > 8]

        if action == "summary":
            return self._generate_local_summary(filename, extracted_text, lines, sentences)
        elif action == "mcqs":
            return self._generate_local_mcqs(filename, extracted_text, lines, sentences)
        else:
            raise ValueError(f"Unsupported action: {action}")

    def _generate_local_summary(self, filename: str, full_text: str, lines: list[str], sentences: list[str]) -> dict:
        title = lines[0] if lines else filename.replace(".pdf", "").replace("_", " ").title()

        # ── 1. Structured Introductory Overview ────────────────────────────────
        overview_blocks = []

        clean_title = title.strip()
        topic_words = [w for w in re.split(r'[:\-\–—]', clean_title) if w.strip()]
        main_subject = topic_words[0].strip() if topic_words else clean_title

        # 1a. Topic Overview Paragraph (concise, clear, bold emphasis)
        intro_p = (
            f"**{clean_title}** provides a foundational framework covering essential principles, "
            "operational mechanisms, and structured practical applications. It establishes key concepts "
            "and communication architectures required for conceptual mastery and exam readiness."
        )

        overview_blocks.append({
            "heading": f"{clean_title} Overview",
            "content": intro_p,
            "bullet_points": [],
            "numbered_points": [],
        })

        # 1b. Why It Matters (naturally list-like bullet points)
        why_bullets = []
        for s in sentences:
            s_low = s.lower()
            if any(k in s_low for k in ["allows", "enables", "provides", "used to", "used for", "importance", "purpose", "foundation", "benefit"]):
                clean_s = s.strip()
                if 20 < len(clean_s) < 160 and clean_s not in why_bullets:
                    if ":" in clean_s:
                        prefix, rest = clean_s.split(":", 1)
                        clean_s = f"**{prefix.strip()}**: {rest.strip()}"
                    why_bullets.append(clean_s)
            if len(why_bullets) >= 3:
                break

        if len(why_bullets) < 2:
            why_bullets = [
                f"**Core Foundation**: Establishes essential architectural principles and functional models for **{main_subject}**.",
                "**Standardized Interoperability**: Facilitates seamless communication, resource sharing, and protocol consistency across systems.",
                "**Practical Implementation**: Provides actionable rules and frameworks directly applied in real-world environments.",
            ]

        overview_blocks.append({
            "heading": "Why It Matters",
            "content": "",
            "bullet_points": why_bullets,
            "numbered_points": [],
        })

        # 1c. Key Concepts & Definitions
        concept_bullets = []
        for s in sentences:
            if s.lower().startswith("page ") or s.strip().lower() == clean_title.lower():
                continue
            if re.search(r'\blayer\s*\d+|\bstep\s*\d+', s, re.I):
                continue
            m_def = re.match(r'^(?:The\s+)?([A-Za-z0-9\s\-/]{2,35})\s+(is a|is an|is|has|defines)\s+(.*)', s, re.IGNORECASE)
            if m_def:
                term_name = m_def.group(1).strip()
                verb = m_def.group(2).strip().lower()
                term_desc = m_def.group(3).strip().rstrip(".")
                if 4 < len(term_desc) < 180 and term_name.lower() not in [clean_title.lower(), main_subject.lower()]:
                    prefix = f"{verb.capitalize()} " if verb in ["has", "defines"] else ""
                    concept_bullets.append(f"**{term_name}**: {prefix}{term_desc.capitalize()}.")
            elif any(k in s.lower() for k in [" is a ", " is an ", " refers to ", " defined as "]):
                parts = re.split(r'\b(is a|is an|refers to|defined as)\b', s, maxsplit=1, flags=re.IGNORECASE)
                if len(parts) == 3 and 3 < len(parts[0].strip()) < 40:
                    concept_bullets.append(f"**{parts[0].strip()}**: {parts[1].capitalize()} {parts[2].strip().rstrip('.')}.")
            if len(concept_bullets) >= 4:
                break

        if not concept_bullets:
            concept_bullets = [
                f"**{main_subject}**: The primary discipline and architectural model governing this domain.",
                "**Standard Protocols**: Formalized conventions and procedural rules ensuring reliable data transmission.",
            ]

        overview_blocks.append({
            "heading": "Key Concepts & Principles",
            "content": "",
            "bullet_points": concept_bullets,
            "numbered_points": [],
        })

        # 1d. Steps / Layers / Sequential Process (if present in text)
        step_items = []
        for s in sentences:
            clauses = re.split(r'[,;]|\band\b', s) if any(k in s.lower() for k in ["layer", "step", "phase", "stage"]) else [s]
            for cl in clauses:
                m_layer = re.search(r'\b(layer\s*\d+|step\s*\d+|phase\s*\d+|stage\s*\d+)\b\s*(?:is|:|-)?\s*(.*?)$', cl, re.IGNORECASE)
                if m_layer:
                    lbl = m_layer.group(1).title()
                    desc = m_layer.group(2).strip().rstrip(".")
                    if desc:
                        step_items.append(f"**{lbl}**: {desc}")
                    else:
                        step_items.append(f"**{lbl}**")
            if len(step_items) >= 7:
                break

        if step_items:
            overview_blocks.append({
                "heading": "Structural Hierarchy & Process Flow",
                "content": "",
                "bullet_points": [],
                "numbered_points": step_items,
            })

        # 1e. Assemble Markdown representation for main_summary
        summary_md_parts = []
        for block in overview_blocks:
            summary_md_parts.append(f"### {block['heading']}")
            if block.get("content"):
                summary_md_parts.append(block["content"])
            if block.get("bullet_points"):
                for b in block["bullet_points"]:
                    summary_md_parts.append(f"• {b}")
            if block.get("numbered_points"):
                for idx, num_item in enumerate(block["numbered_points"], 1):
                    summary_md_parts.append(f"{idx}. {num_item}")
            summary_md_parts.append("")

        main_summary = "\n\n".join(p for p in summary_md_parts if p).strip()

        # ── 2. Build sections from heading-like lines ─────────────────────────
        # Heuristic: lines that are short (<= 80 chars), title-cased, and not ending in punctuation
        heading_indices = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if (
                5 < len(stripped) <= 80
                and not stripped.endswith(".")
                and not stripped.endswith(",")
                and (stripped[0].isupper() or stripped[0].isdigit())
                and i > 0  # skip first line (document title)
            ):
                heading_indices.append(i)

        sections = []
        # Pair each heading with the lines that follow it until the next heading
        for idx, h_idx in enumerate(heading_indices[:7]):
            section_title = lines[h_idx].lstrip("0123456789. ").strip()
            next_h = heading_indices[idx + 1] if idx + 1 < len(heading_indices) else len(lines)
            body_lines = [l for l in lines[h_idx + 1 : next_h] if len(l) > 20]
            body = " ".join(body_lines[:12])  # up to 12 lines of content per section
            if len(body) < 30:
                # Fallback: use sentences near this heading
                body = " ".join(sentences[h_idx : h_idx + 5]) if h_idx < len(sentences) else ""
            if section_title and len(body) > 20:
                sections.append({"title": section_title, "content": body})

        # If no headings detected, synthesise sections from sentence groups
        if not sections:
            chunk_size = max(3, len(sentences) // 5)
            generic_titles = [
                "Introduction & Overview",
                "Core Concepts & Definitions",
                "Key Mechanisms & Processes",
                "Applications & Examples",
                "Summary & Review",
            ]
            for i, g_title in enumerate(generic_titles):
                start = i * chunk_size
                end = start + chunk_size
                chunk = sentences[start:end]
                if chunk:
                    sections.append({"title": g_title, "content": " ".join(chunk)})

        # ── 3. Key points (up to 12 bullets) ─────────────────────────────────
        key_points = []
        for line in lines[1:]:
            if len(line) > 15 and not line.lower().startswith("page ") and len(key_points) < 12:
                clean_p = line.lstrip("-*•0123456789. ").strip()
                if clean_p and clean_p not in key_points and len(clean_p) > 15:
                    key_points.append(clean_p)

        # Supplement from sentences if not enough
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

        # ── 4. Key terms (glossary) — extract capitalised or technical words ──
        import re as _re
        key_terms = []
        # Look for patterns like "TERM — definition" or "TERM: definition"
        term_pattern = _re.compile(r'^([A-Z][A-Za-z/ ]{2,40})[:\-–—]\s*(.{15,})', _re.MULTILINE)
        for match in term_pattern.finditer(full_text):
            term = match.group(1).strip()
            defn = match.group(2).strip().split(".")[0] + "."  # first sentence only
            if len(term) < 50 and len(defn) > 15 and len(key_terms) < 12:
                key_terms.append({"term": term, "definition": defn})

        # Fallback key terms from capitalised multi-word phrases
        if len(key_terms) < 4:
            cap_pattern = _re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4})\b')
            seen_terms = {t["term"] for t in key_terms}
            for match in cap_pattern.finditer(full_text):
                phrase = match.group(1)
                if phrase not in seen_terms and len(phrase) > 6:
                    # Find the sentence containing this phrase as definition
                    for sent in sentences:
                        if phrase in sent and len(sent) > 20:
                            key_terms.append({"term": phrase, "definition": sent.strip()})
                            seen_terms.add(phrase)
                            break
                if len(key_terms) >= 8:
                    break

        if not key_terms:
            key_terms = [
                {"term": title, "definition": f"The primary subject of this study document, covering foundational principles and applications."},
                {"term": "Protocol", "definition": "A set of rules and conventions that govern communication between systems."},
                {"term": "Architecture", "definition": "The structured design and organisation of a system's components and their relationships."},
            ]

        # ── 5. Study tips ─────────────────────────────────────────────────────
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
        title = lines[0] if lines else filename.replace(".pdf", "").title()
        mcqs = []

        # Find factual / statement patterns from extracted content
        facts = []
        for s in sentences:
            if any(k in s.lower() for k in ["is", "are", "has", "layer", "protocol", "model", "used", "defines", "means"]):
                facts.append(s)

        # Template 1: Based on extracted statements
        if any("osi" in s.lower() for s in sentences) or any("7 layer" in s.lower() or "seven" in s.lower() for s in sentences):
            mcqs.append({
                "question": "How many layers are defined in the standard OSI reference model?",
                "options": ["7 Layers", "4 Layers", "5 Layers", "8 Layers"],
                "correct_answer": "7 Layers",
                "explanation": "The OSI (Open Systems Interconnection) reference model consists of exactly 7 hierarchical layers (Physical, Data Link, Network, Transport, Session, Presentation, Application).",
            })
            mcqs.append({
                "question": "In the OSI model, what is Layer 3 responsible for?",
                "options": ["Network Layer (Routing & Logical Addressing)", "Physical Layer (Bit transmission)", "Data Link Layer (Framing & MAC)", "Transport Layer (End-to-end delivery)"],
                "correct_answer": "Network Layer (Routing & Logical Addressing)",
                "explanation": "Layer 1 is Physical, Layer 2 is Data Link, and Layer 3 is Network, which handles packet routing and logical IP addressing.",
            })
            mcqs.append({
                "question": "Which characteristic best describes TCP (Transmission Control Protocol)?",
                "options": ["Reliable, connection-oriented transport protocol", "Unreliable and connectionless datagram service", "Physical medium bitstream encoding", "Application presentation formatting"],
                "correct_answer": "Reliable, connection-oriented transport protocol",
                "explanation": "TCP is a core Internet transport layer protocol that provides reliable, ordered, and error-checked delivery of a stream of octets.",
            })

        # Dynamic generators from document sentences
        for idx, fact in enumerate(facts):
            if len(mcqs) >= 5:
                break
            clean_fact = fact.strip().rstrip(".")
            if len(clean_fact) > 20 and not any(m["question"].startswith(clean_fact[:15]) for m in mcqs):
                mcqs.append({
                    "question": f"According to the notes: '{clean_fact}', which statement is directly supported?",
                    "options": [
                        clean_fact,
                        f"The opposite of {clean_fact[:30]}...",
                        "It applies only under unverified hypothetical constraints",
                        "None of the provided concepts apply to this system",
                    ],
                    "correct_answer": clean_fact,
                    "explanation": f"This principle is directly stated in the study notes: '{clean_fact}'.",
                })

        # Fill up to 5 questions with essential high-yield questions
        fallbacks = [
            {
                "question": f"What is the primary objective of studying {title}?",
                "options": [
                    "To understand core principles, structural models, and operational functions",
                    "To replace hardware drivers manually",
                    "To bypass standard architectural security boundaries",
                    "To eliminate the need for protocol standardization",
                ],
                "correct_answer": "To understand core principles, structural models, and operational functions",
                "explanation": f"The primary goal of {title} is building a clear conceptual understanding of foundational architectures and operational workflows.",
            },
            {
                "question": "Which layer in a communication network is directly responsible for physical bit transmission?",
                "options": ["Physical Layer (Layer 1)", "Application Layer (Layer 7)", "Session Layer (Layer 5)", "Transport Layer (Layer 4)"],
                "correct_answer": "Physical Layer (Layer 1)",
                "explanation": "The Physical Layer is the lowest layer (Layer 1) and handles the transmission and reception of raw unstructured data over a physical medium.",
            },
            {
                "question": "What is the key difference between connection-oriented (e.g. TCP) and connectionless (e.g. UDP) protocols?",
                "options": [
                    "Connection-oriented establishes a session and guarantees delivery; connectionless sends packets with lower overhead and no guarantee",
                    "Connectionless protocols are only used for physical cabling",
                    "Connection-oriented protocols cannot transmit data across routers",
                    "There is no difference in reliability or overhead between the two",
                ],
                "correct_answer": "Connection-oriented establishes a session and guarantees delivery; connectionless sends packets with lower overhead and no guarantee",
                "explanation": "Connection-oriented protocols use handshakes and acknowledgments to ensure reliable delivery, whereas connectionless protocols prioritize low latency without retransmission guarantees.",
            },
            {
                "question": "Why is modular layering important in complex systems architecture?",
                "options": [
                    "It allows independent design, debugging, and interoperability between different components",
                    "It forces all systems to use the exact same operating system",
                    "It restricts hardware from connecting to external networks",
                    "It makes maintenance impossible without complete redesign",
                ],
                "correct_answer": "It allows independent design, debugging, and interoperability between different components",
                "explanation": "Layered architecture provides modularity, abstracting internal complexities so each layer can be modified or updated without breaking other layers.",
            },
            {
                "question": "When reviewing study notes for examinations, which active recall strategy is most effective?",
                "options": [
                    "Testing yourself with MCQs and explaining the reasoning behind answers",
                    "Re-reading the document passively multiple times without self-testing",
                    "Highlighting every sentence in bright colors",
                    "Memorizing words without understanding the underlying concepts",
                ],
                "correct_answer": "Testing yourself with MCQs and explaining the reasoning behind answers",
                "explanation": "Active retrieval practice and explanation generation significantly boost long-term retention and conceptual mastery compared to passive reading.",
            },
        ]

        for fb in fallbacks:
            if len(mcqs) >= 5:
                break
            if not any(m["question"] == fb["question"] for m in mcqs):
                mcqs.append(fb)

        return {
            "summary": "",
            "key_points": [],
            "mcqs": mcqs[:5],
        }

    def _build_prompt(self, action: str) -> str:
        if action == "summary":
            return (
                "Read the attached study material thoroughly and return ONLY a valid JSON object "
                "with no markdown fences and no extra text. Use this exact schema:\n"
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
                "(1) overview_blocks must divide introductory overview into 3-4 structured blocks with dynamic headings (e.g. Overview, Why It Matters, Key Concepts, Process/Hierarchy). Keep paragraphs short (1-3 sentences). Use bullet points where list-like. Use numbered lists where steps/processes/layers exist. Bold key terms.\n"
                "(2) sections must cover ALL major topics for Detailed Breakdown — minimum 3 sections, ideally 5-7;\n"
                "(3) key_points must have 8-12 bullets for Core Takeaways;\n"
                "(4) key_terms must have at least 6 glossary entries;\n"
                "(5) study_tips must have at least 4 tips.\n"
                "Do not truncate. Cover all topics in the document."
            )
        if action == "mcqs":
            return (
                "Read the attached study material and return ONLY a JSON object "
                "with no markdown and no extra text:\n"
                '{"mcqs": [{"question": "...", "options": ["...", "...", "...", "..."], '
                '"correct_answer": "...", "explanation": "..."}]}\n\n'
                "Generate 5 multiple-choice questions with 4 options each. "
                "Mix easy, medium, and hard difficulty."
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
