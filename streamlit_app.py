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
            return {"approved_sources": []}
    return {"approved_sources": []}

def save_settings(approved_list):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump({"approved_sources": approved_list}, f, ensure_ascii=False, indent=4)

# --- 2. פונקציות עזר לעיבוד ---
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

# --- 3. ממשק משתמש (Streamlit) ---
st.set_page_config(page_title="ניהול תקציב - משפחת חדד", layout="wide")
st.title("💰 תזרים מזומנים וניהול הוצאות")

bank_up = st.file_uploader("העלה קובץ עו\"ש (CSV)", type="csv")
credit_up = st.file_uploader("העלה קובץ אשראי (CSV)", type="csv")

if bank_up and credit_up:
    # --- א. עיבוד נתונים ראשוני (עו"ש דיסקונט) ---
    df_bank = pd.read_csv(bank_up, skiprows=7)
    # שימוש בשמות העמודות המדויקים מהקובץ
    df_bank['תאריך'] = pd.to_datetime(df_bank['תאריך'], dayfirst=True, errors='coerce')
    df_bank['סכום'] = df_bank['₪ זכות/חובה '].apply(clean_amount)
    df_bank = df_bank.dropna(subset=['תאריך'])
    df_bank['Month'] = df_bank['תאריך'].dt.to_period('M')
    
    # שינוי שם העמודה כבר כאן כדי למנוע את ה-KeyError
    df_bank = df_bank.rename(columns={'תיאור התנועה': 'מקור התנועה'})
    
    df_inc_raw = df_bank[df_bank['סכום'] > 0].copy()
    
    # --- ב. ניהול הכנסות אינטראקטיבי ---
    st.divider()
    st.subheader("🏦 הגדרת מקורות הכנסה")
    st.info("סמן את מקורות ההכנסה התזרימיים (משכורת וכו'). תיאורים ארוכים לא ייחתכו.")

    settings = load_settings()
    previously_approved = settings.get("approved_sources", [])

    # הכנת טבלת אפשרויות לסימון
    income_options = df_inc_raw.groupby('מקור התנועה')['סכום'].agg(['sum', 'count']).reset_index()
    income_options.columns = ['מקור התנועה', 'סכום מצטבר', 'פעמים']
    
    # הוספת עמודת ה-Checkbox
    income_options.insert(0, "אישור", income_options['מקור התנועה'].isin(previously_approved))

    edited_income = st.data_editor(
        income_options,
        column_config={
            "אישור": st.column_config.CheckboxColumn("נכלל?", default=True),
            "מקור התנועה": st.column_config.TextColumn("תיאור מלא מהבנק", width="large"),
            "סכום מצטבר": st.column_config.NumberColumn("סה\"כ בקובץ", format="₪%.0f"),
        },
        disabled=['מקור התנועה', 'סכום מצטבר', 'פעמים'],
        hide_index=True,
        key="income_editor_v2"
    )

    if st.button("💾 שמור בחירות לחודש הבא"):
        new_approved = edited_income[edited_income["אישור"] == True]['מקור התנועה'].tolist()
        save_settings(new_approved)
        st.success("הבחירות נשמרו בהצלחה!")

    # סינון ההכנסות המאושרות (כאן נפתר ה-KeyError)
    approved_list = edited_income[edited_income["אישור"] == True]['מקור התנועה'].tolist()
    df_inc_filtered = df_inc_raw[df_inc_raw['מקור התנועה'].isin(approved_list)]

    # --- ג. עיבוד הוצאות (בנק ואשראי) ---
    credit_keywords = ['כ.א.ל', 'מקס', 'ישראכרט', 'חיוב לכרטיס', 'ויזה']
    df_bank_exp = df_bank[(df_bank['סכום'] < 0) & (~df_bank['מקור התנועה'].str.contains('|'.join(credit_keywords), na=False))].copy()
    df_bank_exp['סכום'] = df_bank_exp['סכום'].abs()

    df_credit = pd.read_csv(credit_up, skiprows=8)
    df_credit['תאריך עסקה'] = pd.to_datetime(df_credit['תאריך עסקה'], dayfirst=True, errors='coerce')
    df_credit['סכום'] = df_credit['סכום החיוב'].apply(clean_amount)
    df_credit = df_credit.dropna(subset=['תאריך עסקה'])
    df_credit['Month'] = df_credit['תאריך עסקה'].dt.to_period('M')
    df_credit['קטגוריה'] = df_credit['בית עסק'].apply(get_category)

    # --- ד. סיכום חודשי ותצוגה ---
    monthly_inc = df_inc_filtered.groupby('Month')['סכום'].sum()
    monthly_bank_exp = df_bank_exp.groupby('Month')['סכום'].sum()
    monthly_credit_exp = df_credit.groupby('Month')['סכום'].sum()
    
    summary = pd.DataFrame({
        'הכנסות': monthly_inc,
        'הוצאות בנק': monthly_bank_exp,
        'הוצאות אשראי': monthly_credit_exp
    }).fillna(0)
    
    current_month = pd.Timestamp.now().to_period('M')
    summary = summary[summary.index < current_month]
    
    if not summary.empty:
        summary['סה"כ הוצאות'] = summary['הוצאות בנק'] + summary['הוצאות אשראי']
        summary['נטו'] = summary['הכנסות'] - summary['סה"כ הוצאות']
        
        st.divider()
        st.subheader("📊 סיכום תזרימי (חודשים מלאים)")
        st.table(summary.sort_index(ascending=False).style.format("₪{:,.2f}"))
        
        # גרף מגמות
        st.line_chart(summary[['הכנסות', 'סה"כ הוצאות']])
        
        # ניתוח קטגוריות לחודש האחרון
        last_month = summary.index[0]
        st.subheader(f"🔍 פירוט הוצאות אשראי - {last_month}")
        last_month_c = df_c = df_credit[df_credit['Month'] == last_month]
        cat_summary = last_month_c.groupby('קטגוריה')['סכום'].sum().sort_values(ascending=False)
        st.bar_chart(cat_summary)
