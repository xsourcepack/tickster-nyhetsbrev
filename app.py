import streamlit as st
import pandas as pd
import requests
import sqlite3
import os

st.set_page_config(page_title="Playa News", page_icon="🌴", layout="wide")

st.title("🌴 Playa News")
st.subheader("Tickster → Nyhetsbrev Dashboard")

BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_LIST_ID = os.getenv("BREVO_LIST_ID")

conn = sqlite3.connect("kontakter.db", check_same_thread=False)
conn.execute("""
    CREATE TABLE IF NOT EXISTS kontakter (
        email TEXT PRIMARY KEY,
        name TEXT,
        phone TEXT,
        last_purchase TEXT,
        source TEXT,
        synced_to_brevo INTEGER DEFAULT 0,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")

# ====================== SYNK-FUNKTION ======================
def synka_till_brevo():
    if not BREVO_API_KEY:
        st.error("❌ BREVO_API_KEY saknas i Render")
        return 0
    if not BREVO_LIST_ID:
        st.error("❌ BREVO_LIST_ID saknas eller är felaktig")
        return 0

    cursor = conn.cursor()
    cursor.execute("SELECT email, name, phone FROM kontakter WHERE synced_to_brevo = 0")
    rows = cursor.fetchall()

    if not rows:
        st.info("Alla kontakter är redan synkade till Brevo.")
        return 0

    url = "https://api.brevo.com/v3/contacts"
    headers = {"api-key": BREVO_API_KEY, "Content-Type": "application/json"}
    synkade = 0
    fel = 0

    for email, name, phone in rows:
        try:
            data = {
                "email": email,
                "attributes": {"FIRSTNAME": name or "", "SMS": phone or ""},
                "listIds": [int(BREVO_LIST_ID)],
                "updateEnabled": True
            }
            r = requests.post(url, headers=headers, json=data, timeout=10)
            if r.status_code in (200, 201):
                synkade += 1
            else:
                fel += 1
                if fel == 1:  # Visa bara första felet
                    st.warning(f"Brevo svarade med kod {r.status_code}: {r.text[:200]}")
        except Exception as e:
            fel += 1

    # Markera som synkade
    cursor.execute("UPDATE kontakter SET synced_to_brevo = 1")
    conn.commit()

    st.success(f"✅ {synkade} kontakter skickade till Brevo ({fel} fel)")
    return synkade

# ====================== GRÄNSSNITT ======================
tab1, tab2, tab3 = st.tabs(["📤 Ladda upp fil", "📋 Alla kontakter", "✉️ Skicka nyhetsbrev"])

with tab1:
    st.subheader("Ladda upp Excel eller CSV från Tickster")
    uploaded_file = st.file_uploader("Välj fil (.xlsx eller .csv)", type=["xlsx", "xls", "csv"])
    # ... (behåll din befintliga uppladdningskod här om du vill, annars kan vi förenkla)

with tab2:
    st.subheader("Alla kontakter")
    df_db = pd.read_sql_query("SELECT email, name, phone, last_purchase, updated_at FROM kontakter ORDER BY updated_at DESC LIMIT 100", conn)
    st.dataframe(df_db, use_container_width=True, hide_index=True)
    total = pd.read_sql("SELECT COUNT(*) as cnt FROM kontakter", conn).iloc[0]['cnt']
    st.write(f"Totalt i databasen: **{total}** kontakter")

    if st.button("🔄 Synka alla osynkade kontakter till Brevo", type="primary"):
        with st.spinner("Synkar till Brevo..."):
            synka_till_brevo()

with tab3:
    st.link_button("➡️ Öppna Brevo och skapa nyhetsbrev", 
                   "https://app.brevo.com/campaigns", 
                   type="primary", use_container_width=True)

with st.sidebar:
    total = pd.read_sql("SELECT COUNT(*) as cnt FROM kontakter", conn).iloc[0]['cnt']
    st.metric("Totalt unika kontakter", total)
    st.caption("3936 kontakter sparade")
