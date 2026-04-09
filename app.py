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

def rensa_och_spara_df(df_raw):
    df = df_raw.copy()
    df.columns = df.columns.str.strip().str.lower()
    
    email_col = next((col for col in df.columns if any(x in col for x in ['email', 'e-post', 'epost'])), None)
    name_col = next((col for col in df.columns if any(x in col for x in ['namn', 'name', 'köpare'])), None)
    phone_col = next((col for col in df.columns if any(x in col for x in ['telefon', 'phone', 'mobil'])), None)
    date_col = next((col for col in df.columns if any(x in col for x in ['datum', 'date', 'köp'])), None)
    
    if not email_col:
        st.error("Kunde inte hitta e-postkolumn i filen.")
        return 0, 0, 0
    
    rename_dict = {email_col: 'email'}
    if name_col: rename_dict[name_col] = 'name'
    if phone_col: rename_dict[phone_col] = 'phone'
    if date_col: rename_dict[date_col] = 'last_purchase'
    
    df = df.rename(columns=rename_dict)
    
    df['email'] = df['email'].astype(str).str.strip().str.lower()
    df = df[df['email'].str.contains('@', na=False)]
    df = df.drop_duplicates(subset=['email'], keep='last')
    
    cursor = conn.cursor()
    nya = 0
    uppdaterade = 0
    
    for _, row in df.iterrows():
        email = row['email']
        name = str(row.get('name', '')).strip()
        phone = str(row.get('phone', '')).strip()
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
    uploaded_file = st.file_uploader("Välj fil (.xlsx eller .csv)", type=["xlsx", "xls", "csv"])
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"✅ Filen lästes in – {len(df)} rader")
            st.dataframe(df.head(10))
            
            if st.button("💾 Bearbeta filen (ta bort dubbletter)", type="primary"):
                with st.spinner("Bearbetar..."):
                    total, nya, uppdaterade = rensa_och_spara_df(df)
                    st.success(f"✅ {total} unika kontakter\n({nya} nya, {uppdaterade} uppdaterade)")
                    
            if st.button("💾 Bearbeta + Synka till Brevo"):
                with st.spinner("Bearbetar och synkar..."):
                    total, nya, uppdaterade = rensa_och_spara_df(df)
                    synkade = synka_till_brevo()
                    st.success(f"✅ {total} unika | {nya} nya | {uppdaterade} uppdaterade | {synkade} skickade till Brevo")
                    
        except Exception as e:
            st.error(f"Fel vid läsning av filen: {e}")
            st.info("Tips: Se till att filen innehåller en kolumn med e-postadresser.")

with tab2:
    st.subheader("Alla kontakter")
    df_db = pd.read_sql_query("SELECT email, name, phone, last_purchase, updated_at FROM kontakter ORDER BY updated_at DESC", conn)
    if not df_db.empty:
        st.dataframe(df_db, use_container_width=True, hide_index=True)
        st.download_button("📥 Ladda ner alla kontakter", df_db.to_csv(index=False), "playa_kontakter.csv")

with tab3:
    st.link_button("➡️ Öppna Brevo", "https://app.brevo.com/campaigns", type="primary", use_container_width=True)

with st.sidebar:
    total = pd.read_sql("SELECT COUNT(*) as cnt FROM kontakter", conn).iloc[0]['cnt']
    st.metric("Totalt unika kontakter", total)
