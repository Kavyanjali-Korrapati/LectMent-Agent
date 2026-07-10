import React, { useState } from "react";
import { analyzeYoutube } from "../api";

export default function YoutubeInput({ mode, language, onResult, onError, setLoading }) {
  const [url, setUrl] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return onError("Please enter a YouTube URL.");
    if (!trimmed.includes("youtube.com") && !trimmed.includes("youtu.be"))
      return onError("That doesn't look like a valid YouTube URL.");
    setLoading(true);
    try {
      const data = await analyzeYoutube(trimmed, mode, language);
      onResult(data);
    } catch (err) {
      onError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="input-form">
      <label htmlFor="yt-url" className="input-label">
        Paste a YouTube lecture URL (auto-generated captions are supported):
      </label>
      <div className="url-row">
        <input id="yt-url" type="url" className="url-input"
          placeholder="https://www.youtube.com/watch?v=…"
          value={url} onChange={(e) => setUrl(e.target.value)} aria-required="true"
        />
        <button type="submit" className="btn-primary" disabled={!url.trim()}>
          Analyse →
        </button>
      </div>
      <p className="helper-text">Works with English manual or auto-generated captions.</p>
    </form>
  );
}
