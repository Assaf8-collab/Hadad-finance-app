import streamlit as st
import pandas as pd
import json
import os

# --- 1. ניהול הגדרות וזיכרון (JSON) ---
SETTINGS_FILE = 'app_settings.json'

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"approved_income": [], "approved_expenses": []}
    return {"approved_income": [], "approved_expenses": []}

def save_settings(income_list, expense_list):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            "approved_income": income_list,
            "approved_expenses": expense_list
        }, f, ensure_ascii=False, indent=4)

# --- 2. פונקציות עזר ---
CATEGORY_MAP = {
    'מזון וסופר': ['שופרסל', 'הכל כאן', 'יוחננוף', 'קשת טעמים', 'רמי לוי', 'מאפיית'],
    'חינוך וחוגים': ['נוקדים', 'מוסדות חינוך', 'עירייה', 'מתנ"ס'],
    'תחבורה ורכב': ['פנגו', 'פז', 'סונול', 'דור אלון', 'חניון'],
    'פנאי ומסעדות': ['קורטושוק', 'מסעדה', 'קפה', 'וולט', 'WOLT'],
    'בריאות': ['סופר פארם', 'מכבי', 'כללית', 'בית מרקחת'],
}

def get_category(description):
    if pd.isna(description) or description == "": return 'אחר'
    description = str(description).lower()
    for category, keywords in CATEGORY_MAP.items():
        for key in keywords:
            if key in description: return category
    return 'אחר'

def clean_amount(value):
    if pd.isna(value) or value == 'תיאור התנועה': return 0.0
    if isinstance(value, str):
        value = value.replace('₪', '').replace(',', '').replace(' ', '')
    try:
        return float(value)
    except:
        return 0.0

# --- 3. ממשק משתמש ---
st.set_page_config(page_title="ניהול תקציב משפחתי", layout="wide")
st.title("💰 ניהול תזרים מזומנים חכם")

bank_up = st.file_uploader("העלה קובץ עו\"ש (CSV)", type="csv")
credit_up = st.file_uploader("העלה קובץ אשראי (CSV)", type="csv")

if bank_up and credit_up:
    # טעינת הגדרות
    settings = load_settings()
    prev_inc = settings.get("approved_income", [])
    prev_exp = settings.get("approved_expenses", [])

    # עיבוד ראשוני בנק
    df_bank = pd.read_csv(bank_up, skiprows=7)
    df_bank['תאריך'] = pd.to_datetime(df_bank['תאריך'], dayfirst=True, errors='coerce')
    df_bank['סכום'] = df_bank['₪ זכות/חובה '].apply(clean_amount)
    df_bank = df_bank.dropna(subset=['תאריך']).rename(columns={'תיאור התנועה': 'מקור התנועה'})
    df_bank['Month'] = df_bank['תאריך'].dt.to_period('M')
    
    # הפרדה להכנסות והוצאות בנק (ללא אשראי)
    credit_keywords = ['כ.א.ל', 'מקס', 'ישראכרט', 'חיוב לכרטיס', 'ויזה']
    df_inc_raw = df_bank[df_bank['סכום'] > 0].copy()
    df_bank_exp_raw = df_bank[(df_bank['סכום'] < 0) & (~df_bank['מקור התנועה'].str.contains('|'.join(credit_keywords), na=False))].copy()

    # --- א. ניהול הכנסות ---
    st.subheader("🏦 שלב 1: אישור הכנסות")
    inc_opt = df_inc_raw.groupby('מקור התנועה')['סכום'].agg(['sum', 'count']).reset_index()
    inc_opt.columns = ['מקור התנועה', 'סה"כ', 'פעמים']
    inc_opt.insert(0, "אישור", inc_opt['מקור התנועה'].isin(prev_inc) if prev_inc else True)
    
    ed_inc = st.data_editor(inc_opt, column_config={"מקור התנועה": st.column_config.TextColumn(width="large")}, hide_index=True, key="ed_inc")

    # --- ב. ניהול הוצאות בנק ---
    st.subheader("💸 שלב 2: אישור הוצאות עו\"ש (ללא אשראי)")
    exp_opt = df_bank_exp_raw.groupby('מקור התנועה')['סכום'].agg(['sum', 'count']).reset_index()
    exp_opt.columns = ['מקור התנועה', 'סה"כ', 'פעמים']
    exp_opt['סה"כ'] = exp_opt['סה"כ'].abs()
    exp_opt.insert(0, "אישור", exp_opt['מקור התנועה'].isin(prev_exp) if prev_exp else True)

    ed_exp = st.data_editor(exp_opt, column_config={"מקור התנועה": st.column_config.TextColumn(width="large")}, hide_index=True, key="ed_exp")

    if st.button("💾 שמור את כל הבחירות לחודש הבא"):
        list_inc = ed_inc[ed_inc["אישור"] == True]['מקור התנועה'].tolist()
        list_exp = ed_exp[ed_exp["אישור"] == True]['מקור התנועה'].tolist()
        save_settings(list_inc, list_exp)
        st.success("ההגדרות נשמרו!")

    # סינון סופי
    df_inc_f = df_inc_raw[df_inc_raw['מקור התנועה'].isin(ed_inc[ed_inc["אישור"] == True]['מקור התנועה'])]
    df_exp_f = df_bank_exp_raw[df_bank_exp_raw['מקור התנועה'].isin(ed_exp[ed_exp["אישור"] == True]['מקור התנועה'])]

    # עיבוד אשראי
    df_c = pd.read_csv(credit_up, skiprows=8)
    df_c['סכום'] = df_c['סכום החיוב'].apply(clean_amount)
    df_c['תאריך עסקה'] = pd.to_datetime(df_c['תאריך עסקה'], dayfirst=True, errors='coerce')
    df_c['Month'] = df_c['תאריך עסקה'].dt.to_period('M')
    df_c['קטגוריה'] = df_c['בית עסק'].apply(get_category)

    # --- ג. סיכום תזרימי ---
    summary = pd.DataFrame({
        'הכנסות': df_inc_f.groupby('Month')['סכום'].sum(),
        'הוצאות בנק': df_exp_f.groupby('Month')['סכום'].sum().abs(),
        'הוצאות אשראי': df_c.groupby('Month')['סכום'].sum()
    }).fillna(0)
    
    current_month = pd.Timestamp.now().to_period('M')
    summary = summary[summary.index < current_month]
    
    if not summary.empty:
        summary['סה"כ הוצאות'] = summary['הוצאות בנק'] + summary['הוצאות אשראי']
        summary['נטו'] = summary['הכנסות'] - summary['סה"כ הוצאות']
        
        st.divider()
        st.subheader("📊 סיכום תזרים מזומנים חודשי")
        st.table(summary.sort_index(ascending=False).style.format("₪{:,.2f}"))
        
        # גרף התפלגות אשראי חודש אחרון
        last_m = summary.index[0]
        st.subheader(f"🔍 ניתוח אשראי - {last_m}")
        cat_sum = df_c[df_c['Month'] == last_m].groupby('קטגוריה')['סכום'].sum().sort_values(ascending=False)
        st.bar_chart(cat_sum)
