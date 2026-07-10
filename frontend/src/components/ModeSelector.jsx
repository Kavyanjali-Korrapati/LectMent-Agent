import React from "react";

const MODES = [
  {
    id   : "study",
    icon : "📚",
    label: "Study",
    desc : "Deep structured notes, takeaways & quiz",
    color: "#1a6fe8",
  },
  {
    id   : "research",
    icon : "🔍",
    label: "Research",
    desc : "Lecture + web context & search suggestions",
    color: "#7c3aed",
  },
  {
    id   : "sheet",
    icon : "📄",
    label: "Cheat Sheet",
    desc : "Printable 1–2 page reference card",
    color: "#0891b2",
  },
  {
    id   : "quiz",
    icon : "🧠",
    label: "Quiz & Flashcards",
    desc : "Multiple-choice quiz + 8 flip cards",
    color: "#d97706",
  },
  {
    id   : "summarize",
    icon : "✨",
    label: "Summarize",
    desc : "Clean concise lecture summary",
    color: "#16a34a",
  },
];

export default function ModeSelector({ active, onChange }) {
  return (
    <nav className="mode-sidebar" aria-label="Learning mode">
      <p className="mode-sidebar__title">Mode</p>
      {MODES.map((m) => (
        <button
          key={m.id}
          className={`mode-btn ${active === m.id ? "mode-btn--active" : ""}`}
          style={ active === m.id ? { borderLeftColor: m.color, color: m.color } : {} }
          onClick={() => onChange(m.id)}
          aria-pressed={active === m.id}
          title={m.desc}
        >
          <span className="mode-btn__icon">{m.icon}</span>
          <span className="mode-btn__text">
            <span className="mode-btn__label">{m.label}</span>
            <span className="mode-btn__desc">{m.desc}</span>
          </span>
        </button>
      ))}
    </nav>
  );
}
