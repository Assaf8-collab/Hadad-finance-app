import streamlit as st
import pandas as pd
import json
import os

# --- 1. ניהול הגדרות וזיכרון ---
SETTINGS_FILE = 'app_settings.json'

def load_settings():
    default = {"approved_income": None, "approved_expenses": None} # None מסמן שמעולם לא נשמרו הגדרות
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default
    return default

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
    'חסכון והשקעות': ['הפקדה', 'חסכון', 'ניירות ערך', 'קופת גמל', 'פנסיה', 'השתלמות', 'פקדון'],
    'מגורים ואחזקה': ['ארנונה', 'חשמל', 'ועד בית', 'מי שבע'],
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
        # טיפול במחרוזות שכוללות סימני מטבע ופסיקים
        s = str(v).replace('₪', '').replace(',', '').strip()
        return float(s)
    except:
        return 0.0

# --- 3. ממשק משתמש ---
st.set_page_config(page_title="ניהול תקציב משפחתי", layout="wide")

# סרגל צידי לאיפוס
with st.sidebar:
    st.header("⚙️ הגדרות")
    if st.button("🗑️ איפוס כל ההגדרות"):
        if os.path.exists(SETTINGS_FILE):
            os.remove(SETTINGS_FILE)
            st.success("ההגדרות נמחקו. טוען מחדש...")
            st.rerun()
    st.info("איפוס יחזיר את כל התנועות לתצוגה וימחק את הזיכרון של מה שסימנת בעבר.")

st.title("💰 ניהול תזרים מזומנים חכם")

bank_up = st.file_uploader("העלה קובץ עו\"ש (CSV)", type="csv")
credit_up = st.file_uploader("העלה קובץ אשראי (CSV)", type="csv")

if bank_up and credit_up:
    settings = load_settings()
    # אם settings['approved_income'] הוא None, זה אומר שזו הרצה ראשונה או אחרי איפוס
    saved_inc = settings.get("approved_income")
    saved_exp = settings.get("approved_expenses")

    # עיבוד בנק
    df_bank = pd.read_csv(bank_up, skiprows=7)
    df_bank['תאריך'] = pd.to_datetime(df_bank['תאריך'], dayfirst=True, errors='coerce')
    # שימוש בשם העמודה המדויק עם הרווח בסוף
    df_bank['סכום'] = df_bank['₪ זכות/חובה '].apply(clean_amount)
    df_bank = df_bank.dropna(subset=['תאריך']).rename(columns={'תיאור התנועה': 'מקור התנועה'})
    df_bank['Month'] = df_bank['תאריך'].dt.to_period('M')
    
    credit_keywords = ['כ.א.ל', 'מקס', 'ישראכרט', 'חיוב לכרטיס', 'ויזה']
    df_inc_raw = df_bank[df_bank['סכום'] > 0].copy()
    df_bank_exp_raw = df_bank[(df_bank['סכום'] < 0) & (~df_bank['מקור התנועה'].str.contains('|'.join(credit_keywords), na=False))].copy()

    # --- מיון וסיווג לפי חודש ---
    st.divider()
    st.subheader("🛠️ שלב 1: אישור תנועות עו\"ש")
    
    current_month = pd.Timestamp.now().to_period('M')
    available_months = sorted([m for m in df_bank['Month'].unique() if m < current_month], reverse=True)
    
    if available_months:
        selected_month = st.selectbox("בחר חודש לבדיקה:", available_months)
        col_inc, col_exp = st.columns(2)
        
        with col_inc:
            st.write(f"**הכנסות - {selected_month}**")
            m_inc = df_inc_raw[df_inc_raw['Month'] == selected_month].groupby('מקור התנועה')['סכום'].sum().reset_index()
            # לוגיקה: אם אין הגדרות - הכל True. אם יש - רק מה שברשימה True.
            m_inc.insert(0, "אישור", m_inc['מקור התנועה'].isin(saved_inc) if saved_inc is not None else True)
            ed_inc = st.data_editor(m_inc, hide_index=True, key=f"inc_{selected_month}", column_config={"מקור התנועה": st.column_config.TextColumn(width="large")})

        with col_exp:
            st.write(f"**הוצאות עו\"ש - {selected_month}**")
            m_exp = df_bank_exp_raw[df_bank_exp_raw['Month'] == selected_month].groupby('מקור התנועה')['סכום'].sum().abs().reset_index()
            m_exp.insert(0, "אישור", m_exp['מקור התנועה'].isin(saved_exp) if saved_exp is not None else True)
            ed_exp = st.data_editor(m_exp, hide_index=True, key=f"exp_{selected_month}", column_config={"מקור התנועה": st.column_config.TextColumn(width="large")})

        if st.button("💾 שמור בחירות"):
            # עדכון הזיכרון הכללי
            final_inc_list = ed_inc[ed_inc["אישור"] == True]['מקור התנועה'].tolist()
            final_exp_list = ed_exp[ed_exp["אישור"] == True]['מקור התנועה'].tolist()
            save_settings(final_inc_list, final_exp_list)
            st.success("ההגדרות נשמרו!")
            st.rerun()

    # --- סיכום תזרימי סופי ---
    updated_settings = load_settings()
    
    # סינון: אם מעולם לא נשמרו הגדרות, אל תסנן כלום (הצג הכל). אם נשמרו - סנן לפיהן.
    if updated_settings['approved_income'] is not None:
        df_inc_f = df_inc_raw[df_inc_raw['מקור התנועה'].isin(updated_settings['approved_income'])]
    else:
        df_inc_f = df_inc_raw

    if updated_settings['approved_expenses'] is not None:
        df_exp_f = df_bank_exp_raw[df_bank_exp_raw['מקור התנועה'].isin(updated_settings['approved_expenses'])]
    else:
        df_exp_f = df_bank_exp_raw

    # עיבוד אשראי
    df_c = pd.read_csv(credit_up, skiprows=8)
    df_c['סכום'] = df_c['סכום החיוב'].apply(clean_amount)
    df_c['תאריך עסקה'] = pd.to_datetime(df_c['תאריך עסקה'], dayfirst=True, errors='coerce')
    df_c['Month'] = df_c['תאריך עסקה'].dt.to_period('M')
    df_c['קטגוריה'] = df_c['בית עסק'].apply(get_category)

    summary = pd.DataFrame({
        'הכנסות': df_inc_f.groupby('Month')['סכום'].sum(),
        # סינון סופי של הוצאות בנק והוספת קטגוריות
        final_settings = load_settings()
        approved_exp_names = final_settings.get('approved_expenses', [])
    
        if approved_exp_names:
            df_exp_f = df_bank_exp_raw[df_bank_exp_raw['מקור התנועה'].isin(approved_exp_names)].copy()
        else:
            df_exp_f = df_bank_exp_raw.copy()
        
        # הוספת קטגוריה גם להוצאות הבנק
        df_exp_f['קטגוריה'] = df_exp_f['מקור התנועה'].apply(get_category)
        'הוצאות אשראי': df_c.groupby('Month')['סכום'].sum()
    }).fillna(0)
    
    summary = summary[summary.index < current_month]
    if not summary.empty:
        summary['סה"כ הוצאות'] = summary['הוצאות בנק'] + summary['הוצאות אשראי']
        summary['נטו'] = summary['הכנסות'] - summary['סה"כ הוצאות']
        st.divider()
        st.subheader("📊 סיכום תזרים מזומנים סופי")
        st.table(summary.sort_index(ascending=False).style.format("₪{:,.2f}"))

# איחוד כל ההוצאות לצורך ניתוח קטגוריות
    all_expenses = pd.concat([
        df_c[['Month', 'קטגוריה', 'סכום']],
        df_exp_f[['Month', 'קטגוריה', 'סכום']]
    ])
    
    # הצגת ניתוח קטגוריות לחודש האחרון
    last_m = summary.index[0]
    st.divider()
    st.subheader(f"📊 לאן הלך הכסף בחודש {last_m}?")
    
    cat_analysis = all_expenses[all_expenses['Month'] == last_m].groupby('קטגוריה')['סכום'].sum().sort_values(ascending=False)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.bar_chart(cat_analysis)
    with col2:
        # הדגשת החסכון
        if 'חסכון והשקעות' in cat_analysis:
            saving_amount = cat_analysis['חסכון והשקעות']
            st.metric("סכום שנחסך החודש", f"₪{saving_amount:,.0f}")
        st.write(cat_analysis.map("₪{:,.2f}".format))
