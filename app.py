import streamlit as st
import pandas as pd
import datetime
import re
import io
import os

# --- KONFIGURACE APLIKACE ---
st.set_page_config(page_title="FNOL WA ředitelství CAFM", layout="centered", initial_sidebar_state="collapsed")

# Stylování pro mobily
st.markdown("""
<style>
    /* Velká tlačítka */
    .stButton > button {
        width: 100%;
        height: 60px;
        font-size: 20px !important;
        font-weight: bold;
        margin-top: 10px;
        margin-bottom: 10px;
    }
    /* Úprava odsazení na mobilech */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

MASTER_DATA_PATH = "zdroj.xlsx"
LOCAL_BACKUP_PATH = "lokalni_zaloha_pracovni.xlsx"

@st.cache_data
def load_master_data():
    if os.path.exists(MASTER_DATA_PATH):
        # Načteme excel, hlavičky cizího zdroje jsou většinou až na 2. řádku (header=1)
        df_raw = pd.read_excel(MASTER_DATA_PATH, header=1)
        
        # Přejmenování sloupců podle pozic (aby aplikace fungovala s původní logikou)
        # 0 = Podlaží
        # 1 = Název objektu (např. SNIM - 01)
        # 2 = GUID (Archicad IFC ID)
        # 3 = Místnost (Číslo související zóny)
        
        if len(df_raw.columns) >= 4:
            df = df_raw.rename(columns={
                df_raw.columns[3]: "Umístění - místnost",
                df_raw.columns[1]: "Název objektu",
                df_raw.columns[2]: "IFCGUID"
            })
        else:
            df = df_raw
            
        for c in ["Umístění - místnost", "Název objektu", "IFCGUID"]:
            if c not in df.columns:
                df[c] = ""
        return df
    else:
        st.warning(f"Referenční soubor {MASTER_DATA_PATH} nebyl nalezen. Bude vytvořena prázdná databáze. Pro funkční kaskádu prosím zajistěte, aby byl soubor dostupný ve složce s aplikací.")
        return pd.DataFrame(columns=["Umístění - místnost", "Název objektu", "IFCGUID"])

df_master = load_master_data()

# --- INITIALIZACE STAVU ---
if "collected_data" not in st.session_state:
    if os.path.exists(LOCAL_BACKUP_PATH):
        try:
            # Načti existující zálohu, pokud existuje
            st.session_state.collected_data = pd.read_excel(LOCAL_BACKUP_PATH).to_dict('records')
        except:
            st.session_state.collected_data = []
    else:
        st.session_state.collected_data = []

if "vyrobni_cisla" not in st.session_state:
    st.session_state.vyrobni_cisla = ""

st.title("FNOL WA ředitelství - Sběr dat")
st.markdown("Aplikace pro zadávání atributů a majetku pro CAFM přímo na stavbě.")

# --- KASKÁDA (Záznamy) ---
st.header("1. Umístění a identifikace (Kaskáda)")

room_options = [""] + sorted(list(df_master["Umístění - místnost"].dropna().astype(str).unique()))
selected_room = st.selectbox("Umístění - místnost *", options=room_options, key="room")

object_options = [""]
if selected_room:
    df_room = df_master[df_master["Umístění - místnost"].astype(str) == selected_room]
    object_options = [""] + sorted(list(df_room["Název objektu"].dropna().astype(str).unique()))
selected_object = st.selectbox("Název objektu *", options=object_options, key="obj")

guid_options = [""]
if selected_room and selected_object:
    df_guid = df_master[
        (df_master["Umístění - místnost"].astype(str) == selected_room) & 
        (df_master["Název objektu"].astype(str) == selected_object)
    ]
    guid_opts = list(df_guid["IFCGUID"].dropna().astype(str).unique())
    if len(guid_opts) == 1:
        guid_options = guid_opts 
    else:
        guid_options = [""] + guid_opts

selected_guid = st.selectbox("IFCGUID *", options=guid_options, key="guid")

# --- FORMULÁŘ (Doplňující data) ---
st.header("2. Doplňující data")

st.text_input("Kód *", key="kod")
st.text_input("Typ *", key="typ")

# Speciální pole pro výrobní čísla
st.text_area("Výrobní číslo (více čísel oddělte novým řádkem nebo čárkou) *", key="vyrobni_cisla")

st.text_input("Výrobce *", key="vyrobce")
st.text_input("Dodavatel (ne zhotovitel) *", key="dodavatel")
st.text_input("Dodavatel - osoba, email, tel. číslo *", key="dodavatel_kontakt")

st.date_input("Datum výchozí revize/kontroly *", value=None, key="revize_datum")
st.text_input("č. výchozí revize/kontroly (odkaz na CDE) *", key="revize_url")
st.text_area("Prováděné pravidelné činnosti a jejich periody *", key="cinnosti")

st.markdown("### Checklist dokumentů *")
# Checklist zobrazen klasicky pod sebou pro bezproblémové fungování na mobilu
st.selectbox("Návod v ČJ", ["Ano", "Ne"], index=1, key="chk_navod")
st.selectbox("Instruktáž uživatelů", ["Ano", "Ne"], index=1, key="chk_instruktaz")
st.selectbox("Školení techniků", ["Ano", "Ne"], index=1, key="chk_skoleni")
st.selectbox("Prohlášení o shodě", ["Ano", "Ne"], index=1, key="chk_shoda")
st.selectbox("Certifikát školitele", ["Ano", "Ne"], index=1, key="chk_certifikat")

st.write("---")

# --- ZPRACOVÁNÍ FORMULÁŘE ---

def pre_validation():
    required_keys = [
        "room", "obj", "guid", "kod", "typ", "vyrobce", 
        "dodavatel", "dodavatel_kontakt", "revize_datum", "revize_url", "cinnosti"
    ]
    
    missing = []
    for k in required_keys:
        val = st.session_state.get(k)
        if val is None or str(val).strip() == "":
            missing.append(k)
            
    vys_cisla_raw = st.session_state.get("vyrobni_cisla", "")
    vcs = [vc.strip() for vc in re.split(r'[\n,]+', vys_cisla_raw) if vc.strip()]
    
    if not vcs:
        missing.append("vyrobni_cisla (čísla nenalezena)")
        
    return missing, vcs

def action_save():
    missing, vcs = pre_validation()
    
    for vc in vcs:
        dt_val = st.session_state.revize_datum
        if isinstance(dt_val, datetime.date):
            rev_datum_str = dt_val.strftime('%d.%m.%Y')
        else:
            rev_datum_str = str(dt_val)

        record = {
            "Místnost": st.session_state.room,
            "Název objektu": st.session_state.obj,
            "IFCGUID": st.session_state.guid,
            "Kód": st.session_state.kod,
            "Typ": st.session_state.typ,
            "Výrobní číslo": vc,
            "Výrobce": st.session_state.vyrobce,
            "Dodavatel": st.session_state.dodavatel,
            "Kontakt dodavatele": st.session_state.dodavatel_kontakt,
            "Datum revize": rev_datum_str,
            "Odkaz revize": st.session_state.revize_url,
            "Činnosti": st.session_state.cinnosti,
            "Návod v ČJ": st.session_state.chk_navod,
            "Prohlášení o shodě": st.session_state.chk_shoda,
            "Instruktáž": st.session_state.chk_instruktaz,
            "Certifikát školitele": st.session_state.chk_certifikat,
            "Školení techniků": st.session_state.chk_skoleni,
            "Čas pořízení": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        st.session_state.collected_data.append(record)
        
    # Záloha do lokálního souboru
    try:
        df_export = pd.DataFrame(st.session_state.collected_data)
        df_export.to_excel(LOCAL_BACKUP_PATH, index=False)
    except Exception as e:
        print(f"Nepodařilo se zálohovat: {e}")

    # Vymazání pouze výrobních čísel 
    st.session_state.vyrobni_cisla = ""

def submit_callback():
    missing, vcs = pre_validation()
    if missing:
        st.session_state.form_error = "Chyba: Některá povinná pole chybí! Doplňte všechna pole se symbolem hvězdičky (*)."
    else:
        action_save()
        st.session_state.form_success = f"Úspěšně uloženo {len(vcs)} položek! Data zůstala pro další zadávání, pole 'Výrobní číslo' bylo smazáno."
        if 'form_error' in st.session_state:
            del st.session_state['form_error']

st.button("ULOŽIT ZÁZNAM", type="primary", on_click=submit_callback)

# Zobrazení notifikací z callbacku
if 'form_error' in st.session_state:
    st.error(st.session_state.form_error)
if 'form_success' in st.session_state:
    st.success(st.session_state.form_success)
    # Po zobrazení smazat, ať nezůstává po dalším reloadu
    del st.session_state['form_success']

# --- EXPORT ---
if st.session_state.collected_data:
    st.write("---")
    st.subheader(f"Zatím nasbíráno: {len(st.session_state.collected_data)} záznamů")
    
    df_export = pd.DataFrame(st.session_state.collected_data)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='NasbiranaData')
        
    st.download_button(
        label="📥 EXPORTOVAT DO EXCELU (Všechny záznamy)",
        data=buffer.getvalue(),
        file_name=f"export_cafm_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="secondary"
    )
