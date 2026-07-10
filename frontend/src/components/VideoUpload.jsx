import React, { useState, useRef } from "react";
import { analyzeVideo } from "../api";

const ACCEPTED = ".mp4,.webm,.mov,.mkv,.avi";
const MAX_MB   = 200;

export default function VideoUpload({ mode, language, onResult, onError, setLoading }) {
  const [file, setFile]       = useState(null);
  const [dragging, setDragging] = useState(false);
  const inputRef              = useRef(null);

  const pickFile = (f) => {
    if (!f) return;
    if (f.size > MAX_MB * 1024 * 1024) return onError(`File exceeds ${MAX_MB} MB.`);
    setFile(f);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return onError("Please select a video file first.");
    setLoading(true);
    try {
      const data = await analyzeVideo(file, mode, language);
      onResult(data);
    } catch (err) { onError(err.message); }
    finally { setLoading(false); }
  };

  return (
    <form onSubmit={handleSubmit} className="input-form">
      <p className="input-label">Upload a lecture video (MP4, WebM, MOV, MKV, AVI — max {MAX_MB} MB). Audio extracted automatically.</p>
      <div className={`drop-zone ${dragging?"drop-zone--over":""} ${file?"drop-zone--filled":""}`}
        role="button" tabIndex={0} aria-label="Drop video or click to browse"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key==="Enter" && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files?.[0]); }}
      >
        {file ? <span className="drop-zone__filename">🎬 {file.name} ({(file.size/1048576).toFixed(1)} MB)</span>
              : <span className="drop-zone__prompt">Drag &amp; drop video here, or <u>click to browse</u></span>}
      </div>
      <input ref={inputRef} type="file" accept={ACCEPTED} className="visually-hidden" aria-hidden="true"
        onChange={(e) => pickFile(e.target.files?.[0])} />
      <div className="form-footer">
        {file && <button type="button" className="btn-ghost" onClick={() => setFile(null)}>Remove</button>}
        <button type="submit" className="btn-primary" disabled={!file}>Extract &amp; Analyse →</button>
      </div>
    </form>
  );
}
