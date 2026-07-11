/**
 * LectMent API helpers.
 * All calls pass the selected mode + output language to the backend.
 */

const BASE = import.meta.env.VITE_API_BASE ?? "";
/**
 * Parse the response body safely — never throws on non-JSON bodies.
 * If the body is not JSON, returns a synthetic error object.
 */
async function _safeJson(res) {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    // Server returned plain text / HTML (e.g. 502 Bad Gateway from proxy)
    return { detail: text.trim().slice(0, 300) || `HTTP ${res.status}` };
  }
}

async function _post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method : "POST",
    headers: { "Content-Type": "application/json" },
    body   : JSON.stringify(body),
  });
  const data = await _safeJson(res);
  if (!res.ok) throw new Error(data.detail ?? `Request failed (${res.status})`);
  return data;
}

async function _postForm(path, formData) {
  const res = await fetch(`${BASE}${path}`, { method: "POST", body: formData });
  const data = await _safeJson(res);
  if (!res.ok) throw new Error(data.detail ?? `Request failed (${res.status})`);
  return data;
}

export const analyzeText = (transcript, mode, language, difficulty = "medium", numCards = 8) =>
  _post("/api/analyze/text", { transcript, mode, language, difficulty, num_cards: numCards });

export const analyzeYoutube = (url, mode, language, difficulty = "medium", numCards = 8) =>
  _post("/api/analyze/youtube", { url, mode, language, difficulty, num_cards: numCards });

export const analyzeAudio = (file, mode, language, difficulty = "medium") => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("mode", mode);
  fd.append("language", language);
  fd.append("difficulty", difficulty);
  return _postForm("/api/analyze/audio", fd);
};

export const analyzeVideo = (file, mode, language, difficulty = "medium") => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("mode", mode);
  fd.append("language", language);
  fd.append("difficulty", difficulty);
  return _postForm("/api/analyze/video", fd);
};

/**
 * Ask a follow-up question about the transcript produced in the current session.
 * @param {string} transcript  - The original raw transcript text
 * @param {string} question    - The student's follow-up question
 * @param {string} mode        - Current learning mode
 * @param {string} language    - Output language
 * @returns {Promise<{answer: string, question: string}>}
 */
export const askQuestion = (transcript, question, mode, language) =>
  _post("/api/analyze/ask", { transcript, question, mode, language });
