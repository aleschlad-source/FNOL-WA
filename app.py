import streamlit as st
import pandas as pd
import datetime
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
        margin-bottom: 20px;
    }
    /* Úprava odsazení na mobilech */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    /* Šedá kurzíva pro dodatečné vysvětlivky v názvech polí */
    label p em {
        color: #888888;
        font-weight: normal;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

MASTER_DATA_PATH = "zdroj.xlsx"
LOCAL_BACKUP_PATH = "VYSTUP.xlsx"

@st.cache_data
def load_master_data():
    if os.path.exists(MASTER_DATA_PATH):
        # Načteme excel, uživatel data vyčistil do 3 sloupců bez definované hlavičky
        df_raw = pd.read_excel(MASTER_DATA_PATH, header=None)
        
        if len(df_raw.columns) >= 3:
            df = df_raw.rename(columns={
                df_raw.columns[0]: "Název objektu",
                df_raw.columns[1]: "IFCGUID",
                df_raw.columns[2]: "Umístění - místnost"
            })
        else:
            df = df_raw
            
        for c in ["Umístění - místnost", "Název objektu", "IFCGUID"]:
            if c not in df.columns:
                df[c] = ""
                
        # Doplnění "NEZNAME" u prázdných místností podle pravidla
        df["Umístění - místnost"] = df["Umístění - místnost"].fillna("NEZNAME").replace("", "NEZNAME")
        
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

if "vyrobni_cislo" not in st.session_state:
    st.session_state.vyrobni_cislo = ""

st.title("FNOL WA ředitelství - Sběr dat")
st.markdown("Aplikace pro zadávání atributů a majetku pro CAFM přímo na stavbě.")

# --- ZPRACOVÁNÍ FORMULÁŘE (FUNKCE) ---
def pre_validation():
    required_keys = [
        "room", "obj", "guid", "typ", "vyrobce", 
        "dodavatel", "dodavatel_kontakt", "revize_datum", "revize_url", "cinnosti"
    ]
    
    missing = []
    for k in required_keys:
        val = st.session_state.get(k)
        if val is None or str(val).strip() == "":
            missing.append(k)
            
    vc = st.session_state.get("vyrobni_cislo", "").strip()
    if not vc:
        missing.append("vyrobni_cislo")
        
    return missing, vc

def action_save():
    missing, vc = pre_validation()
    
    dt_val = st.session_state.revize_datum
    if isinstance(dt_val, datetime.date):
        rev_datum_str = dt_val.strftime('%d.%m.%Y')
    else:
        rev_datum_str = str(dt_val)

    record = {
        "Místnost": st.session_state.room,
        "Název objektu": st.session_state.obj,
        "IFCGUID": st.session_state.guid,
        "Typ": st.session_state.typ,
        "Výrobní číslo": vc,
        "Výrobce": st.session_state.vyrobce,
        "Dodavatel": st.session_state.dodavatel,
        "Kontakt dodavatele": st.session_state.dodavatel_kontakt,
        "Datum revize": rev_datum_str,
        "Odkaz revize": st.session_state.revize_url,
        "Činnosti": st.session_state.cinnosti,
        "Datum vyplnění": datetime.datetime.now().strftime('%d.%m.%Y'),
        "Čas vyplnění": datetime.datetime.now().strftime('%H:%M:%S')
    }
    st.session_state.collected_data.append(record)
        
    # Záloha do lokálního souboru
    try:
        df_export = pd.DataFrame(st.session_state.collected_data)
        df_export.to_excel(LOCAL_BACKUP_PATH, index=False)
    except Exception as e:
        print(f"Nepodařilo se zálohovat: {e}")

    # Vymazání pouze výrobního čísla
    st.session_state.vyrobni_cislo = ""

def submit_callback():
    missing, vc = pre_validation()
    if missing:
        st.session_state.form_error = "Chyba: Některá povinná pole chybí! Zkontrolujte i doplňující data úplně dole."
    else:
        action_save()
        st.session_state.form_success = f"Úspěšně uloženo pro výrobní číslo: {vc}! (Pole vymazáno)"
        if 'form_error' in st.session_state:
            del st.session_state['form_error']


# --- ČÁST 1. KASKÁDA A VÝROBNÍ ČÍSLO (NAHOŘE) ---
st.header("1. Identifikace a štítkování")
st.markdown("Pro interakci na stavbě – nejdůležitější blok nahoře. Místnost, objekt, GUID a sériové číslo.")

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

# Změna u výrobního čísla
st.text_input("Výrobní číslo * — *Sériové číslo, případně jiné relevantní pořadové číslo. Zadejte NA, pokud žádné číslo neobsahuje.*", key="vyrobni_cislo")


# --- TLAČÍTKO SUBMIT ---
st.button("ULOŽIT ZÁZNAM", type="primary", on_click=submit_callback)

# Zobrazení notifikací z uložení PŘÍMO POD tlačítkem
if 'form_error' in st.session_state:
    st.error(st.session_state.form_error)
if 'form_success' in st.session_state:
    st.success(st.session_state.form_success)
    # Po zobrazení smazat, ať nezůstává úspech po dalším např. napsání písmenka
    del st.session_state['form_success']


# --- HISTORIE A EXPORT (POD TLAČÍTKEM) ---
if st.session_state.collected_data:
    st.write("---")
    st.subheader(f"Historie zadaných prvků ({len(st.session_state.collected_data)})")
    
    df_export = pd.DataFrame(st.session_state.collected_data)
    
    # Zobrazení klíčových dat rovnou na displeji, nejnovější záznamy nahoře
    ukazka_df = df_export[["Datum vyplnění", "Čas vyplnění", "Místnost", "Název objektu", "Výrobní číslo"]].iloc[::-1]
    st.dataframe(ukazka_df, use_container_width=True, hide_index=True)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='NasbiranaData')
        
    st.download_button(
        label="📥 STÁHNOUT EXCEL VYSTUP",
        data=buffer.getvalue(),
        file_name=f"VYSTUP_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="secondary"
    )

st.write("---")

# --- ČÁST 2. OBECNÁ DATA (DOLE) ---
st.header("2. Doplňující data")
st.markdown("Vyplňte pouze při změně typu prvku – hodnoty zůstávají trvale zapamatovány pro další ukládání.")

st.text_input("Typ * — *Produktový název výrobku nebo zařízení*", key="typ")
st.text_input("Výrobce * — *Konkrétní výrobce prvku nebo zařízení*", key="vyrobce")
st.text_input("Dodavatel (ne zhotovitel) * — *Dodavatel dílčí části*", key="dodavatel")
st.text_input("Kontakt * — *Jméno, telefonní číslo, email*", key="dodavatel_kontakt")

st.date_input("Datum výchozí revize/kontroly *", value=None, key="revize_datum")
st.text_input("č. výchozí revize/kontroly (odkaz na CDE) * — *Číslo výchozí revize nebo případně odkaz na CDE*", key="revize_url")

cinnosti_opts = ["REVIZE se neprovádí"] + [f"{m} měsíců" for m in range(3, 63, 3)]
st.selectbox("Prováděné pravidelné činnosti a jejich periody *", options=cinnosti_opts, key="cinnosti")

