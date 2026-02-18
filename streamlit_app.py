import streamlit as st
import pandas as pd
import json
import os

# --- 1. ניהול הגדרות וזיכרון (JSON) ---
SETTINGS_FILE = 'app_settings.json'

def load_settings():
    default = {
        "approved_income": [], 
        "approved_expenses": [], 
        "savings_list": [],
        "credit_categories": {}, # זוכר: {'בית עסק': 'קטגוריה'}
        "excluded_credit": []    # זוכר בתי עסק שהוחרגו מהתזרים
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for key in default:
                    if key not in data: data[key] = default[key]
                return data
        except:
            return default
    return default

def save_settings(settings_dict):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings_dict, f, ensure_ascii=False, indent=4)

# --- 2. פונקציות עזר וסיווג ---
CATEGORIES = ['אחר', 'קניות סופר', 'רכב', 'ביטוח', 'ביגוד', 'אוכל בחוץ', 'בילויים', 'חסכון והשקעות']

CATEGORY_MAP = {
    'קניות סופר': ['שופרסל', 'הכל כאן', 'יוחננוף', 'קשת טעמים', 'רמי לוי', 'ויקטורי', 'מחסני השוק'],
    'אוכל בחוץ': ['מסעדה', 'קפה', 'וולט', 'WOLT', 'מקדונלד', 'פיצה'],
    'רכב': ['פנגו', 'פז', 'סונול', 'דור אלון', 'חניון', 'דלק'],
    'בילויים': ['קורטושוק', 'קולנוע', 'מוזיאון', 'תיאטרון'],
    'ביגוד': ['זארה', 'ZARA', 'H&M', 'טרמינל', 'TERMINAL', 'גולף', 'דלתא'],
}

def get_initial_category(description, settings):
    desc = str(description)
    # 1. בדיקה בזיכרון משתמש
    if desc in settings['credit_categories']:
        return settings['credit_categories'][desc]
    # 2. בדיקה במילון אוטומטי
    desc_lower = desc.lower()
    for cat, keys in CATEGORY_MAP.items():
        if any(k in desc_lower for k in keys): return cat
    return 'אחר'

def clean_amount(v):
    if pd.isna(v) or v == 'תיאור התנועה': return 0.0
    try:
        return float(str(v).replace('₪', '').replace(',', '').strip())
    except:
        return 0.0

# --- 3. ממשק משתמש ---
st.set_page_config(page_title="ניהול תקציב משפחתי", layout="wide")

with st.sidebar:
    st.header("⚙️ הגדרות")
    if st.button("🗑️ איפוס כל ההגדרות"):
        if os.path.exists(SETTINGS_FILE):
            os.remove(SETTINGS_FILE)
            st.rerun()

st.title("💰 ניהול תזרים מזומנים חכם")

bank_up = st.file_uploader("העלה קובץ עו\"ש (CSV)", type="csv")
credit_up = st.file_uploader("העלה קובץ אשראי (CSV)", type="csv")

if bank_up and credit_up:
    settings = load_settings()
    
    # --- עיבוד בסיסי ---
    df_bank = pd.read_csv(bank_up, skiprows=7)
    df_bank['תאריך'] = pd.to_datetime(df_bank['תאריך'], dayfirst=True, errors='coerce')
    df_bank['סכום'] = df_bank['₪ זכות/חובה '].apply(clean_amount)
    df_bank = df_bank.dropna(subset=['תאריך']).rename(columns={'תיאור התנועה': 'מקור התנועה'})
    df_bank['Month'] = df_bank['תאריך'].dt.to_period('M')
    
    credit_keywords = ['כ.א.ל', 'מקס', 'ישראכרט', 'חיוב לכרטיס', 'ויזה']
    df_inc_raw = df_bank[df_bank['סכום'] > 0].copy()
    df_bank_exp_raw = df_bank[(df_bank['סכום'] < 0) & (~df_bank['מקור התנועה'].str.contains('|'.join(credit_keywords), na=False))].copy()

    df_c_raw = pd.read_csv(credit_up, skiprows=8)
    df_c_raw['סכום'] = df_c_raw['סכום החיוב'].apply(clean_amount)
    df_c_raw['תאריך עסקה'] = pd.to_datetime(df_c_raw['תאריך עסקה'], dayfirst=True, errors='coerce')
    df_c_raw['Month'] = df_c_raw['תאריך עסקה'].dt.to_period('M')
    df_c_raw = df_c_raw.dropna(subset=['תאריך עסקה'])

    # --- שלב 1: מיון עו"ש ---
    st.divider()
    available_months = sorted([m for m in df_bank['Month'].unique() if m < pd.Timestamp.now().to_period('M')], reverse=True)
    selected_month = st.selectbox("בחר חודש לעבודה:", available_months)

    st.subheader(f"🛠️ שלב 1: סיווג עו\"ש - {selected_month}")
    col_inc, col_exp = st.columns(2)
    
    with col_inc:
        m_inc = df_inc_raw[df_inc_raw['Month'] == selected_month].groupby('מקור התנועה')['סכום'].sum().reset_index()
        m_inc.insert(0, "אישור", m_inc['מקור התנועה'].isin(settings['approved_income']) if settings['approved_income'] else True)
        ed_inc = st.data_editor(m_inc, hide_index=True, key=f"inc_{selected_month}")

    with col_exp:
        m_exp = df_bank_exp_raw[df_bank_exp_raw['Month'] == selected_month].groupby('מקור התנועה')['סכום'].sum().abs().reset_index()
        m_exp.insert(0, "חסכון?", m_exp['מקור התנועה'].isin(settings['savings_list']))
        m_exp.insert(0, "אישור", m_exp['מקור התנועה'].isin(settings['approved_expenses']) if settings['approved_expenses'] else True)
        ed_exp = st.data_editor(m_exp, hide_index=True, key=f"exp_{selected_month}")

    # --- שלב 2: סיווג אשראי ---
    st.divider()
    st.subheader(f"💳 שלב 2: סיווג הוצאות אשראי - {selected_month}")
    
    df_c_m = df_c_raw[df_c_raw['Month'] == selected_month].groupby('בית עסק')['סכום'].sum().reset_index()
    df_c_m['קטגוריה'] = df_c_m['בית עסק'].apply(lambda x: get_initial_category(x, settings))
    df_c_m.insert(0, "תזרימי?", ~df_c_m['בית עסק'].isin(settings['excluded_credit']))
    
    ed_credit = st.data_editor(
        df_c_m, 
        hide_index=True, 
        key=f"credit_{selected_month}",
        column_config={
            "קטגוריה": st.column_config.SelectboxColumn("קטגוריה", options=CATEGORIES, width="medium"),
            "תזרימי?": st.column_config.CheckboxColumn("תזרימי?", help="הסר סימון להוצאה חד פעמית/לא תזרימית")
        }
    )

    if st.button("💾 שמור הגדרות חודש " + str(selected_month)):
        # עדכון הגדרות עו"ש
        settings['approved_income'] = list((set(settings['approved_income']) - set(m_inc['מקור התנועה'])) | set(ed_inc[ed_inc["אישור"]]['מקור התנועה']))
        settings['approved_expenses'] = list((set(settings['approved_expenses']) - set(m_exp['מקור התנועה'])) | set(ed_exp[ed_exp["אישור"]]['מקור התנועה']))
        settings['savings_list'] = list((set(settings['savings_list']) - set(m_exp['מקור התנועה'])) | set(ed_exp[ed_exp["חסכון?"]]['מקור התנועה']))
        
        # עדכון הגדרות אשראי (רק מה ששונה ידנית)
        for _, row in ed_credit.iterrows():
            settings['credit_categories'][row['בית עסק']] = row['קטגוריה']
            if not row['תזרימי?']:
                if row['בית עסק'] not in settings['excluded_credit']:
                    settings['excluded_credit'].append(row['בית עסק'])
            else:
                if row['בית עסק'] in settings['excluded_credit']:
                    settings['excluded_credit'].remove(row['בית עסק'])
        
        save_settings(settings)
        st.success("ההגדרות נשמרו בהצלחה!")
        st.rerun()

    # --- שלב 3: סיכום תזרים סופי ---
    st.divider()
    st.subheader("📊 שלב 3: סיכום תזרים וניתוח")

    # סינון תנועות לפי האישורים
    final_inc = df_inc_raw[df_inc_raw['מקור התנועה'].isin(settings['approved_income'])]
    final_bank_exp = df_bank_exp_raw[df_bank_exp_raw['מקור התנועה'].isin(settings['approved_expenses'])]
    
    # סינון אשראי - רק מה שתזרימי
    df_c_final = df_c_raw[~df_c_raw['בית עסק'].isin(settings['excluded_credit'])].copy()
    df_c_final['קטגוריה'] = df_c_final['בית עסק'].apply(lambda x: settings['credit_categories'].get(x, get_initial_category(x, settings)))

    summary = pd.DataFrame({
        'הכנסות': final_inc.groupby('Month')['סכום'].sum(),
        'הוצאות בנק': final_bank_exp.groupby('Month')['סכום'].sum().abs(),
        'הוצאות אשראי': df_c_final.groupby('Month')['סכום'].sum()
    }).fillna(0)
    
    summary = summary[summary.index < pd.Timestamp.now().to_period('M')]
    
    if not summary.empty:
        summary['סה"כ הוצאות'] = summary['הוצאות בנק'] + summary['הוצאות אשראי']
        summary['נטו'] = summary['הכנסות'] - summary['סה"כ הוצאות']
        st.table(summary.sort_index(ascending=False).style.format("₪{:,.2f}"))

        # ניתוח "לאן הולך הכסף" (מאוחד)
        all_exp_combined = pd.concat([
            df_c_final[df_c_final['Month'] == selected_month][['קטגוריה', 'סכום']],
            final_bank_exp[final_bank_exp['Month'] == selected_month].assign(קטגוריה=lambda x: x['מקור התנועה'].apply(lambda y: 'חסכון והשקעות' if y in settings['savings_list'] else 'אחר'))[['קטגוריה', 'סכום']]
        ])
        
        cat_sum = all_exp_combined.groupby('קטגוריה')['סכום'].sum().sort_values(ascending=False)
        c1, c2 = st.columns([2, 1])
        with c1: st.bar_chart(cat_sum)
        with c2: st.write(cat_sum.map("₪{:,.2f}".format))
            
