import React, { useState, useRef } from "react";
import { analyzeText, analyzeYoutube, analyzeAudio, analyzeVideo } from "../api";

const WARN_CHARS = 12_000;

const MODES = [
  { id: "study",     icon: "📚", label: "Study",             desc: "Deep notes + quiz"           },
  { id: "research",  icon: "🔍", label: "Research",          desc: "Lecture + web context"        },
  { id: "sheet",     icon: "📄", label: "Cheat Sheet",       desc: "Printable 1–2 page card"      },
  { id: "quiz",      icon: "🧠", label: "Quiz & Flashcards", desc: "MCQ quiz + flip cards"        },
  { id: "summarize", icon: "✨", label: "Summarize",         desc: "Clean concise summary"        },
];

const UPLOAD_OPTIONS = [
  { id: "youtube", icon: "▶️",  label: "YouTube Link" },
  { id: "audio",   icon: "🎙️", label: "Audio File"   },
  { id: "video",   icon: "🎬", label: "Video File"   },
];

const DIFFICULTY_OPTIONS = [
  { id: "easy",   label: "Easy",   color: "#22c55e" },
  { id: "medium", label: "Medium", color: "#f59e0b" },
  { id: "hard",   label: "Hard",   color: "#ef4444" },
];

const AUDIO_ACCEPT = ".mp3,.wav,.flac,.ogg,.m4a";
const VIDEO_ACCEPT = ".mp4,.webm,.mov,.mkv,.avi";

export default function ChatBox({ mode, setMode, language, onResult, onError, setLoading }) {
  const [text,        setText]        = useState("");
  const [modeOpen,    setModeOpen]    = useState(false);
  const [uploadOpen,  setUploadOpen]  = useState(false);
  const [diffOpen,    setDiffOpen]    = useState(false);
  const [uploadType,  setUploadType]  = useState(null);   // "youtube" | "audio" | "video" | null
  const [ytUrl,       setYtUrl]       = useState("");
  const [mediaFile,   setMediaFile]   = useState(null);
  const [dragging,    setDragging]    = useState(false);
  const [difficulty,  setDifficulty]  = useState("medium");
  const [numCards,    setNumCards]    = useState(8);

  const audioRef = useRef(null);
  const videoRef = useRef(null);

  const currentMode = MODES.find((m) => m.id === mode) || MODES[0];
  const currentDiff = DIFFICULTY_OPTIONS.find((d) => d.id === difficulty) || DIFFICULTY_OPTIONS[1];

  // ── Close all dropdowns when clicking outside ──────────────────────────────
  const closeAll = () => { setModeOpen(false); setUploadOpen(false); setDiffOpen(false); };

  // ── Submit handler — decides which API to call ──────────────────────────────
  const handleSubmit = async (e) => {
    e?.preventDefault();
    closeAll();

    if (uploadType === "youtube") {
      if (!ytUrl.trim()) return onError("Please enter a YouTube URL.");
      if (!ytUrl.includes("youtube.com") && !ytUrl.includes("youtu.be"))
        return onError("That doesn't look like a valid YouTube URL.");
      setLoading(true);
      try   { onResult(await analyzeYoutube(ytUrl.trim(), mode, language, difficulty, numCards)); }
      catch (err) { onError(err.message); }
      finally { setLoading(false); }
      return;
    }

    if (uploadType === "audio" || uploadType === "video") {
      if (!mediaFile) return onError("Please select a file first.");
      setLoading(true);
      try {
        const fn = uploadType === "audio" ? analyzeAudio : analyzeVideo;
        onResult(await fn(mediaFile, mode, language, difficulty));
      } catch (err) { onError(err.message); }
      finally { setLoading(false); }
      return;
    }

    // Default — plain text
    if (!text.trim()) return onError("Please type or paste a transcript first.");
    setLoading(true);
    try   { onResult(await analyzeText(text.trim(), mode, language, difficulty, numCards)); }
    catch (err) { onError(err.message); }
    finally { setLoading(false); }
  };

  const selectUploadType = (id) => {
    setUploadType(id);
    setUploadOpen(false);
    setMediaFile(null);
    setYtUrl("");
  };

  const clearUpload = () => { setUploadType(null); setMediaFile(null); setYtUrl(""); };

  const pickFile = (f, maxMB) => {
    if (!f) return;
    if (f.size > maxMB * 1024 * 1024) { onError(`File exceeds ${maxMB} MB.`); return; }
    setMediaFile(f);
  };

  const overLimit = text.length > WARN_CHARS;

  // ── Keyboard: Ctrl/Cmd+Enter submits ───────────────────────────────────────
  const onKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") handleSubmit();
  };

  return (
    <div className="chatbox-wrap" onClick={(e) => {
      if (!e.target.closest(".chatbox-dropdown") &&
          !e.target.closest(".toolbar-btn")) closeAll();
    }}>
      {/* ── Main textarea (shown only for text mode) ── */}
      {!uploadType && (
        <textarea
          className={`chatbox-textarea ${overLimit ? "chatbox-textarea--warn" : ""}`}
          rows={6}
          placeholder="Paste transcript, lecture notes, or voice-to-text here… (Ctrl+Enter to send)"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          aria-label="Lecture transcript"
        />
      )}

      {/* ── YouTube URL inline input ── */}
      {uploadType === "youtube" && (
        <div className="chatbox-upload-preview">
          <span className="upload-preview-icon">▶️</span>
          <input
            type="url"
            className="chatbox-url-input"
            placeholder="https://www.youtube.com/watch?v=…"
            value={ytUrl}
            onChange={(e) => setYtUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            aria-label="YouTube URL"
            autoFocus
          />
          <button className="upload-clear-btn" onClick={clearUpload} title="Cancel">✕</button>
        </div>
      )}

      {/* ── Audio / Video file inline picker ── */}
      {(uploadType === "audio" || uploadType === "video") && (
        <div
          className={`chatbox-upload-preview chatbox-drop ${dragging ? "chatbox-drop--over" : ""} ${mediaFile ? "chatbox-drop--filled" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault(); setDragging(false);
            pickFile(e.dataTransfer.files?.[0], uploadType === "audio" ? 50 : 200);
          }}
          onClick={() => (uploadType === "audio" ? audioRef : videoRef).current?.click()}
          style={{ cursor: mediaFile ? "default" : "pointer" }}
        >
          <span className="upload-preview-icon">{uploadType === "audio" ? "🎙️" : "🎬"}</span>
          {mediaFile
            ? <span className="upload-file-name">{mediaFile.name} <em>({(mediaFile.size/1048576).toFixed(1)} MB)</em></span>
            : <span className="upload-drop-hint">Drop file here or click to browse · max {uploadType === "audio" ? "50" : "200"} MB</span>
          }
          <button className="upload-clear-btn" onClick={(e) => { e.stopPropagation(); clearUpload(); }} title="Cancel">✕</button>
        </div>
      )}

      {/* hidden file inputs */}
      <input ref={audioRef} type="file" accept={AUDIO_ACCEPT} className="visually-hidden" aria-hidden="true"
        onChange={(e) => pickFile(e.target.files?.[0], 50)} />
      <input ref={videoRef} type="file" accept={VIDEO_ACCEPT} className="visually-hidden" aria-hidden="true"
        onChange={(e) => pickFile(e.target.files?.[0], 200)} />

      {/* ── Bottom toolbar ──────────────────────────────────────────── */}
      <div className="chatbox-toolbar">
        <div className="toolbar-left">

          {/* Mode dropdown */}
          <div className="toolbar-dropdown-wrap">
            <button
              className={`toolbar-btn toolbar-btn--mode ${modeOpen ? "toolbar-btn--open" : ""}`}
              onClick={() => { setModeOpen((o) => !o); setUploadOpen(false); setDiffOpen(false); }}
              aria-expanded={modeOpen}
              aria-haspopup="listbox"
              title="Select learning mode"
            >
              <span>{currentMode.icon}</span>
              <span className="toolbar-btn-label">{currentMode.label}</span>
              <span className="toolbar-caret">▾</span>
            </button>

            {modeOpen && (
              <div className="chatbox-dropdown chatbox-dropdown--mode" role="listbox" aria-label="Learning mode">
                {MODES.map((m) => (
                  <button
                    key={m.id}
                    role="option"
                    aria-selected={mode === m.id}
                    className={`dropdown-item ${mode === m.id ? "dropdown-item--active" : ""}`}
                    onClick={() => { setMode(m.id); setModeOpen(false); }}
                  >
                    <span className="di-icon">{m.icon}</span>
                    <span className="di-text">
                      <span className="di-label">{m.label}</span>
                      <span className="di-desc">{m.desc}</span>
                    </span>
                    {mode === m.id && <span className="di-check">✓</span>}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Upload dropdown */}
          <div className="toolbar-dropdown-wrap">
            <button
              className={`toolbar-btn toolbar-btn--upload ${uploadOpen ? "toolbar-btn--open" : ""} ${uploadType ? "toolbar-btn--active" : ""}`}
              onClick={() => { setUploadOpen((o) => !o); setModeOpen(false); setDiffOpen(false); }}
              aria-expanded={uploadOpen}
              aria-haspopup="listbox"
              title="Upload or add media"
            >
              <span>📎</span>
              <span className="toolbar-btn-label">
                {uploadType ? UPLOAD_OPTIONS.find((u) => u.id === uploadType)?.label : "Upload"}
              </span>
              <span className="toolbar-caret">▾</span>
            </button>

            {uploadOpen && (
              <div className="chatbox-dropdown chatbox-dropdown--upload" role="listbox" aria-label="Upload type">
                {uploadType && (
                  <button className="dropdown-item dropdown-item--clear" onClick={() => { clearUpload(); setUploadOpen(false); }}>
                    <span className="di-icon">✕</span>
                    <span className="di-text"><span className="di-label">Clear upload</span></span>
                  </button>
                )}
                {UPLOAD_OPTIONS.map((u) => (
                  <button
                    key={u.id}
                    role="option"
                    aria-selected={uploadType === u.id}
                    className={`dropdown-item ${uploadType === u.id ? "dropdown-item--active" : ""}`}
                    onClick={() => selectUploadType(u.id)}
                  >
                    <span className="di-icon">{u.icon}</span>
                    <span className="di-text"><span className="di-label">{u.label}</span></span>
                    {uploadType === u.id && <span className="di-check">✓</span>}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Difficulty dropdown + flashcard count — only shown in quiz mode */}
          {mode === "quiz" && (
            <div className="toolbar-dropdown-wrap">
              <button
                className={`toolbar-btn toolbar-btn--diff ${diffOpen ? "toolbar-btn--open" : ""}`}
                onClick={() => { setDiffOpen((o) => !o); setModeOpen(false); setUploadOpen(false); }}
                aria-expanded={diffOpen}
                aria-haspopup="listbox"
                title="Set difficulty level"
                style={{ "--diff-color": currentDiff.color }}
              >
                <span className="diff-dot" style={{ background: currentDiff.color }} />
                <span className="toolbar-btn-label">{currentDiff.label}</span>
                <span className="toolbar-caret">▾</span>
              </button>

              {diffOpen && (
                <div className="chatbox-dropdown chatbox-dropdown--diff" role="listbox" aria-label="Difficulty">
                  {DIFFICULTY_OPTIONS.map((d) => (
                    <button
                      key={d.id}
                      role="option"
                      aria-selected={difficulty === d.id}
                      className={`dropdown-item ${difficulty === d.id ? "dropdown-item--active" : ""}`}
                      onClick={() => { setDifficulty(d.id); setDiffOpen(false); }}
                    >
                      <span className="diff-dot" style={{ background: d.color }} />
                      <span className="di-text"><span className="di-label">{d.label}</span></span>
                      {difficulty === d.id && <span className="di-check">✓</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {mode === "quiz" && (
            <div className="toolbar-cards-wrap" title="Number of flashcards to generate">
              <span className="toolbar-cards-label">🃏</span>
              <input
                type="number"
                className="toolbar-cards-input"
                min={3}
                max={20}
                value={numCards}
                onChange={(e) => {
                  const v = Math.max(3, Math.min(20, Number(e.target.value) || 8));
                  setNumCards(v);
                }}
                aria-label="Number of flashcards"
              />
              <span className="toolbar-cards-label">cards</span>
            </div>
          )}
        </div>

        <div className="toolbar-right">
          {/* Char count — only for text mode */}
          {!uploadType && text.length > 0 && (
            <span className={`chatbox-charcount ${overLimit ? "chatbox-charcount--warn" : ""}`}>
              {text.length.toLocaleString()}{overLimit ? " ⚠️" : ""}
            </span>
          )}

          {/* Send button */}
          <button
            className="chatbox-send"
            onClick={handleSubmit}
            disabled={!uploadType ? !text.trim() : uploadType === "youtube" ? !ytUrl.trim() : !mediaFile}
            aria-label="Analyse lecture"
            title="Analyse (Ctrl+Enter)"
          >
            Analyse ↑
          </button>
        </div>
      </div>
    </div>
  );
}
