import React, { useState, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { askQuestion } from "../api";

/* ── Tab definitions per mode ─────────────────────────────────────────────── */
const MODE_TABS = {
  study    : ["summary", "takeaways", "quiz", "prerequisites"],
  research : ["summary", "takeaways", "quiz", "research"],
  sheet    : ["summary", "takeaways", "quiz", "cheatsheet"],
  quiz     : ["summary", "takeaways", "quiz", "flashcards"],
  summarize: ["summary", "takeaways", "quiz", "prerequisites"],
};

const TAB_META = {
  summary      : { label: "📄 Summary"             },
  takeaways    : { label: "💡 Key Takeaways"        },
  quiz         : { label: "🧠 Practice Quiz"        },
  flashcards   : { label: "🃏 Flashcards"           },
  cheatsheet   : { label: "📋 Cheat Sheet"          },
  research     : { label: "🔍 Research Connections" },
  prerequisites: { label: "🎓 Difficulty & Prerequisites" },
};

/* ── Helpers ──────────────────────────────────────────────────────────────── */
function downloadBlob(content, filename, mime = "text/plain") {
  const url = URL.createObjectURL(new Blob([content], { type: mime }));
  Object.assign(document.createElement("a"), { href: url, download: filename }).click();
  URL.revokeObjectURL(url);
}

function printWindow(html) {
  const win = window.open("", "_blank");
  win.document.write(html);
  win.document.close();
  win.print();
}

/* ── Flashcard parser ─────────────────────────────────────────────────────── */
function parseFlashcards(raw) {
  const cards = [];
  const blocks = raw.split(/CARD\s+\d+/i).filter(Boolean);
  for (const block of blocks) {
    const f = block.match(/FRONT:\s*(.+?)(?=BACK:|$)/si);
    const b = block.match(/BACK:\s*(.+?)(?=FRONT:|CARD|$)/si);
    if (f && b) cards.push({ front: f[1].trim(), back: b[1].trim() });
  }
  return cards;
}

/* ── Flashcard flip card ──────────────────────────────────────────────────── */
function Flashcard({ front, back, index }) {
  const [flipped, setFlipped] = useState(false);
  return (
    <div
      className={`flashcard ${flipped ? "flashcard--flipped" : ""}`}
      onClick={() => setFlipped((f) => !f)}
      onKeyDown={(e) => e.key === "Enter" && setFlipped((f) => !f)}
      role="button" tabIndex={0}
      aria-label={`Card ${index + 1}. ${flipped ? "Showing answer" : "Click to reveal answer"}`}
    >
      <div className="flashcard__inner">
        <div className="flashcard__face flashcard__face--front">
          <span className="fc-badge">Q</span>
          <p>{front}</p>
          <span className="fc-hint">Click to flip</span>
        </div>
        <div className="flashcard__face flashcard__face--back">
          <span className="fc-badge fc-badge--back">A</span>
          <p>{back}</p>
          <span className="fc-hint">Click to flip back</span>
        </div>
      </div>
    </div>
  );
}

function FlashcardsPanel({ raw }) {
  const cards = parseFlashcards(raw);
  if (!cards.length) return <p className="empty-state">No flashcards generated.</p>;

  const exportCSV = () => {
    const csv = "Term,Definition\n" +
      cards.map((c) => `"${c.front.replace(/"/g,'""')}","${c.back.replace(/"/g,'""')}"`).join("\n");
    downloadBlob(csv, "LectMent_Flashcards.csv", "text/csv");
  };

  return (
    <div>
      <div className="sheet-actions">
        <button className="btn-ghost" onClick={exportCSV}>⬇ Export Anki/Quizlet CSV</button>
      </div>
      <div className="result-content">
        <div className="flashcards-grid">
          {cards.map((c, i) => <Flashcard key={i} index={i} front={c.front} back={c.back} />)}
        </div>
      </div>
    </div>
  );
}

/* ── Interactive Quiz panel ───────────────────────────────────────────────── */
function parseQuizQuestions(raw) {
  const questions = [];
  const blocks = raw.split(/Q\d+[.)]/i).filter(Boolean);
  for (const block of blocks) {
    const lines     = block.trim().split("\n").map((l) => l.trim()).filter(Boolean);
    const qText     = lines[0] || "";
    const options   = {};
    let answer      = "";
    let explanation = "";
    for (const line of lines.slice(1)) {
      const optMatch = line.match(/^([A-D])[.)]\s*(.+)/i);
      const ansMatch = line.match(/^Answer:\s*([A-D])/i);
      const expMatch = line.match(/^Explanation:\s*(.+)/i);
      if (optMatch) options[optMatch[1].toUpperCase()] = optMatch[2];
      else if (ansMatch) answer = ansMatch[1].toUpperCase();
      else if (expMatch) explanation = expMatch[1];
    }
    if (qText && Object.keys(options).length) {
      questions.push({ qText, options, answer, explanation });
    }
  }
  return questions;
}

function QuizPanel({ raw }) {
  const questions = parseQuizQuestions(raw);
  const [selected, setSelected] = useState({});
  const [revealed, setRevealed] = useState({});

  if (!questions.length) {
    return (
      <div className="result-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{raw}</ReactMarkdown>
      </div>
    );
  }

  const score = Object.entries(revealed).filter(
    ([i]) => selected[i] === questions[Number(i)].answer
  ).length;

  const allRevealed = questions.every((_, i) => revealed[i]);

  return (
    <div className="result-content">
      {allRevealed && (
        <div className="quiz-score">
          Score: {score} / {questions.length}
          {score === questions.length ? " 🎉 Perfect!" : score >= questions.length / 2 ? " 👍 Good job!" : " 📖 Keep studying!"}
        </div>
      )}
      {questions.map((q, i) => (
        <div key={i} className="quiz-question">
          <p className="quiz-q-text"><strong>Q{i + 1}.</strong> {q.qText}</p>
          <div className="quiz-options">
            {Object.entries(q.options).map(([letter, text]) => {
              const isSelected = selected[i] === letter;
              const isCorrect  = letter === q.answer;
              let cls = "quiz-option";
              if (revealed[i]) {
                if (isCorrect)           cls += " quiz-option--correct";
                else if (isSelected)     cls += " quiz-option--wrong";
              } else if (isSelected)     cls += " quiz-option--selected";
              return (
                <button key={letter} className={cls}
                  disabled={!!revealed[i]}
                  onClick={() => setSelected((s) => ({ ...s, [i]: letter }))}
                >
                  <span className="quiz-letter">{letter}</span> {text}
                </button>
              );
            })}
          </div>
          {selected[i] && !revealed[i] && (
            <button className="btn-ghost quiz-reveal-btn"
              onClick={() => setRevealed((r) => ({ ...r, [i]: true }))}
            >
              Reveal answer
            </button>
          )}
          {revealed[i] && q.explanation && (
            <p className="quiz-explanation">💡 {q.explanation}</p>
          )}
        </div>
      ))}
    </div>
  );
}

/* ── Cheat sheet panel ────────────────────────────────────────────────────── */
function CheatsheetPanel({ raw }) {
  const printCSS = `body{font-family:system-ui,sans-serif;font-size:12px;padding:16px;max-width:800px;margin:0 auto}
    h4{margin:12px 0 4px;border-bottom:1px solid #ccc}
    table{width:100%;border-collapse:collapse;font-size:11px}
    th,td{border:1px solid #ccc;padding:4px 6px;text-align:left}
    th{background:#eee}ul,ol{margin:4px 0;padding-left:18px}li{margin-bottom:2px}`;

  return (
    <div>
      <div className="sheet-actions">
        <button className="btn-ghost" onClick={() => downloadBlob(raw, "LectMent_CheatSheet.md")}>
          ⬇ Download .md
        </button>
        <button className="btn-ghost" onClick={() => printWindow(
          `<!DOCTYPE html><html><head><title>LectMent Cheat Sheet</title>
          <style>${printCSS}</style></head><body>
          <h2>LectMent Cheat Sheet</h2>
          <pre style="white-space:pre-wrap;font-size:11px">${raw}</pre></body></html>`
        )}>
          🖨 Print Sheet
        </button>
      </div>
      <div className="result-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{raw}</ReactMarkdown>
      </div>
    </div>
  );
}

/* ── Generic PDF/print for any tab ───────────────────────────────────────── */
function printMarkdown(title, content) {
  const printCSS = `body{font-family:system-ui,sans-serif;font-size:13px;padding:24px;max-width:800px;margin:0 auto;line-height:1.6}
    h1,h2{border-bottom:1px solid #ccc;padding-bottom:4px}
    table{width:100%;border-collapse:collapse}
    th,td{border:1px solid #ccc;padding:5px 8px;text-align:left}
    th{background:#eee}ul,ol{padding-left:20px}`;
  printWindow(
    `<!DOCTYPE html><html><head><title>${title}</title>
    <style>${printCSS}</style></head><body>
    <h1>${title}</h1><div>${content}</div></body></html>`
  );
}

/* ── Q&A chat panel ───────────────────────────────────────────────────────── */
function QAPanel({ transcript, mode, language }) {
  const [question,  setQuestion]  = useState("");
  const [messages,  setMessages]  = useState([]);  // [{role:"user"|"ai", text}]
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState(null);
  const bottomRef = useRef(null);

  const submit = async () => {
    const q = question.trim();
    if (!q || loading) return;
    setQuestion("");
    setError(null);
    setMessages((m) => [...m, { role: "user", text: q }]);
    setLoading(true);
    try {
      const resp = await askQuestion(transcript, q, mode, language);
      setMessages((m) => [...m, { role: "ai", text: resp.answer }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  };

  const onKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey || e.key === "Enter") && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="qa-panel">
      <p className="qa-intro">
        Ask a follow-up question about this lecture. Answers are grounded in the transcript only.
      </p>

      {messages.length > 0 && (
        <div className="qa-messages">
          {messages.map((msg, i) => (
            <div key={i} className={`qa-msg qa-msg--${msg.role}`}>
              <span className="qa-msg-badge">{msg.role === "user" ? "You" : "AI"}</span>
              <div className="qa-msg-body">
                {msg.role === "ai"
                  ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
                  : <p>{msg.text}</p>
                }
              </div>
            </div>
          ))}
          {loading && (
            <div className="qa-msg qa-msg--ai">
              <span className="qa-msg-badge">AI</span>
              <div className="qa-msg-body qa-typing">
                <span /><span /><span />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}

      {error && <p className="qa-error">⚠ {error}</p>}

      <div className="qa-input-row">
        <textarea
          className="qa-textarea"
          rows={2}
          placeholder="Ask anything about this lecture… (Enter to send)"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={loading}
          aria-label="Follow-up question"
        />
        <button
          className="qa-send-btn"
          onClick={submit}
          disabled={!question.trim() || loading}
          aria-label="Send question"
        >
          {loading ? "…" : "↑"}
        </button>
      </div>
    </div>
  );
}

/* ── Main ResultPanel ─────────────────────────────────────────────────────── */
export default function ResultPanel({ data, mode }) {
  const tabs = MODE_TABS[mode] ?? MODE_TABS.study;
  // Filter out tabs that have no content (except prerequisites/qa which always render)
  const visibleTabs = [...tabs, "ask"];
  const [active, setActive] = useState(tabs[0]);
  const [copied, setCopied] = useState(false);

  const copyAll = useCallback(() => {
    const text = tabs
      .filter((k) => k !== "ask")
      .map((k) => `## ${TAB_META[k]?.label ?? k}\n\n${data[k] ?? ""}`)
      .join("\n\n---\n\n");
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }, [tabs, data]);

  // Reading time badge
  const readingBadge = data.est_reading_time_min
    ? `${data.word_count?.toLocaleString() ?? "?"} words · ~${data.est_reading_time_min} min read`
    : null;

  const diffBadgeColor = { easy: "#22c55e", medium: "#f59e0b", hard: "#ef4444" }[data.difficulty] ?? "#888";

  return (
    <section className="result-panel" aria-label="Analysis results">
      {/* metadata bar */}
      <div className="result-meta-bar">
        {data.difficulty && (
          <span className="result-meta-badge" style={{ borderColor: diffBadgeColor, color: diffBadgeColor }}>
            {data.difficulty.charAt(0).toUpperCase() + data.difficulty.slice(1)}
          </span>
        )}
        {readingBadge && <span className="result-meta-text">{readingBadge}</span>}
        {data.language && data.language !== "English" && (
          <span className="result-meta-badge result-meta-badge--lang">🌐 {data.language}</span>
        )}
      </div>

      {/* transcript preview */}
      {data.transcript_preview && (
        <details className="transcript-preview">
          <summary>Transcript preview (first 500 chars)</summary>
          <p className="preview-text">{data.transcript_preview}</p>
        </details>
      )}

      {/* result tabs */}
      <div className="result-tabs" role="tablist" aria-label="Result sections">
        {tabs.map((k) => (
          <button key={k} role="tab"
            aria-selected={active === k}
            className={`result-tab ${active === k ? "result-tab--active" : ""}`}
            onClick={() => setActive(k)}
          >
            {TAB_META[k]?.label ?? k}
          </button>
        ))}
        {/* Q&A tab — always last */}
        <button role="tab"
          aria-selected={active === "ask"}
          className={`result-tab ${active === "ask" ? "result-tab--active" : ""}`}
          onClick={() => setActive("ask")}
        >
          💬 Ask AI
        </button>
      </div>

      {/* content */}
      {tabs.map((k) => (
        <div key={k} role="tabpanel" hidden={active !== k} aria-label={TAB_META[k]?.label ?? k}>
          {active === k && (
            k === "flashcards"   ? <FlashcardsPanel raw={data.flashcards   ?? ""} /> :
            k === "cheatsheet"   ? <CheatsheetPanel raw={data.cheatsheet   ?? ""} /> :
            k === "quiz"         ? <QuizPanel       raw={data.quiz         ?? ""} /> :
            data[k]              ? (
              <div className="result-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{data[k]}</ReactMarkdown>
              </div>
            ) : (
              <div className="result-content">
                <p className="empty-state">No content generated for this section.</p>
              </div>
            )
          )}
        </div>
      ))}

      {/* Q&A tab panel */}
      <div role="tabpanel" hidden={active !== "ask"} aria-label="Ask AI">
        {active === "ask" && (
          <QAPanel
            transcript={data.transcript_preview ?? ""}
            mode={mode}
            language={data.language ?? "English"}
          />
        )}
      </div>

      {/* actions */}
      <div className="result-actions">
        <button className="btn-ghost" onClick={() => {
          const content = data[active] ?? "";
          printMarkdown(`LectMent — ${TAB_META[active]?.label ?? active}`, content);
        }}>🖨 Print / PDF</button>
        <button className={`btn-ghost ${copied ? "btn-ghost--copied" : ""}`} onClick={copyAll}>
          {copied ? "✅ Copied!" : "Copy all to clipboard"}
        </button>
      </div>
    </section>
  );
}
