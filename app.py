import json
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="Test connexion Pennylane API", layout="wide")

COMPANY_BASE_URL = "https://app.pennylane.com/api/external/v2"

DEFAULT_TIMEOUT = 20  # seconds


# -----------------------------
# Helpers
# -----------------------------
def build_headers(token: str) -> dict:
    # Pennylane: Authorization: Bearer <TOKEN> :contentReference[oaicite:1]{index=1}
    return {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return {"_raw": resp.text}


def api_get(token: str, endpoint: str, params: dict | None = None):
    url = f"{COMPANY_BASE_URL}{endpoint}"
    headers = build_headers(token)
    resp = requests.get(url, headers=headers, params=params, timeout=DEFAULT_TIMEOUT)
    payload = safe_json(resp)
    return resp.status_code, payload, url


def normalize_items(payload):
    """
    Les endpoints listent généralement un array dans une clé type 'items' ou directement un array.
    On gère les 2 cas.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ["items", "data", "results"]:
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    return None


def show_result(title: str, status_code: int, payload, url: str):
    ok = 200 <= status_code < 300
    if ok:
        st.success(f"{title} ✅ ({status_code})")
    else:
        st.error(f"{title} ❌ ({status_code})")

    st.caption(url)

    items = normalize_items(payload)
    if items is not None and len(items) > 0 and isinstance(items[0], dict):
        df = pd.json_normalize(items)
        st.dataframe(df, use_container_width=True, hide_index=True)
        with st.expander("Voir la réponse JSON brute"):
            st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")
    else:
        st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")


# -----------------------------
# UI
# -----------------------------
st.title("🔌 Test connexion Pennylane (API Company v2)")

st.markdown(
    """
Cette app sert à **valider rapidement** :
- que le **token** est correct,
- que les **scopes** permettent bien la lecture,
- et que Streamlit peut appeler Pennylane sans souci.
"""
)

with st.sidebar:
    st.header("Auth")

    token_from_secrets = st.secrets.get("PENNYLANE_TOKEN", "") if hasattr(st, "secrets") else ""
    token = st.text_input(
        "Token API Pennylane (Bearer)",
        value=token_from_secrets,
        type="password",
        help="Idéalement, mets-le dans .streamlit/secrets.toml (PENNYLANE_TOKEN).",
    )

    st.divider()
    st.header("Tests")
    do_journals = st.checkbox("Lister les journaux (/journals)", value=True)
    do_accounts = st.checkbox("Lister les comptes (/ledger_accounts)", value=True)
    do_entries = st.checkbox("Lister des écritures (/ledger_entries)", value=False)
    do_transactions = st.checkbox("Lister des transactions bancaires (/transactions)", value=False)

    st.divider()
    st.header("Filtres (optionnels)")

    # Filtre simple "période récente" (si l'API ignore, ce n'est pas bloquant : on verra dans la réponse)
    days_back = st.number_input("Jours en arrière (pour filtres date)", min_value=1, max_value=365, value=30)
    start = date.today() - timedelta(days=int(days_back))
    end = date.today()
    st.caption(f"Période: {start.isoformat()} → {end.isoformat()}")

    run = st.button("▶️ Tester la connexion", use_container_width=True)

if not run:
    st.info("Renseigne ton token puis clique **Tester la connexion**.")
    st.stop()

if not token or not token.strip():
    st.warning("Il me faut un token pour lancer les tests.")
    st.stop()

# -----------------------------
# Calls
# -----------------------------
st.subheader("Résultats")

cols = st.columns(2)
left, right = cols[0], cols[1]

with left:
    if do_journals:
        # GET /journals :contentReference[oaicite:2]{index=2}
        status, payload, url = api_get(token, "/journals")
        show_result("Journaux", status, payload, url)

    if do_accounts:
        # GET /ledger_accounts :contentReference[oaicite:3]{index=3}
        status, payload, url = api_get(token, "/ledger_accounts")
        show_result("Comptes (ledger_accounts)", status, payload, url)

with right:
    if do_entries:
        # GET /ledger_entries :contentReference[oaicite:4]{index=4}
        # Certains environnements supportent des filtres date; si ignorés, tu verras juste plus/moins d'items.
        params = {"start_date": start.isoformat(), "end_date": end.isoformat()}
        status, payload, url = api_get(token, "/ledger_entries", params=params)
        show_result("Écritures (ledger_entries)", status, payload, url)

    if do_transactions:
        # GET /transactions :contentReference[oaicite:5]{index=5}
        params = {"start_date": start.isoformat(), "end_date": end.isoformat()}
        status, payload, url = api_get(token, "/transactions", params=params)
        show_result("Transactions (transactions)", status, payload, url)

st.divider()
st.subheader("Aide au diagnostic (si ça ne marche pas)")

st.markdown(
    """
- **401/403** : token invalide ou scopes insuffisants (ex. `journals:readonly`, `ledger_accounts:readonly`, `ledger_entries:readonly`, `transactions:readonly`). :contentReference[oaicite:6]{index=6}  
- **429** : rate limit → il faudra mettre un petit retry/backoff dans le client. :contentReference[oaicite:7]{index=7}  
- **Changements 2026** : certaines ressources “ledger” ont des changements de scopes/pagination → on adaptera le client si tu es concerné. :contentReference[oaicite:8]{index=8}
"""
)
