import streamlit as st
import pandas as pd
import requests
import sqlite3
import json
import os

st.set_page_config(
    page_title="Playa News",
    page_icon="🌴",
    layout="wide"
)

st.title("🌴 Playa News")
st.subheader("Tickster → Nyhetsbrev Dashboard")
st.caption("Automatisk synk från Tickster till Brevo")

# ====================== HÄMTA API-NYCKLAR ======================
# Fungerar både med Render Environment Variables och secrets.toml
TICKSTER_API_KEY = (
    os.getenv("TICKSTER_API_KEY") or 
    st.secrets.get("TICKSTER_API_KEY")
)
TICKSTER_BASE_URL = (
    os.getenv("TICKSTER_BASE_URL") or 
    st.secrets.get("TICKSTER_BASE_URL", "https://api.tickster.com")
)
BREVO_API_KEY = (
    os.getenv("BREVO_API_KEY") or 
    st.secrets.get("BREVO_API_KEY")
)
BREVO_LIST_ID = (
    os.getenv("BREVO_LIST_ID") or 
    st.secrets.get("BREVO_LIST_ID")
)

# ====================== DATATABELL ======================
conn = sqlite3.connect("kontakter.db", check_same_thread=False)
conn.execute("""
    CREATE TABLE IF NOT EXISTS kontakter (
        email TEXT PRIMARY KEY,
        name TEXT,
        phone TEXT,
        last_purchase TEXT,
        events TEXT,
        synced_to_brevo INTEGER DEFAULT 0
    )
""")

# ====================== FUNKTIONER ======================
def hämta_tickster_orders():
    if not TICKSTER_API_KEY:
        st.error("❌ TICKSTER_API_KEY saknas. Lägg till den i Render → Environment Variables.")
        return []
    
    url = f"{TICKSTER_BASE_URL}/orders"   # ← ÄNDRA denna rad när Tickster ger dig rätt endpoint
    headers = {"Authorization": f"Bearer {TICKSTER_API_KEY}"}
    params = {"limit": 1000}
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Fel vid kontakt med Tickster: {e}")
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
            json.dumps(order.get("events", []))
        ))
        antal += 1
    conn.commit()
    return antal

def synka_till_brevo():
    if not BREVO_API_KEY or not BREVO_LIST_ID:
        st.error("❌ BREVO_API_KEY eller BREVO_LIST_ID saknas.")
        return 0
    
    cursor = conn.cursor()
    cursor.execute("SELECT email, name, phone FROM kontakter WHERE synced_to_brevo = 0")
    rows = cursor.fetchall()
    if not rows:
        st.info("Alla kontakter är redan synkade.")
        return 0

    url = "https://api.brevo.com/v3/contacts"
    headers = {"api-key": BREVO_API_KEY, "Content-Type": "application/json"}
    synkade = 0

    for email, name, phone in rows:
        try:
            data = {
                "email": email,
                "attributes": {"FIRSTNAME": name or "", "SMS": phone or ""},
                "listIds": [int(BREVO_LIST_ID)]
            }
            r = requests.post(url, headers=headers, json=data)
            if r.status_code in (200, 201):
                synkade += 1
        except:
            pass

    cursor.execute("UPDATE kontakter SET synced_to_brevo = 1")
    conn.commit()
    return synkade

# ====================== GRÄNSSNITT ======================
tab1, tab2, tab3 = st.tabs(["🔄 Synka Tickster", "📋 Alla kontakter", "✉️ Skicka nyhetsbrev"])

with tab1:
    st.subheader("Hämta nya biljettköpare från Tickster")
    if st.button("🔄 Synka nu från Tickster", type="primary", use_container_width=True):
        with st.spinner("Hämtar data från Tickster..."):
            orders = hämta_tickster_orders()
            if orders:
                sparade = spara_till_db(orders)
                st.success(f"✅ {sparade} kontakter sparade i databasen")
                
                with st.spinner("Synkar till Brevo..."):
                    synkade = synka_till_brevo()
                    st.success(f"✅ {synkade} kontakter skickade till Brevo!")

with tab2:
    st.subheader("Alla kontakter")
    df = pd.read_sql_query("""
        SELECT email, name, phone, last_purchase, synced_to_brevo 
        FROM kontakter 
        ORDER BY last_purchase DESC
    """, conn)
    
    if len(df) > 0:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("📥 Ladda ner som CSV", df.to_csv(index=False), "playa_kontakter.csv")
    else:
        st.info("Inga kontakter än. Synka från Tickster först.")

with tab3:
    st.subheader("Skapa nyhetsbrev")
    st.link_button(
        "➡️ Öppna Brevo och skapa nytt brev →",
        "https://app.brevo.com/campaigns",
        use_container_width=True,
        type="primary"
    )

# Sidebar
with st.sidebar:
    st.header("🌴 Playa News")
    total = pd.read_sql("SELECT COUNT(*) as cnt FROM kontakter", conn).iloc[0]['cnt']
    st.metric("Totalt kontakter", total)
    st.caption("Enkel synk • Max 300 kr/mån")
