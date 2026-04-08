import streamlit as st
import pandas as pd
import requests
import sqlite3
import json
import os


st.set_page_config(
    page_title="Playa News",
    page_icon="🌴",
    layout="wide",
    initial_sidebar_state="expanded"
)


st.title("🌴 Playa News")
st.subheader("Tickster → Nyhetsbrev Dashboard")
st.caption("Automatisk synk från Tickster till Brevo")


# ====================== KONFIG ======================
TICKSTER_API_KEY = st.secrets.get("TICKSTER_API_KEY") or os.getenv("TICKSTER_API_KEY")
TICKSTER_BASE_URL = st.secrets.get("TICKSTER_BASE_URL") or os.getenv("TICKSTER_BASE_URL")
BREVO_API_KEY = st.secrets.get("BREVO_API_KEY") or os.getenv("BREVO_API_KEY")
BREVO_LIST_ID = st.secrets.get("BREVO_LIST_ID") or os.getenv("BREVO_LIST_ID")


# SQLite databas
conn = sqlite3.connect("kontakter.db", check_same_thread=False)


conn.execute("""
    CREATE TABLE IF NOT EXISTS kontakter (
        email TEXT PRIMARY KEY,
        name TEXT,
        phone TEXT,
        last_purchase TEXT,
        events TEXT,
        synced_to_brevo INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")


# ====================== FUNKTIONER ======================
def hämta_tickster_orders():
    if not TICKSTER_API_KEY or not TICKSTER_BASE_URL:
        st.error("Tickster API-nyckel eller URL saknas.")
        return []
    
    # ÄNDRA DENNA RAD när du får exakt endpoint från Tickster
    url = f"{TICKSTER_BASE_URL}/orders"  
    headers = {"Authorization": f"Bearer {TICKSTER_API_KEY}"}
    params = {"limit": 1000}
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Fel från Tickster: {e}")
        return []


def spara_till_db(orders):
    if not orders:
        return 0
    cursor = conn.cursor()
    antal = 0
    for order in orders:
        buyer = order.get("buyer") or order.get("customer", {})
        email = buyer.get("email")
        if not email:
            continue
        cursor.execute("""
            INSERT OR REPLACE INTO kontakter 
            (email, name, phone, last_purchase, events, synced_to_brevo)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (
            email,
            buyer.get("name") or buyer.get("full_name"),
            buyer.get("phone"),
            order.get("purchase_date") or order.get("created_at"),
            json.dumps(order.get("events", []) or [])
        ))
        antal += 1
    conn.commit()
    return antal


def synka_till_brevo():
    cursor = conn.cursor()
    cursor.execute("SELECT email, name, phone FROM kontakter WHERE synced_to_brevo = 0")
    rows = cursor.fetchall()
    if not rows:
        return 0
    
    url = "https://api.brevo.com/v3/contacts"
    headers = {"api-key": BREVO_API_KEY, "Content-Type": "application/json"}
    synkade = 0
    for email, name, phone in rows:
        try:
            data = {
                "email": email,
                "attributes": {"FIRSTNAME": name or "", "SMS": phone or ""},
                "listIds": [int(BREVO_LIST_ID)] if BREVO_LIST_ID else []
            }
            r = requests.post(url, headers=headers, json=data)
            if r.status_code in [200, 201]:
                synkade += 1
        except:
            pass
    cursor.execute("UPDATE kontakter SET synced_to_brevo = 1")
    conn.commit()
    return synkade


# ====================== TABS ======================
tab1, tab2, tab3 = st.tabs(["🔄 Synka Tickster", "📋 Alla kontakter", "✉️ Skicka nyhetsbrev"])


with tab1:
    st.subheader("Hämta nya biljettköpare")
    if st.button("🔄 Synka nu från Tickster", type="primary", use_container_width=True):
        with st.spinner("Hämtar från Tickster..."):
            orders = hämta_tickster_orders()
            if orders:
                sparade = spara_till_db(orders)
                st.success(f"{sparade} kontakter sparade")
                with st.spinner("Synkar till Brevo..."):
                    synkade = synka_till_brevo()
                    st.success(f"{synkade} kontakter skickade till Brevo")


with tab2:
    st.subheader("Alla kontakter")
    df = pd.read_sql_query("SELECT email, name, phone, last_purchase, synced_to_brevo FROM kontakter ORDER BY last_purchase DESC", conn)
    if len(df) > 0:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("📥 Ladda ner CSV", df.to_csv(index=False), "playa_kontakter.csv")
    else:
        st.info("Inga kontakter än – synka först.")


with tab3:
    st.subheader("Skapa nyhetsbrev i Brevo")
    st.link_button("➡️ Öppna Brevo och skapa brev", "https://app.brevo.com/campaigns", use_container_width=True, type="primary")


with st.sidebar:
    st.header("🌴 Playa News")
    total = len(pd.read_sql("SELECT 1 FROM kontakter", conn))
    st.metric("Kontakter totalt", total)
    st.caption("Byggd för Playa")