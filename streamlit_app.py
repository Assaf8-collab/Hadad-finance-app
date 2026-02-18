import streamlit as st
import pandas as pd
import json
import os
import re

# --- 1. ניהול הגדרות וזיכרון ---
SETTINGS_FILE = 'app_settings.json'

def load_settings():
    default = {
        "approved_income": [], "approved_expenses": [], 
        "savings_list": [], "credit_categories": {}, "excluded_credit": []
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for key in default:
                    if key not in data: data[key] = default[key]
                return data
        except: return default
    return default

def save_settings(settings_dict):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings_dict, f, ensure_ascii=False, indent=4)

# --- 2. פונקציות עזר (משופרות לטיפול במט"ח) ---
CATEGORIES = ['אחר', 'קניות סופר', 'רכב', 'ביטוח', 'ביגוד', 'אוכל בחוץ', 'בילויים', 'חסכון והשקעות']

def clean_amount(v):
    """מנקה כל סכום כספי ומחלץ רק את המספר, תומך במט"ח ומינוסים"""
    if pd.isna(v) or v == '': return 0.0
    if isinstance(v, (int, float)): return float(v)
    
    # הסרת סימני מטבע, פסיקים ורווחים, השארת נקודה עשרונית ומינוס
    cleaned = re.sub(r'[^\d\.\-]', '', str(v))
    try:
        return float(cleaned)
    except:
        return 0.0

def get_initial_category(description, settings):
    desc = str(description)
    if desc in settings['credit_categories']:
        return settings['credit_categories'][desc]
    
    mapping = {
        'קניות סופר': ['שופרסל', 'הכל כאן', 'יוחננוף', 'קשת טעמים', 'רמי לוי', 'ויקטורי', 'מחסני השוק'],
        'אוכל בחוץ': ['מסעדה', 'קפה', 'וולט', 'WOLT', 'מקדונלד', 'פיצה'],
        'רכב': ['פנגו', 'פז', 'סונול', 'דור אלון', 'חניון', 'דלק'],
        'ביגוד': ['זארה', 'ZARA', 'H&M', 'טרמינל', 'TERMINAL']
    }
    desc_lower = desc.lower()
    for cat, keys in mapping.items():
        if any(k in desc_lower for k in keys): return cat
    return 'אחר'

# --- 3. ממשק משתמש ---
st.set_page_config(page_title="ניהול תקציב משפחתי", layout="wide")

with st.sidebar:
    st.header("⚙️ הגדרות")
    if st.button("🗑️ איפוס כל ההגדרות"):
        if os.path.exists(SETTINGS_FILE): os.remove(SETTINGS_FILE)
        st.rerun()

st.title("💰 ניהול תזרים מזומנים (כולל תמיכה במט\"ח)")

bank_up = st.file_uploader("העלה קובץ עו\"ש (CSV)", type="csv")
credit_up = st.file_uploader("העלה קובץ אשראי (CSV)", type="csv")

if bank_up and credit_up:
    settings = load_settings()
    
    # --- עיבוד בנק ---
    df_bank = pd.read_csv(bank_up, skiprows=7)
    df_bank['תאריך'] = pd.to_datetime(df_bank['תאריך'], dayfirst=True, errors='coerce')
    df_bank['סכום'] = df_bank['₪ זכות/חובה '].apply(clean_amount)
    df_bank = df_bank.dropna(subset=['תאריך']).rename(columns={'תיאור התנועה': 'מקור התנועה'})
    df_bank['Month'] = df_bank['תאריך'].dt.to_period('M')
    
    # --- עיבוד אשראי (טיפול חכם בעסקאות מט"ח) ---
    df_c_raw = pd.read_csv(credit_up, skiprows=8)
    
    # במידה ו"סכום חיוב" ריק (קורה בעסקאות חו"ל), ננסה לקחת מעמודות אחרות
    if 'סכום חיוב' in df_c_raw.columns:
        df_c_raw['סכום'] = df_c_raw['סכום חיוב'].apply(clean_amount)
    elif 'סכום החיוב' in df_c_raw.columns:
        df_c_raw['סכום'] = df_c_raw['סכום החיוב'].apply(clean_amount)
    
    # תיקון למקרים בהם הסכום התפספס בגלל מט"ח (עמודת "סכום מקורי" או ערכים אפסיים)
    df_c_raw.loc[df_c_raw['סכום'] == 0, 'סכום'] = df_c_raw.get('סכום מקורי', pd.Series([0]*len(df_c_raw))).apply(clean_amount)

    df_c_raw['תאריך עסקה'] = pd.to_datetime(df_c_raw['תאריך עסקה'], dayfirst=True, errors='coerce')
    df_c_raw['Month'] = df_c_raw['תאריך עסקה'].dt.to_period('M')
    df_c_raw = df_c_raw.dropna(subset=['תאריך עסקה'])

    # --- ממשק סיווג ---
    available_months = sorted([m for m in df_bank['Month'].unique() if m < pd.Timestamp.now().to_period('M')], reverse=True)
    selected_month = st.selectbox("בחר חודש לעבודה:", available_months)

    st.subheader(f"💳 סיווג אשראי - {selected_month} (כולל עסקאות חו\"ל)")
    
    df_c_m = df_c_raw[df_c_raw['Month'] == selected_month].groupby('בית עסק')['סכום'].sum().reset_index()
    df_c_m['קטגוריה'] = df_c_m['בית עסק'].apply(lambda x: get_initial_category(x, settings))
    df_c_m.insert(0, "תזרימי?", ~df_c_m['בית עסק'].isin(settings['excluded_credit']))
    
    ed_credit = st.data_editor(
        df_c_m, 
        hide_index=True, 
        key=f"credit_{selected_month}",
        column_config={
            "סכום": st.column_config.NumberColumn("סכום", format="₪%.2f"),
            "קטגוריה": st.column_config.SelectboxColumn("קטגוריה", options=CATEGORIES)
        }
    )

    if st.button("💾 שמור הגדרות"):
        # עדכון קטגוריות והחרגות
        for _, row in ed_credit.iterrows():
            settings['credit_categories'][row['בית עסק']] = row['קטגוריה']
            if not row['תזרימי?']:
                if row['בית עסק'] not in settings['excluded_credit']: settings['excluded_credit'].append(row['בית עסק'])
            elif row['בית עסק'] in settings['excluded_credit']: settings['excluded_credit'].remove(row['בית עסק'])
        save_settings(settings)
        st.success("נשמר!")
        st.rerun()

    # --- סיכום סופי ---
    st.divider()
    df_c_final = df_c_raw[~df_c_raw['בית עסק'].isin(settings['excluded_credit'])].copy()
    
    summary = pd.DataFrame({
        'הכנסות': df_bank[df_bank['סכום'] > 0].groupby('Month')['סכום'].sum(),
        'הוצאות': (df_bank[df_bank['סכום'] < 0].groupby('Month')['סכום'].sum().abs() + 
                   df_c_final.groupby('Month')['סכום'].sum())
    }).fillna(0)
    
    st.subheader("📊 תזרים סופי")
    st.table(summary.sort_index(ascending=False).style.format("₪{:,.2f}"))
