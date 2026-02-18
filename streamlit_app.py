import json
import os

SETTINGS_FILE = 'app_settings.json'

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"approved_sources": []}

def save_settings(settings_dict):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings_dict, f, ensure_ascii=False, indent=4)
import streamlit as st
import pandas as pd

# 1. הגדרות וסיווגים
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

# 2. פונקציית עיבוד הנתונים
def process_data(bank_file, credit_file):
    # עיבוד עו"ש - שימוש בשם העמודה המדויק עם הרווח בסוף
    df_bank = pd.read_csv(bank_file, skiprows=7)
    df_bank['תאריך'] = pd.to_datetime(df_bank['תאריך'], dayfirst=True, errors='coerce')
    df_bank['סכום'] = df_bank['₪ זכות/חובה '].apply(clean_amount)
    df_bank = df_bank.dropna(subset=['תאריך'])
    df_bank['Month'] = df_bank['תאריך'].dt.to_period('M')
    
    # הפרדה להכנסות גולמיות
    df_income_raw = df_bank[df_bank['סכום'] > 0].copy()
    
    # הפרדה להוצאות בנק (ללא חיובי אשראי)
    credit_keywords = ['כ.א.ל', 'מקס', 'ישראכרט', 'חיוב לכרטיס', 'ויזה']
    df_bank_exp = df_bank[
        (df_bank['סכום'] < 0) & 
        (~df_bank['תיאור התנועה'].str.contains('|'.join(credit_keywords), na=False))
    ].copy()
    df_bank_exp['סכום'] = df_bank_exp['סכום'].abs()

    # עיבוד אשראי
    df_credit = pd.read_csv(credit_file, skiprows=8)
    df_credit['תאריך עסקה'] = pd.to_datetime(df_credit['תאריך עסקה'], dayfirst=True, errors='coerce')
    df_credit['סכום'] = df_credit['סכום החיוב'].apply(clean_amount)
    df_credit = df_credit.dropna(subset=['תאריך עסקה'])
    df_credit['Month'] = df_credit['תאריך עסקה'].dt.to_period('M')
    df_credit['קטגוריה'] = df_credit['בית עסק'].apply(get_category)

    return df_income_raw, df_bank_exp, df_credit

# 3. ממשק המשתמש
st.set_page_config(page_title="ניהול תקציב משפחתי", layout="wide")
st.title("💰 תזרים מזומנים וניהול הוצאות")

bank_up = st.file_uploader("העלה קובץ עו\"ש (CSV)", type="csv")
credit_up = st.file_uploader("העלה קובץ אשראי (CSV)", type="csv")

if bank_up and credit_up:
    df_inc_raw, df_bank_exp, df_c = process_data(bank_up, credit_up)
    
    # --- חלק אינטראקטיבי משופר: ניהול הכנסות ---
    st.divider()
    st.subheader("🏦 הגדרת מקורות הכנסה")
    st.write("סמן את מקורות ההכנסה האמיתיים (משכורות, קצבאות וכו'). פריטים שלא יסומנו יושמטו מהתזרים.")

    # יצירת טבלת סיכום של מקורות הכנסה לבחירה
    # אנחנו מקבצים לפי תיאור כדי שלא תצטרך לסמן כל חודש בנפרד
    income_options = df_inc_raw.groupby('תיאור התנועה').agg({
        'סכום': ['sum', 'mean', 'count']
    }).reset_index()
    
    income_options.columns = ['תיאור התנועה', 'סך הכל שהתקבל', 'ממוצע חודשי', 'מספר פעמים']
    
    # הוספת עמודת בחירה (Checkmark)
    income_options.insert(0, "נכלל בתזרים", True)

   # טעינת הגדרות קודמות
    saved_config = load_settings()
    previously_approved = saved_config.get("approved_sources", [])

    st.subheader("🏦 הגדרת מקורות הכנסה")
    
    # הכנת הנתונים לטבלה
    income_options = df_inc_raw.groupby('תיאור התנועה').agg({'סכום': ['sum', 'count']}).reset_index()
    income_options.columns = ['תיאור התנועה', 'סך הכל', 'פעמים']
    
    # סימון אוטומטי של מה שנשמר בעבר
    income_options.insert(0, "נכלל", income_options['תיאור התנועה'].isin(previously_approved))

    # הצגת הטבלה (בלי חיתוך טקסט)
    edited_income = st.data_editor(
        income_options,
        column_config={
            "נכלל": st.column_config.CheckboxColumn("אישור", default=True),
            "תיאור התנועה": st.column_config.TextColumn("מקור הכנסה", width="large"),
            "סך הכל": st.column_config.NumberColumn("סכום מצטבר", format="₪%.0f"),
        },
        disabled=['תיאור התנועה', 'סך הכל', 'פעמים'],
        hide_index=True,
    )

    # כפתור שמירה קבוע
    if st.button("💾 שמור הגדרות אלו לחודש הבא"):
        approved_list = edited_income[edited_income["נכלל"] == True]['תיאור התנועה'].tolist()
        save_settings({"approved_sources": approved_list})
        st.success("ההגדרות נשמרו בהצלחה!")
        
    # סינון הנתונים להמשך החישוב
    final_approved = edited_income[edited_income["נכלל"] == True]['תיאור התנועה'].tolist()
    df_inc_filtered = df_inc_raw[df_inc_raw['תיאור התנועה'].isin(final_approved)]

    # סינון הנתונים המקוריים לפי מה שנבחר בטבלה
    approved_descriptions = edited_income[edited_income["נכלל בתזרים"] == True]['תיאור התנועה'].tolist()
    df_inc_filtered = df_inc_raw[df_inc_raw['תיאור התנועה'].isin(approved_descriptions)]
    
    # --- המשך חישוב הסיכום החודשי (כמו קודם) ---
    
    # --- חישוב סיכום חודשי (איחוד וסינון חודשים) ---
    monthly_inc = df_inc_filtered.groupby('Month')['סכום'].sum()
    monthly_bank_exp = df_bank_exp.groupby('Month')['סכום'].sum()
    monthly_credit_exp = df_c.groupby('Month')['סכום'].sum()
    
    summary = pd.DataFrame({
        'הכנסות': monthly_inc,
        'הוצאות בנק': monthly_bank_exp,
        'הוצאות אשראי': monthly_credit_exp
    }).fillna(0)
    
    # סינון חודשים שלמים בלבד (לפני החודש הנוכחי)
    current_month = pd.Timestamp.now().to_period('M')
    summary = summary[summary.index < current_month]
    
    if not summary.empty:
        summary['סה"כ הוצאות'] = summary['הוצאות בנק'] + summary['הוצאות אשראי']
        summary['נטו (נשאר בכיס)'] = summary['הכנסות'] - summary['סה"כ הוצאות']
        
        # --- תצוגת תוצאות ---
        last_month = summary.index[0]
        st.success(f"ניתוח לחודש מלא אחרון: {last_month}")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("הכנסות", f"₪{summary.loc[last_month, 'הכנסות']:,.0f}")
        m2.metric("הוצאות", f"₪{summary.loc[last_month, 'סה\"כ הוצאות']:,.0f}")
        m3.metric("יתרה", f"₪{summary.loc[last_month, 'נטו (נשאר בכיס)']:,.0f}")
        
        # גרף התפלגות אשראי
        st.divider()
        st.subheader(f"📊 ניתוח קטגוריות אשראי - {last_month}")
        last_month_c = df_c[df_c['Month'] == last_month]
        cat_data = last_month_c.groupby('קטגוריה')['סכום'].sum().sort_values(ascending=False)
        st.bar_chart(cat_data)
        
        # טבלת סיכום רב-חודשית
        st.divider()
        st.subheader("📅 השוואה חודש מול חודש")
        st.table(summary.sort_index(ascending=False).style.format("₪{:,.2f}"))
    else:
        st.warning("לא נמצאו חודשים מלאים קודמים בקבצים שהעלית.")

with st.sidebar:
    st.header("⚙️ הגדרות מערכת")
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            st.download_button(
                label="📥 הורד קובץ הגדרות לגיבוי",
                data=f.read(),
                file_name="my_finance_settings.json",
                mime="application/json"
            )
