"""
IBM watsonx.ai + IBM watsonx Orchestrate client.

Priority:
  1. If ORCHESTRATE_API_KEY + ORCHESTRATE_SKILL_FLOW_ID are set ->
       route the prompt through an IBM Orchestrate skill flow (REST call).
  2. Otherwise -> call Granite directly via ibm-watsonx-ai SDK.

Credentials are read lazily (inside functions, not at import time) so the
server starts cleanly even if .env is not yet configured.
"""
import logging
import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

# Load .env from the project root (two levels up from this file: services/ -> backend/ -> root)
_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_ROOT / ".env", override=False)

log = logging.getLogger("lectment.watsonx")

# ── Default Granite model (overridable via WATSONX_MODEL_ID env var) ──────────
DEFAULT_MODEL_ID = "meta-llama/llama-3-3-70b-instruct"

# ── Per-mode generation parameters ───────────────────────────────────────────
#   Research uses sampling for richer, more varied output.
#   All other modes use greedy decoding for deterministic structured output.
MODE_GEN_PARAMS: dict[str, dict] = {
    "research": {
        GenParams.DECODING_METHOD    : "sample",
        GenParams.MAX_NEW_TOKENS     : 1800,
        GenParams.MIN_NEW_TOKENS     : 100,
        GenParams.TEMPERATURE        : 0.7,
        GenParams.TOP_P              : 0.9,
        GenParams.REPETITION_PENALTY : 1.1,
    },
    "study": {
        GenParams.DECODING_METHOD    : "greedy",
        GenParams.MAX_NEW_TOKENS     : 1600,
        GenParams.MIN_NEW_TOKENS     : 80,
        GenParams.REPETITION_PENALTY : 1.1,
    },
    "sheet": {
        GenParams.DECODING_METHOD    : "greedy",
        GenParams.MAX_NEW_TOKENS     : 1400,
        GenParams.MIN_NEW_TOKENS     : 80,
        GenParams.REPETITION_PENALTY : 1.1,
    },
    "quiz": {
        GenParams.DECODING_METHOD    : "greedy",
        GenParams.MAX_NEW_TOKENS     : 1600,
        GenParams.MIN_NEW_TOKENS     : 80,
        GenParams.REPETITION_PENALTY : 1.1,
    },
    "summarize": {
        GenParams.DECODING_METHOD    : "greedy",
        GenParams.MAX_NEW_TOKENS     : 1200,
        GenParams.MIN_NEW_TOKENS     : 80,
        GenParams.REPETITION_PENALTY : 1.1,
    },
}

# Fallback for unknown modes
_DEFAULT_GEN_PARAMS = {
    GenParams.DECODING_METHOD    : "greedy",
    GenParams.MAX_NEW_TOKENS     : 1400,
    GenParams.MIN_NEW_TOKENS     : 80,
    GenParams.REPETITION_PENALTY : 1.1,
}


def _creds() -> dict:
    """Read credentials lazily — raises a clear error if missing."""
    api_key    = os.environ.get("WATSONX_API_KEY", "")
    project_id = os.environ.get("WATSONX_PROJECT_ID", "")
    url        = os.environ.get("WATSONX_URL") or "https://us-south.ml.cloud.ibm.com"
    model_id   = os.environ.get("WATSONX_MODEL_ID") or DEFAULT_MODEL_ID
    if not api_key:
        raise EnvironmentError(
            "WATSONX_API_KEY is not set. Copy .env.example to .env and fill in your key."
        )
    if not project_id:
        raise EnvironmentError(
            "WATSONX_PROJECT_ID is not set. Copy .env.example to .env and fill in your project ID."
        )
    return {"api_key": api_key, "project_id": project_id, "url": url, "model_id": model_id}


# ─────────────────────────────────────────────────────────────────────────────
# Path 1 — IBM watsonx Orchestrate  (skill flow)
# ─────────────────────────────────────────────────────────────────────────────

def _iam_token(api_key: str) -> str:
    """Exchange an IBM Cloud IAM API key for a short-lived bearer token."""
    resp = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


@retry(
    retry=retry_if_exception_type(requests.HTTPError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _orchestrate_generate(prompt: str) -> str:
    """POST the prompt to an IBM Orchestrate skill flow and return the text output."""
    orch_key      = os.environ.get("ORCHESTRATE_API_KEY", "")
    orch_url      = os.environ.get("ORCHESTRATE_INSTANCE_URL", "")
    orch_flow_id  = os.environ.get("ORCHESTRATE_SKILL_FLOW_ID", "")

    token = _iam_token(orch_key)
    url   = f"{orch_url.rstrip('/')}/v1/skill_flows/{orch_flow_id}/invoke"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type" : "application/json",
        "Accept"       : "application/json",
    }
    log.info("Calling Orchestrate skill flow %s", orch_flow_id)
    resp = requests.post(url, json={"input": prompt}, headers=headers, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    if "output" in data:
        return str(data["output"]).strip()
    if "result" in data:
        return str(data["result"]).strip()
    return str(data)


# ─────────────────────────────────────────────────────────────────────────────
# Path 2 — IBM watsonx.ai Granite (direct SDK)
# ─────────────────────────────────────────────────────────────────────────────

# Retry only on transient network / HTTP errors — not on EnvironmentError or ValueError
_RETRYABLE = (requests.HTTPError, ConnectionError, TimeoutError)

@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _granite_generate(prompt: str, mode: str = "study") -> str:
    c = _creds()
    print("=" * 50)
    print("URL      :", c["url"])
    print("PROJECT  :", c["project_id"])
    print("MODEL    :", c["model_id"])
    print("=" * 50)
    params = MODE_GEN_PARAMS.get(mode, _DEFAULT_GEN_PARAMS)
    log.info(
        "Calling Granite model=%s mode=%s decoding=%s max_tokens=%d prompt_len=%d",
        c["model_id"], mode,
        params.get(GenParams.DECODING_METHOD, "greedy"),
        params.get(GenParams.MAX_NEW_TOKENS, 1400),
        len(prompt),
    )
    credentials = Credentials(url=c["url"], api_key=c["api_key"])
    client      = APIClient(credentials, project_id=c["project_id"])
    model       = ModelInference(
        model_id   = c["model_id"],
        api_client = client,
        params     = params,
    )
    result = model.generate_text(prompt=prompt).strip()
    log.info("Granite response received, length=%d chars", len(result))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate(prompt: str, mode: str = "study") -> str:
    """
    Route to Orchestrate skill flow when credentials are present,
    otherwise call Granite directly.
    Both paths have automatic retry (up to 3 attempts, exponential back-off).
    mode is used to select per-mode generation params for the Granite path.
    """
    orch_key     = os.environ.get("ORCHESTRATE_API_KEY", "")
    orch_url     = os.environ.get("ORCHESTRATE_INSTANCE_URL", "")
    orch_flow_id = os.environ.get("ORCHESTRATE_SKILL_FLOW_ID", "")

    if orch_key and orch_url and orch_flow_id:
        return _orchestrate_generate(prompt)
    return _granite_generate(prompt, mode)
