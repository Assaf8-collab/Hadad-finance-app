import streamlit as st
import pandas as pd
import json
import os

# --- 1. ניהול הגדרות וזיכרון ---
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
}

def get_category(description):
    if pd.isna(description): return 'אחר'
    desc = str(description).lower()
    for cat, keys in CATEGORY_MAP.items():
        if any(k in desc for k in keys): return cat
    return 'אחר'

def clean_amount(v):
    if pd.isna(v) or v == 'תיאור התנועה': return 0.0
    try:
        return float(str(v).replace('₪', '').replace(',', '').strip())
    except:
        return 0.0

# --- 3. ממשק משתמש ---
st.set_page_config(page_title="ניהול תקציב משפחתי", layout="wide")
st.title("💰 ניהול תזרים מזומנים חכם")

bank_up = st.file_uploader("העלה קובץ עו\"ש (CSV)", type="csv")
credit_up = st.file_uploader("העלה קובץ אשראי (CSV)", type="csv")

if bank_up and credit_up:
    settings = load_settings()
    prev_inc = settings.get("approved_income", [])
    prev_exp = settings.get("approved_expenses", [])

    # עיבוד בנק
    df_bank = pd.read_csv(bank_up, skiprows=7)
    df_bank['תאריך'] = pd.to_datetime(df_bank['תאריך'], dayfirst=True, errors='coerce')
    df_bank['סכום'] = df_bank['₪ זכות/חובה '].apply(clean_amount)
    df_bank = df_bank.dropna(subset=['תאריך']).rename(columns={'תיאור התנועה': 'מקור התנועה'})
    df_bank['Month'] = df_bank['תאריך'].dt.to_period('M')
    
    credit_keywords = ['כ.א.ל', 'מקס', 'ישראכרט', 'חיוב לכרטיס', 'ויזה']
    df_inc_raw = df_bank[df_bank['סכום'] > 0].copy()
    df_bank_exp_raw = df_bank[(df_bank['סכום'] < 0) & (~df_bank['מקור התנועה'].str.contains('|'.join(credit_keywords), na=False))].copy()

    # --- חלוקה לטאבים למיון לפי חודש ---
    st.divider()
    st.subheader("🛠️ מיון וסיווג תנועות")
    
    # נמצא את החודשים הקיימים בקובץ (שלמים בלבד)
    current_month = pd.Timestamp.now().to_period('M')
    available_months = sorted([m for m in df_bank['Month'].unique() if m < current_month], reverse=True)
    
    selected_month = st.selectbox("בחר חודש לסינון תנועות:", available_months)
    
    col_inc, col_exp = st.columns(2)
    
    with col_inc:
        st.write(f"**הכנסות - {selected_month}**")
        month_inc = df_inc_raw[df_inc_raw['Month'] == selected_month].groupby('מקור התנועה')['סכום'].sum().reset_index()
        month_inc.insert(0, "אישור", month_inc['מקור התנועה'].apply(lambda x: x in prev_inc if prev_inc else True))
        ed_inc = st.data_editor(month_inc, hide_index=True, key=f"inc_{selected_month}", column_config={"מקור התנועה": st.column_config.TextColumn(width="large")})

    with col_exp:
        st.write(f"**הוצאות עו\"ש - {selected_month}**")
        month_exp = df_bank_exp_raw[df_bank_exp_raw['Month'] == selected_month].groupby('מקור התנועה')['סכום'].sum().abs().reset_index()
        month_exp.insert(0, "אישור", month_exp['מקור התנועה'].apply(lambda x: x in prev_exp if prev_exp else True))
        ed_exp = st.data_editor(month_exp, hide_index=True, key=f"exp_{selected_month}", column_config={"מקור התנועה": st.column_config.TextColumn(width="large")})

    if st.button("💾 שמור הגדרות (המערכת תזכור תיאורים אלו לעתיד)"):
        # עדכון הרשימה הכללית בזיכרון (מוסיף חדשים ושומר קיימים)
        new_inc = set(prev_inc) | set(ed_inc[ed_inc["אישור"] == True]['מקור התנועה'])
        new_inc = new_inc - set(ed_inc[ed_inc["אישור"] == False]['מקור התנועה'])
        
        new_exp = set(prev_exp) | set(ed_exp[ed_exp["אישור"] == True]['מקור התנועה'])
        new_exp = new_exp - set(ed_exp[ed_exp["אישור"] == False]['מקור התנועה'])
        
        save_settings(list(new_inc), list(new_exp))
        st.success("ההגדרות נשמרו! בחודש הבא תנועות אלו יסווגו אוטומטית.")

    # --- סיכום תזרימי ---
    # כאן אנחנו משתמשים בזיכרון המעודכן כדי לסנן את כל החודשים
    final_settings = load_settings()
    df_inc_f = df_inc_raw[df_inc_raw['מקור התנועה'].isin(final_settings['approved_income'])]
    df_exp_f = df_bank_exp_raw[df_bank_exp_raw['מקור התנועה'].isin(final_settings['approved_expenses'])]

    # עיבוד אשראי
    df_c = pd.read_csv(credit_up, skiprows=8)
    df_c['סכום'] = df_c['סכום החיוב'].apply(clean_amount)
    df_c['תאריך עסקה'] = pd.to_datetime(df_c['תאריך עסקה'], dayfirst=True, errors='coerce')
    df_c['Month'] = df_c['תאריך עסקה'].dt.to_period('M')
    df_c['קטגוריה'] = df_c['בית עסק'].apply(get_category)

    summary = pd.DataFrame({
        'הכנסות': df_inc_f.groupby('Month')['סכום'].sum(),
        'הוצאות בנק': df_exp_f.groupby('Month')['סכום'].sum().abs(),
        'הוצאות אשראי': df_c.groupby('Month')['סכום'].sum()
    }).fillna(0)
    
    summary = summary[summary.index < current_month]
    if not summary.empty:
        summary['סה"כ הוצאות'] = summary['הוצאות בנק'] + summary['הוצאות אשראי']
        summary['נטו'] = summary['הכנסות'] - summary['סה"כ הוצאות']
        st.divider()
        st.subheader("📊 טבלת תזרים מזומנים סופית")
        st.table(summary.sort_index(ascending=False).style.format("₪{:,.2f}"))
        
