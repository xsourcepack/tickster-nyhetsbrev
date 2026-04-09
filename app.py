import streamlit as st
import pandas as pd
import requests
import sqlite3
import os
from datetime import datetime

st.set_page_config(page_title="Playa News", page_icon="🌴", layout="wide")

st.title("🌴 Playa News")
st.subheader("Tickster → Nyhetsbrev Dashboard")
st.caption("Stöd för Excel (.xlsx) och CSV från Tickster-rapporter")

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

# ====================== HJÄLPFUNKTIONER ======================
def rensa_och_spara_df(df_raw):
    df = df_raw.copy()
    
    # Normalisera kolumnnamn (vanliga namn från Tickster-rapporter)
    df.columns = df.columns.str.strip().str.lower()
    
    # Hitta rätt kolumner (flexibelt)
    email_col = next((col for col in df.columns if 'email' in col or 'e-post' in col), None)
    name_col = next((col for col in df.columns if 'namn' in col or 'name' in col or 'köpare' in col), None)
    phone_col = next((col for col in df.columns if 'telefon' in col or 'phone' in col or 'mobil' in col), None)
    date_col = next((col for col in df.columns if 'datum' in col or 'date' in col or 'köp' in col), None)
    
    if not email_col:
        st.error("Kunde inte hitta någon e-postkolumn i filen. Kolla att filen innehåller e-postadresser.")
        return 0, 0, 0
    
    df = df.rename(columns={
        email_col: 'email',
        name_col: 'name' if name_col else None,
        phone_col: 'phone' if phone_col else None,
        date_col: 'last_purchase' if date_col else None
    })
    
    # Rensa data
    df['email'] = df['email'].astype(str).str.strip().str.lower()
    df = df[df['email'].str.contains('@', na=False)]   # ta bort rader utan e-post
    
    # Ta bort exakta dubbletter baserat på e-post (behåll senaste)
    df = df.drop_duplicates(subset=['email'], keep='last')
    
    cursor = conn.cursor()
    nya = 0
    uppdaterade = 0
    
    for _, row in df.iterrows():
        email = row['email']
        name = str(row.get('name', '')).strip() if 'name' in row else ''
        phone = str(row.get('phone', '')).strip() if 'phone' in row else ''
        last_purchase = str(row.get('last_purchase', '')).strip()
        
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
        """, (email, name, phone, last_purchase, "Tickster rapport"))
    
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
                "updateEnabled": True
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
tab1, tab2, tab3 = st.tabs(["📤 Ladda upp fil", "📋 Alla kontakter", "✉️ Skicka nyhetsbrev"])

with tab1:
    st.subheader("Ladda upp Excel eller CSV från Tickster")
    st.info("Du kan ladda upp både **.xlsx** (Excel) och **.csv** filer från Ticksters rapporter.")
    
    uploaded_file = st.file_uploader("Välj fil från Tickster", type=["xlsx", "xls", "csv"])
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"✅ Filen lästes in – {len(df)} rader hittades")
            st.dataframe(df.head(8), use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                if
