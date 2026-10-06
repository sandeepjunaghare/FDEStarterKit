"""Streamlit front end. Skeleton: shows the API connection; pane C adds the chat view."""

import os

import httpx
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8710").rstrip("/")

st.set_page_config(page_title="FDE assistant", page_icon="💬")
st.title("FDE assistant")


def get(path: str) -> tuple[bool, str]:
    """GET an API path; returns (ok, body or error class) without raising."""
    try:
        r = httpx.get(f"{API_URL}{path}", timeout=10)
        return r.is_success, r.text
    except httpx.HTTPError as e:
        return False, type(e).__name__


with st.sidebar:
    st.caption("API")
    st.code(API_URL, language=None)
    checks = {path: get(path) for path in ("/health", "/version", "/health/db")}
    for path, (ok, body) in checks.items():
        st.write(f"{'✅' if ok else '❌'} `{path}` {body}")

if all(ok for ok, _ in checks.values()):
    st.success("Connected to the API and the database.")
else:
    st.error(f"Can't reach the API at {API_URL}. Start it, or set API_URL.")

st.chat_input("Chat arrives with POST /chat", disabled=True)
