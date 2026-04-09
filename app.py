import streamlit as st
import pandas as pd
import requests
import sqlite3
import json
import os
from datetime import datetime

st.set_page_config(
    page_title="Playa News",
    page_icon="🌴",
    layout="wide"
)

st.title("🌴 Playa News")
st.subheader("Tickster → Nyhetsbrev Dashboard")
st.caption("Ladda upp CSV från Tickster → Synk till Brevo")

# ====================== BREVO INSTÄLLNINGAR ======================
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_LIST_ID = os.getenv("BREVO_LIST_ID")

if not BREVO_API_KEY:
    st.error("❌ BREVO_API_KEY saknas i Render Environment Variables")
if not BREVO_LIST_ID:
    st.warning("⚠️ BREVO_LIST_ID saknas – lägg till den i Render")

# ====================== DATATABELL ======================
conn = sqlite3.connect("kontakter.db", check_same_thread=False)
conn.execute("""
    CREATE TABLE IF NOT EXISTS kontakter (
        email TEXT PRIMARY KEY,
        name TEXT,
        phone TEXT,
        last_purchase TEXT,
        source TEXT,
        synced_to_brevo INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")

# ====================== FUNKTIONER ======================
def spara_till_db(df):
    cursor = conn.cursor()
    antal = 0
    for _, row in df.iterrows():
        email = str(row.get('email', '')).strip().lower()
        if not email or email == 'nan' or '@' not in email:
            continue
            
        name = str(row.get('name', '')).strip()
        phone = str(row.get('phone', '')).strip()
        last_purchase = str(row.get('purchase_date', '')).strip() or str(row.get('date', ''))
        
        cursor.execute("""
            INSERT OR REPLACE INTO kontakter 
            (email, name, phone, last_purchase, source, synced_to_brevo)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (email, name, phone, last_purchase, "CSV från Tickster"))
        antal += 1
    conn.commit()
    return antal

def synka_till_brevo():
    if not BREVO_API_KEY or not BREVO_LIST_ID:
        st.error("Brevo API-nyckel eller List ID saknas.")
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
tab1, tab2, tab3 = st.tabs(["📤 Ladda upp CSV", "📋 Alla kontakter", "✉️ Skicka nyhetsbrev"])

with tab1:
    st.subheader("Ladda upp CSV-fil från Tickster")
    st.info("Exportera dina ordrar/kunder som CSV från Tickster och ladda upp filen här.")
    
    uploaded_file = st.file_uploader("Välj CSV-fil från Tickster", type=["csv"])
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.success(f"✅ Filen lästes in med {len(df)} rader")
            st.dataframe(df.head(), use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Spara kontakter i databasen", type="primary"):
                    with st.spinner("Sparar kontakter..."):
                        antal = spara_till_db(df)
                        st.success(f"✅ {antal} kontakter sparade/uppdaterade")
            
            with col2:
                if st.button("🔄 Spara + Synka till Brevo"):
                    with st.spinner("Sparar och synkar till Brevo..."):
                        antal = spara_till_db(df)
                        synkade = synka_till_brevo()
                        st.success(f"✅ {antal} sparade | {synkade} synkade till Brevo")
                        
        except Exception as e:
            st.error(f"Fel vid läsning av CSV: {e}")

with tab2:
    st.subheader("Alla kontakter")
    df_db = pd.read_sql_query("""
        SELECT email, name, phone, last_purchase, source, synced_to_brevo 
        FROM kontakter 
        ORDER BY created_at DESC
    """, conn)
    
    if len(df_db) > 0:
        st.dataframe(df_db, use_container_width=True, hide_index=True)
        st.download_button("📥 Ladda ner alla kontakter som CSV", 
                          df_db.to_csv(index=False), 
                          "playa_kontakter.csv")
    else:
        st.info("Inga kontakter än. Ladda upp en CSV-fil först.")

with tab3:
    st.subheader("Skapa nyhetsbrev i Brevo")
    st.link_button(
        "➡️ Öppna Brevo och skapa nytt nyhetsbrev →",
        "https://app.brevo.com/campaigns",
        use_container_width=True,
        type="primary"
    )

# Sidebar
with st.sidebar:
    st.header("🌴 Playa News")
    total = pd.read_sql("SELECT COUNT(*) as cnt FROM kontakter", conn).iloc[0]['cnt']
    st.metric("Totalt antal kontakter", total)
    st.caption("CSV-uppladdning från Tickster")
