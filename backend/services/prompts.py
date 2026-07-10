"""
Zero-shot prompt templates for LectMent — one per mode.
All prompts instruct Granite to work ONLY from the supplied transcript,
except Research mode which explicitly invites broader context connections.
"""

# ── Difficulty guidance injected into prompts ─────────────────────────────────
_DIFFICULTY_GUIDE = {
    "easy"  : "Use very simple language. Avoid jargon. Explain every term. Suitable for a beginner.",
    "medium": "Use standard academic language. Briefly explain technical terms.",
    "hard"  : "Use precise technical language. Assume an advanced student. Be concise and rigorous.",
}


def _preamble(language: str, difficulty: str = "medium") -> str:
    # Accept "en", "en-US", "english", "English" — anything starting with "en"
    lang_note = (
        f" Respond ENTIRELY in {language}."
        if not language.lower().startswith("en") else ""
    )
    diff_note = _DIFFICULTY_GUIDE.get(difficulty.lower(), _DIFFICULTY_GUIDE["medium"])
    return (
        "You are LectMent, an AI assistant that helps students understand lectures. "
        "Write clearly for non-native English speakers and neurodivergent students. "
        f"Use plain language and short sentences.{lang_note} "
        f"Difficulty level: {difficulty.upper()}. {diff_note}"
    )


STRICT_NOTE = "Base ALL content ONLY on the transcript. Do not add outside knowledge."
RESEARCH_NOTE = (
    "You may connect lecture concepts to well-known external research, papers, "
    "or real-world examples to deepen understanding. Clearly mark any external "
    "additions with 🔗 so students know what came from the lecture vs. broader research."
)


# ─────────────────────────────────────────────────────────────────────────────
# MODE 1 — STUDY
# Deep structured notes optimised for studying
# ─────────────────────────────────────────────────────────────────────────────
def study_prompt(
    transcript: str,
    language  : str = "English",
    difficulty: str = "medium",
    num_cards : int = 8,   # unused in study but accepted for uniform signature
) -> str:
    return f"""{_preamble(language, difficulty)}
{STRICT_NOTE}

## Mode: STUDY — Deep Lecture Notes

Produce a detailed study guide in Markdown from the transcript below.

Output this exact structure:

### SECTION 1 — SUMMARY
A structured summary using ## headings and bullet points. Bold key terms. Under 400 words.

### SECTION 2 — KEY TAKEAWAYS
Exactly 5 numbered takeaways. One sentence each. Bold the core concept.

### SECTION 3 — QUIZ
5 multiple-choice questions (Q1–Q5). Each has options A–D, then "Answer: X" and one-sentence "Explanation:".

### SECTION 5 — DIFFICULTY & PREREQUISITES
**Estimated difficulty:** {difficulty.capitalize()}
**Prerequisites:** List 3–5 concepts a student should already know before this lecture. Bullet list.

## Transcript
{transcript}

---
"""


# ─────────────────────────────────────────────────────────────────────────────
# MODE 2 — RESEARCH
# Connects lecture to broader academic context
# ─────────────────────────────────────────────────────────────────────────────
def research_prompt(
    transcript: str,
    language  : str = "English",
    difficulty: str = "medium",
    num_cards : int = 8,
) -> str:
    return f"""{_preamble(language, difficulty)}
{RESEARCH_NOTE}

## Mode: RESEARCH — Lecture + Broader Context

Produce a research-enriched analysis from the transcript below.

Output this exact structure:

### SECTION 1 — SUMMARY
Structured Markdown summary of what was said in the lecture. ## headings + bullets. Bold key terms.

### SECTION 2 — KEY TAKEAWAYS
5 numbered takeaways from the lecture only. Bold core concept per line.

### SECTION 3 — QUIZ
5 multiple-choice questions. Q1–Q5, options A–D, "Answer: X", one-sentence "Explanation:".

### SECTION 4 — RESEARCH CONNECTIONS
List 4–6 bullet points connecting lecture topics to broader research, real-world examples, or related fields.
Mark each with 🔗. Include a suggested search query in quotes for each point.

## Transcript
{transcript}

---
"""


# ─────────────────────────────────────────────────────────────────────────────
# MODE 3 — SHEET (Cheat Sheet)
# Dense 1–2 page reference card
# ─────────────────────────────────────────────────────────────────────────────
def sheet_prompt(
    transcript: str,
    language  : str = "English",
    difficulty: str = "medium",
    num_cards : int = 8,
) -> str:
    return f"""{_preamble(language, difficulty)}
{STRICT_NOTE}

## Mode: SHEET — Cheat Sheet (1–2 pages)

Create a dense, printable cheat sheet from the transcript below.
This must be compact enough to fit on 1–2 printed pages.

Output this exact structure:

### SECTION 1 — SUMMARY
One short paragraph (max 80 words) capturing the lecture in a nutshell.

### SECTION 2 — KEY TAKEAWAYS
Exactly 5 numbered one-sentence takeaways. Bold core concept.

### SECTION 3 — QUIZ
5 multiple-choice questions. Q1–Q5, options A–D, "Answer: X", one-sentence "Explanation:".

### SECTION 4 — CHEATSHEET
A dense reference card with these subsections:
#### Key Terms
| Term | Definition |
(table format, max 10 rows)

#### Core Formulas / Rules
Bullet list of the most important rules, formulas, or steps mentioned.

#### Quick-Reference Facts
3–5 bullet points of the most exam-likely facts.

## Transcript
{transcript}

---
"""


# ─────────────────────────────────────────────────────────────────────────────
# MODE 4 — QUIZ / FLASHCARDS
# Extended quiz + flashcard pairs
# ─────────────────────────────────────────────────────────────────────────────
def quiz_prompt(
    transcript: str,
    language  : str = "English",
    difficulty: str = "medium",
    num_cards : int = 8,
) -> str:
    card_list = "\n".join(
        f"CARD {i}\nFRONT: (question or term)\nBACK: (answer or definition)"
        for i in range(1, num_cards + 1)
    )
    return f"""{_preamble(language, difficulty)}
{STRICT_NOTE}

## Mode: QUIZ / FLASHCARDS — Memory Practice

Produce a quiz and flashcard set from the transcript below.

Output this exact structure:

### SECTION 1 — SUMMARY
Brief summary in bullet points only. Max 150 words.

### SECTION 2 — KEY TAKEAWAYS
5 numbered one-sentence takeaways. Bold core concept.

### SECTION 3 — QUIZ
5 multiple-choice questions. Q1–Q5, options A–D, "Answer: X", one-sentence "Explanation:".

### SECTION 4 — FLASHCARDS
Generate exactly {num_cards} flashcard pairs in this format:

{card_list}

## Transcript
{transcript}

---
"""


# ─────────────────────────────────────────────────────────────────────────────
# MODE 5 — SUMMARIZE
# Clean concise summary only
# ─────────────────────────────────────────────────────────────────────────────
def summarize_prompt(
    transcript: str,
    language  : str = "English",
    difficulty: str = "medium",
    num_cards : int = 8,
) -> str:
    return f"""{_preamble(language, difficulty)}
{STRICT_NOTE}

## Mode: SUMMARIZE — Clean Lecture Summary

Produce a clean, readable summary of the lecture from the transcript below.

Output this exact structure:

### SECTION 1 — SUMMARY
A well-structured Markdown summary using ## headings and bullet points.
Bold key terms. Under 500 words. Suitable for a student who missed the lecture.

### SECTION 2 — KEY TAKEAWAYS
Exactly 5 numbered one-sentence takeaways. Bold the core concept.

### SECTION 3 — QUIZ
5 multiple-choice questions. Q1–Q5, options A–D, "Answer: X", one-sentence "Explanation:".

### SECTION 5 — DIFFICULTY & PREREQUISITES
**Estimated difficulty:** {difficulty.capitalize()}
**Prerequisites:** List 3–5 concepts a student should already know before this lecture. Bullet list.

## Transcript
{transcript}

---
"""


# ─────────────────────────────────────────────────────────────────────────────
# Follow-up Q&A prompt
# ─────────────────────────────────────────────────────────────────────────────
def ask_prompt(
    transcript: str,
    question  : str,
    language  : str = "English",
    mode      : str = "study",
) -> str:
    lang_note = (
        f" Respond ENTIRELY in {language}."
        if not language.lower().startswith("en") else ""
    )
    return f"""You are LectMent, an AI assistant that helps students understand lectures.
Answer the student's question using ONLY information from the provided lecture transcript.
Write clearly for non-native English speakers and neurodivergent students.
Use plain language and short sentences.{lang_note}
If the answer is not in the transcript, say: "I don't see that covered in this lecture."

## Lecture Transcript
{transcript}

## Student Question
{question}

## Answer
"""


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────
MODE_PROMPTS = {
    "study"    : study_prompt,
    "research" : research_prompt,
    "sheet"    : sheet_prompt,
    "quiz"     : quiz_prompt,
    "summarize": summarize_prompt,
}


def get_prompt(
    mode      : str,
    transcript: str,
    language  : str = "English",
    difficulty: str = "medium",
    num_cards : int = 8,
) -> str:
    fn = MODE_PROMPTS.get(mode, study_prompt)
    return fn(transcript, language, difficulty, num_cards)
