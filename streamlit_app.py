import streamlit as st
import pandas as pd

st.set_page_config(page_title="מעקב פיננסי משפחתי", layout="wide")
st.title("📊 מעקב הוצאות - משפחת חדד")

def clean_amount(value):
    """פונקציה שמנקה סימני מטבע ופסיקים והופכת למספר"""
    if pd.isna(value):
        return 0.0
    if isinstance(value, str):
        # מסיר ₪, פסיקים ורווחים
        value = value.replace('₪', '').replace(',', '').strip()
    try:
        return float(value)
    except:
        return 0.0

def process_data(bank_file, credit_file):
    # קריאת עו"ש - דילוג על 7 שורות
    df_bank = pd.read_csv(bank_file, skiprows=7)
    # ניקוי עמודת הסכום בעו"ש
    df_bank['₪ זכות/חובה '] = df_bank['₪ זכות/חובה '].apply(clean_amount)
    
    # קריאת אשראי - דילוג על 8 שורות
    df_credit = pd.read_csv(credit_file, skiprows=8)
    # ניקוי עמודת הסכום באשראי
    df_credit['סכום החיוב'] = df_credit['סכום החיוב'].apply(clean_amount)
    
    return df_bank, df_credit

# ממשק העלאה
bank_up = st.file_uploader("העלה קובץ עו\"ש (CSV)", type="csv")
credit_up = st.file_uploader("העלה קובץ אשראי (CSV)", type="csv")

if bank_up and credit_up:
    try:
        df_b, df_c = process_data(bank_up, credit_up)
        
        # חישוב סך הכל
        total_spent = df_c['סכום החיוב'].sum()
        
        st.metric("סה\"כ חיוב אשראי", f"₪{total_spent:,.2f}")
        
        # הצגת נתונים
        st.subheader("פירוט עסקאות אשראי")
        st.dataframe(df_c[['בית עסק', 'תאריך עסקה', 'סכום החיוב']])
        
    except Exception as e:
        st.error(f"אופס, יש שגיאה בעיבוד הקובץ: {e}")
        st.info("טיפ: וודא שהעלית את הקבצים הנכונים ושלא שינית את שמות העמודות.")
