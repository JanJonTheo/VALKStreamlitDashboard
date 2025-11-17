import requests
import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

# API_BASE z.B. "http://127.0.0.1:5000/api" oder ohne /api je nach Deployment
API_BASE = os.getenv("API_BASE", "").rstrip("/")

def get_api_key(api_key=None):
    # Verwende explizit übergebenen API-Key oder den aus der Session
    if api_key:
        return api_key
    if hasattr(st, "session_state") and "api_key" in st.session_state and st.session_state.api_key:
        return st.session_state.api_key
    return None

def verify_user(username, password, api_key=None):
    """
    Ruft die Login-Route auf und gibt die JSON-Response des Backends unverändert zurück.
    Erwartete Felder u.a.: faction_logo, faction_name, tenant_name, username, is_admin, id
    """
    headers = {}
    key = get_api_key(api_key)
    if key:
        headers["apikey"] = key  # optional; Backend-/Proxy-Setups akzeptieren das idR.
    try:
        # Unterstützt beide Varianten: mit /api oder ohne (API_BASE flexibel halten)
        url = f"{API_BASE}/login" if API_BASE.endswith("/api") else f"{API_BASE}/api/login"
        r = requests.post(url, json={"username": username, "password": password}, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json()
        else:
            # Für Diagnose in der Console hilfreich
            print("Login failed:", r.status_code, r.text)
        return None
    except Exception as ex:
        print("Login exception:", ex)
        return None

def user_has_access(user, page, api_key=None):
    # Optional: Page-spezifische Rechte per API prüfen
    if user.get("is_admin"):
        return True
    return True
