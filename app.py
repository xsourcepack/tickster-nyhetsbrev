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

# Databas
conn = sqlite3.connect("kontakter.db", check_same_thread=False)
conn.execute("""
    CREATE TABLE IF NOT EXISTS kontakter (
        email TEXT PRIMARY KEY,
        name TEXT,
        phone TEXT,
        last_purchase TEXT,
        source TEXT DEFAULT "Tickster",
        synced_to_brevo INTEGER DEFAULT 0,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")

# ====================== FUNKTIONER ======================
def synka_till_brevo():
    if not BREVO_API_KEY or not BREVO_LIST_ID:
        st.error("❌ Brevo API-nyckel eller List ID saknas i Render")
        return 0

    cursor = conn.cursor()
    cursor.execute("SELECT email, name, phone FROM kontakter WHERE synced_to_brevo = 0")
    rows = cursor.fetchall()

    if not rows:
        st.info("✅ Alla kontakter är redan synkade till Brevo.")
        return 0

    url = "https://api.brevo.com/v3/contacts"
    headers = {"api-key": BREVO_API_KEY, "Content-Type": "application/json"}
    synkade = 0

    with st.spinner(f"Synkar {len(rows)} kontakter till Brevo..."):
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
            except:
                pass

    cursor.execute("UPDATE kontakter SET synced_to_brevo = 1")
    conn.commit()
    st.success(f"✅ {synkade} kontakter skickade till Brevo!")
    return synkade

# ====================== SIDAN ======================
tab1, tab2, tab3 = st.tabs(["📤 Ladda upp fil", "📋 Alla kontakter", "✉️ Nyhetsbrev"])

with tab1:
    st.subheader("Ladda upp Excel eller CSV från Tickster")
    uploaded_file = st.file_uploader("Välj Excel eller CSV-fil", type=["xlsx", "xls", "csv"])
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"✅ Filen lästes in – {len(df)} rader")
            st.dataframe(df.head(10), use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Bearbeta fil (spara kontakter)", type="primary"):
                    with st.spinner("Sparar kontakter..."):
                        # Enkel version av bearbetning
                        df.columns = df.columns.str.strip().str.lower()
                        email_col = next((col for col in df.columns if 'email' in col or 'e-post' in col), None)
                        if email_col:
                            df = df.rename(columns={email_col: 'email'})
                            df['email'] = df['email'].astype(str).str.strip().str.lower()
                            df = df[df['email'].str.contains('@')]
                            df = df.drop_duplicates(subset=['email'], keep='last')
                            
                            cursor = conn.cursor()
                            for _, row in df.iterrows():
                                cursor.execute("""
                                    INSERT OR REPLACE INTO kontakter (email, name, phone, source)
                                    VALUES (?, ?, ?, ?)
                                """, (row['email'], row.get('name', ''), row.get('phone', ''), "Tickster"))
                            conn.commit()
                            st.success(f"✅ {len(df)} kontakter sparade/uppdaterade")
                        else:
                            st.error("Kunde inte hitta e-postkolumn")
        except Exception as e:
            st.error(f"Fel: {e}")

with tab2:
    st.subheader("Alla kontakter")
    
    # Visa antal
    total = pd.read_sql("SELECT COUNT(*) as cnt FROM kontakter", conn).iloc[0]['cnt']
    st.metric("Totalt unika kontakter", total)
    
    # Visa tabell (max 100 rader för att inte bli för långsam)
    df_show = pd.read_sql_query("""
        SELECT email, name, phone, last_purchase, updated_at 
        FROM kontakter 
        ORDER BY updated_at DESC LIMIT 100
    """, conn)
    
    if not df_show.empty:
        st.dataframe(df_show, use_container_width=True, hide_index=True)
    else:
        st.info("Inga kontakter än.")

    # Knapp för att synka
    if st.button("🔄 Synka alla osynkade kontakter till Brevo", type="primary", use_container_width=True):
        synka_till_brevo()

    if st.button("📥 Ladda ner alla kontakter som CSV"):
        df_all = pd.read_sql_query("SELECT * FROM kontakter", conn)
        st.download_button("Ladda ner nu", df_all.to_csv(index=False), "playa_kontakter.csv", "text/csv")

with tab3:
    st.subheader("Skapa nyhetsbrev")
    st.link_button("➡️ Öppna Brevo och skapa nytt nyhetsbrev", 
                   "https://app.brevo.com/campaigns", 
                   type="primary", use_container_width=True)

with st.sidebar:
    total = pd.read_sql("SELECT COUNT(*) as cnt FROM kontakter", conn).iloc[0]['cnt']
    st.metric("Totalt unika kontakter", total)
    st.caption("3936 kontakter sparade tidigare")
