import React, { useState } from "react";
import { analyzeText } from "../api";

const WARN_CHARS = 12_000;

export default function TranscriptInput({ mode, language, onResult, onError, setLoading }) {
  const [text, setText] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!text.trim()) return onError("Please paste some transcript text first.");
    setLoading(true);
    try {
      const data = await analyzeText(text.trim(), mode, language);
      onResult(data);
    } catch (err) {
      onError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const overLimit = text.length > WARN_CHARS;

  return (
    <form onSubmit={handleSubmit} className="input-form">
      <label htmlFor="transcript-area" className="input-label">
        Paste your lecture transcript or messy voice-to-text notes below:
      </label>
      <textarea
        id="transcript-area"
        className={`transcript-area ${overLimit ? "transcript-area--warn" : ""}`}
        rows={12}
        placeholder="Paste raw lecture notes, auto-generated captions, or voice-to-text output here…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        aria-required="true"
      />
      <div className="form-footer">
        <span className={`char-count ${overLimit ? "char-count--warn" : ""}`}>
          {text.length.toLocaleString()} / {WARN_CHARS.toLocaleString()} chars
          {overLimit && " ⚠️ will be trimmed"}
        </span>
        <button type="submit" className="btn-primary" disabled={!text.trim()}>
          Analyse Lecture →
        </button>
      </div>
    </form>
  );
}
