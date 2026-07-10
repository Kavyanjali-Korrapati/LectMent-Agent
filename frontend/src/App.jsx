import React, { useState, useEffect } from "react";
import ChatBox from "./components/ChatBox";
import ResultPanel from "./components/ResultPanel";
import "./index.css";

const LANGUAGES = [
  "English","Spanish","French","Arabic","Hindi",
  "Mandarin","Portuguese","German","Japanese","Korean",
  "Italian","Turkish","Russian","Bengali","Swahili",
];

const HISTORY_KEY = "lectment_history";
const MAX_HISTORY = 8;

function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]"); }
  catch { return []; }
}
function saveHistory(h) { localStorage.setItem(HISTORY_KEY, JSON.stringify(h)); }

export default function App() {
  const [mode,     setMode]     = useState("study");
  const [language, setLanguage] = useState("English");
  const [result,   setResult]   = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState("");
  const [history,  setHistory]  = useState(loadHistory);
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem("lectment_dark") === "true");
  const [fontSize, setFontSize] = useState(() => Number(localStorage.getItem("lectment_fontsize") || 15));

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", darkMode ? "dark" : "light");
    localStorage.setItem("lectment_dark", darkMode);
  }, [darkMode]);

  useEffect(() => {
    document.documentElement.style.setProperty("--base-font", `${fontSize}px`);
    localStorage.setItem("lectment_fontsize", fontSize);
  }, [fontSize]);

  const handleResult = (data) => {
    setResult(data); setError("");
    const entry = {
      id: Date.now(), mode, language,
      label: data.summary?.split("\n")[0]?.replace(/^#+\s*/, "").slice(0, 60) || "Lecture",
      data,
    };
    setHistory((prev) => { const u = [entry, ...prev].slice(0, MAX_HISTORY); saveHistory(u); return u; });
  };
  const handleError = (msg) => { setError(msg); setResult(null); };
  const clearHistory = () => { setHistory([]); saveHistory([]); };

  return (
    <div className="app-shell">
      {/* ── Header ──────────────────────────────────────────────────── */}
      <header className="app-header">
        <div className="header-inner">
          <div className="header-top">
            <span className="logo-mark">LectMent</span>
            <div className="header-controls">
              <select className="lang-select" value={language} onChange={(e) => setLanguage(e.target.value)}
                aria-label="Output language" title="Output language">
                {LANGUAGES.map((l) => <option key={l}>{l}</option>)}
              </select>
              <button className="hdr-btn" onClick={() => setFontSize((s) => Math.max(12, s - 1))} title="Smaller text">A−</button>
              <button className="hdr-btn" onClick={() => setFontSize((s) => Math.min(22, s + 1))} title="Larger text">A+</button>
              <button className="hdr-btn" onClick={() => setDarkMode((d) => !d)} title="Dark / Light mode">
                {darkMode ? "☀️" : "🌙"}
              </button>
            </div>
          </div>
          <p className="tagline">Drop a lecture — get smart notes powered by IBM watsonx.ai</p>
        </div>
      </header>

      {/* ── Body ────────────────────────────────────────────────────── */}
      <div className="app-body app-body--centered">

        {/* History rail (left) */}
        {history.length > 0 && (
          <aside className="history-rail">
            <div className="history-header">
              <span className="history-title">Recent</span>
              <button className="btn-ghost-sm" onClick={clearHistory}>Clear</button>
            </div>
            {history.map((h) => (
              <button key={h.id} className="history-item"
                onClick={() => { setResult(h.data); setMode(h.mode); setLanguage(h.language); }}>
                <span className="history-mode">{h.mode}</span>
                <span className="history-label">{h.label}</span>
              </button>
            ))}
          </aside>
        )}

        {/* Main column */}
        <main className="app-main">
          {/* Chat input */}
          <ChatBox
            mode={mode} setMode={setMode}
            language={language}
            onResult={handleResult} onError={handleError} setLoading={setLoading}
          />

          {/* Status */}
          {loading && (
            <div className="status-bar status-bar--loading" role="status" aria-live="polite">
              <span className="spinner" aria-hidden="true" />
              Analysing in <strong>{mode}</strong> mode, output in <strong>{language}</strong>…
            </div>
          )}
          {error && (
            <div className="status-bar status-bar--error" role="alert">⚠️ {error}</div>
          )}

          {/* Results */}
          {result && !loading && <ResultPanel data={result} mode={mode} />}
        </main>
      </div>

      <footer className="app-footer">
        Powered by <strong>IBM watsonx.ai</strong> (Granite) &amp; <strong>IBM watsonx Orchestrate</strong>
      </footer>
    </div>
  );
}
