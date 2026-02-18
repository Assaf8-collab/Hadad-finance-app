import streamlit as st
import pandas as pd
import json
import os

# --- 1. ניהול הגדרות וזיכרון (JSON) ---
SETTINGS_FILE = 'app_settings.json'

def load_settings():
    default = {"approved_income": [], "approved_expenses": []}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # וידוא שכל המפתחות קיימים (למניעת KeyError)
                for key in default:
                    if key not in data: data[key] = []
                return data
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
    # שימוש ב-.get למניעת KeyError
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

    # --- מיון וסיווג לפי חודש ---
    st.divider()
    st.subheader("🛠️ מיון וסיווג תנועות")
    
    current_month = pd.Timestamp.now().to_period('M')
    available_months = sorted([m for m in df_bank['Month'].unique() if m < current_month], reverse=True)
    
    if available_months:
        selected_month = st.selectbox("בחר חודש לסינון תנועות:", available_months)
        
        col_inc, col_exp = st.columns(2)
        
        with col_inc:
            st.write(f"**הכנסות - {selected_month}**")
            m_inc = df_inc_raw[df_inc_raw['Month'] == selected_month].groupby('מקור התנועה')['סכום'].sum().reset_index()
            # סימון אוטומטי של מה שנשמר בעבר
            m_inc.insert(0, "אישור", m_inc['מקור התנועה'].isin(prev_inc))
            ed_inc = st.data_editor(m_inc, hide_index=True, key=f"inc_{selected_month}", column_config={"מקור התנועה": st.column_config.TextColumn(width="large")})

        with col_exp:
            st.write(f"**הוצאות עו\"ש - {selected_month}**")
            m_exp = df_bank_exp_raw[df_bank_exp_raw['Month'] == selected_month].groupby('מקור התנועה')['סכום'].sum().abs().reset_index()
            m_exp.insert(0, "אישור", m_exp['מקור התנועה'].isin(prev_exp))
            ed_exp = st.data_editor(m_exp, hide_index=True, key=f"exp_{selected_month}", column_config={"מקור התנועה": st.column_config.TextColumn(width="large")})

        if st.button("💾 שמור הגדרות (המערכת תזכור תיאורים אלו לעתיד)"):
            # לוגיקה לעדכון הזיכרון הכללי
            all_inc_in_editor = set(ed_inc['מקור התנועה'])
            current_approved_inc = set(ed_inc[ed_inc["אישור"] == True]['מקור התנועה'])
            
            all_exp_in_editor = set(ed_exp['מקור התנועה'])
            current_approved_exp = set(ed_exp[ed_exp["אישור"] == True]['מקור התנועה'])
            
            # מעדכנים את הזיכרון הקיים: מוסיפים מאושרים חדשים ומסירים כאלו שבוטלו בטבלה
            final_inc = (set(prev_inc) - all_inc_in_editor) | current_approved_inc
            final_exp = (set(prev_exp) - all_exp_in_editor) | current_approved_exp
            
            save_settings(list(final_inc), list(final_exp))
            st.success("ההגדרות נשמרו!")
            st.rerun() # מרענן את הדף כדי לעדכן את הטבלאות למטה

    # --- סיכום תזרימי ---
    updated_settings = load_settings()
    df_inc_f = df_inc_raw[df_inc_raw['מקור התנועה'].isin(updated_settings['approved_income'])]
    df_exp_f = df_bank_exp_raw[df_bank_exp_raw['מקור התנועה'].isin(updated_settings['approved_expenses'])]

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
        st.subheader("📊 סיכום תזרים מזומנים (חודשים מלאים)")
        st.table(summary.sort_index(ascending=False).style.format("₪{:,.2f}"))
        
        # ניתוח קטגוריות חודש אחרון
        last_m = summary.index[0]
        st.subheader(f"🔍 ניתוח אשראי - {last_m}")
        cat_sum = df_c[df_c['Month'] == last_m].groupby('קטגוריה')['סכום'].sum().sort_values(ascending=False)
        st.bar_chart(cat_sum)
