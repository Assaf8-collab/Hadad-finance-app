import streamlit as st
import pandas as pd

st.set_page_config(page_title="מעקב פיננסי משפחתי", layout="wide")

st.title("📊 מעקב הוצאות - משפחת חדד")

# פונקציות עיבוד הנתונים
def process_data(bank_file, credit_file):
    # עו"ש דיסקונט - מתחיל משורה 8
    df_bank = pd.read_csv(bank_file, skiprows=7)
    
    # כרטיסי אשראי - מתחיל משורה 9
    df_credit = pd.read_csv(credit_file, skiprows=8)
    
    return df_bank, df_credit

# ממשק העלאת קבצים
col1, col2 = st.columns(2)
with col1:
    bank_up = st.file_uploader("העלה קובץ עו\"ש (CSV)", type="csv")
with col2:
    credit_up = st.file_uploader("העלה קובץ אשראי (CSV)", type="csv")

if bank_up and credit_up:
    df_b, df_c = process_data(bank_up, credit_up)
    
    # תצוגה ראשונית בנייד
    st.subheader("סיכום מהיר")
    
    # חישוב הוצאה כוללת באשראי (למשל)
    total_credit = df_c['סכום החיוב'].sum()
    st.metric("סה\"כ חיוב אשראי קרוב", f"₪{total_credit:,.2f}")
    
    # הצגת הטבלאות
    with st.expander("לצפייה בפירוט עו\"ש"):
        st.dataframe(df_b)
    
    with st.expander("לצפייה בפירוט אשראי"):
        st.dataframe(df_c)
