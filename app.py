import streamlit as st
import pandas as pd
import requests
import sqlite3
import os
from datetime import datetime

st.set_page_config(page_title="Playa News", page_icon="🌴", layout="wide")

st.title("🌴 Playa News")
st.subheader("Tickster → Nyhetsbrev Dashboard")
st.caption("CSV-uppladdning med dubblett-hantering")

BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_LIST_ID = os.getenv("BREVO_LIST_ID")

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
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")

# ====================== FUNKTIONER ======================
def rensa_och_spara_df(df):
    # Rensa data
    df = df.copy()
    df['email'] = df['email'].astype(str).str.strip().str.lower()
    df = df[df['email'].str.contains('@')]  # ta bort rader utan giltig e-post
    
    # Ta bort dubbletter – behåll den senaste raden (baserat på index eller datum om möjligt)
    df = df.drop_duplicates(subset=['email'], keep='last')
    
    cursor = conn.cursor()
    nya = 0
    uppdaterade = 0
    
    for _, row in df.iterrows():
        email = row['email']
        name = str(row.get('name', '')).strip()
        phone = str(row.get('phone', '')).strip()
        last_purchase = str(row.get('purchase_date', '') or row.get('date', '')).strip()
        
        # Kolla om e-post redan finns
        cursor.execute("SELECT email FROM kontakter WHERE email = ?", (email,))
        exists = cursor.fetchone()
        
        if exists:
            uppdaterade += 1
        else:
            nya += 1
            
        cursor.execute("""
            INSERT OR REPLACE INTO kontakter 
            (email, name, phone, last_purchase, source, synced_to_brevo, updated_at)
            VALUES (?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
        """, (email, name, phone, last_purchase, "CSV från Tickster"))
    
    conn.commit()
    return len(df), nya, uppdaterade

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
                "listIds": [int(BREVO_LIST_ID)],
                "updateEnabled": True   # ← Detta uppdaterar befintliga kontakter
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
    uploaded_file = st.file_uploader("Välj CSV-fil", type=["csv"])
    
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.write(f"Filen innehåller **{len(df)}** rader")
        st.dataframe(df.head(10))
        
        if st.button("💾 Bearbeta filen (ta bort dubbletter + spara)", type="primary"):
            with st.spinner("Rensar dubbletter och sparar..."):
                total, nya, uppdaterade = rensa_och_spara_df(df)
                st.success(f"✅ Klar! Totalt {total} unika e-postadresser bearbetade ({nya} nya, {uppdaterade} uppdaterade)")

        if st.button("💾 Bearbeta + Synka direkt till Brevo"):
            with st.spinner("Bearbetar och synkar..."):
                total, nya, uppdaterade = rensa_och_spara_df(df)
                synkade = synka_till_brevo()
                st.success(f"✅ {total} unika | {nya} nya | {uppdaterade} uppdaterade | {synkade} skickade till Brevo")

with tab2:
    st.subheader("Alla kontakter i databasen")
    df_db = pd.read_sql_query("SELECT email, name, phone, last_purchase, updated_at FROM kontakter ORDER BY updated_at DESC", conn)
    st.dataframe(df_db, use_container_width=True, hide_index=True)
    
    if not df_db.empty:
        st.download_button("📥 Ladda ner alla kontakter", df_db.to_csv(index=False), "playa_kontakter.csv")

with tab3:
    st.link_button("➡️ Öppna Brevo och skapa nyhetsbrev", "https://app.brevo.com/campaigns", type="primary", use_container_width=True)

with st.sidebar:
    total = pd.read_sql("SELECT COUNT(*) as cnt FROM kontakter", conn).iloc[0]['cnt']
    st.metric("Totalt unika kontakter", total)
