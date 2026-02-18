import streamlit as st
import pandas as pd

# פונקציית ניקוי מספרים (מעודכנת לטיפול במינוסים וסימנים)
def clean_amount(value):
    if pd.isna(value) or value == 'תיאור התנועה': return 0.0
    if isinstance(value, str):
        value = value.replace('₪', '').replace(',', '').replace(' ', '')
    try:
        return float(value)
    except:
        return 0.0

def process_data(bank_file, credit_file):
    # 1. עיבוד עו"ש
    df_bank = pd.read_csv(bank_file, skiprows=7)
    df_bank['תאריך'] = pd.to_datetime(df_bank['תאריך'], dayfirst=True, errors='coerce')
    df_bank['סכום'] = df_bank['₪ זכות/חובה '].apply(clean_amount)
    df_bank = df_bank.dropna(subset=['תאריך'])
    
    # זיהוי חיובי אשראי בעו"ש כדי למנוע כפילות
    credit_keywords = ['כ.א.ל', 'מקס', 'ישראכרט', 'חיוב לכרטיס', 'ויזה']
    
    # הפרדה להכנסות והוצאות בנק (ללא אשראי)
    bank_income = df_bank[df_bank['סכום'] > 0].copy()
    bank_expenses = df_bank[
        (df_bank['סכום'] < 0) & 
        (~df_bank['תיאור התנועה'].str.contains('|'.join(credit_keywords), na=False))
    ].copy()
    bank_expenses['סכום'] = bank_expenses['סכום'].abs()

    # 2. עיבוד אשראי
    df_credit = pd.read_csv(credit_file, skiprows=8)
    df_credit['תאריך עסקה'] = pd.to_datetime(df_credit['תאריך עסקה'], dayfirst=True, errors='coerce')
    df_credit['סכום'] = df_credit['סכום החיוב'].apply(clean_amount)
    df_credit = df_credit.dropna(subset=['תאריך עסקה'])

    # 3. איחוד נתונים לפי חודש
    bank_income['Month'] = bank_income['תאריך'].dt.to_period('M')
    bank_expenses['Month'] = bank_expenses['תאריך'].dt.to_period('M')
    df_credit['Month'] = df_credit['תאריך עסקה'].dt.to_period('M')

    monthly_inc = bank_income.groupby('Month')['סכום'].sum()
    monthly_bank_exp = bank_expenses.groupby('Month')['סכום'].sum()
    monthly_credit_exp = df_credit.groupby('Month')['סכום'].sum()

    # יצירת טבלת תזרים
    summary = pd.DataFrame({
        'הכנסות': monthly_inc,
        'הוצאות בנק (משכנתא/הו"ק)': monthly_bank_exp,
        'הוצאות אשראי': monthly_credit_exp
    }).fillna(0)

    summary['סה"כ הוצאות'] = summary['הוצאות בנק (משכנתא/הו"ק)'] + summary['הוצאות אשראי']
    summary['נטו (נשאר בכיס)'] = summary['הכנסות'] - summary['סה"כ הוצאות']
    
    return summary.sort_index(ascending=False)

# ממשק המשתמש
st.set_page_config(page_title="תזרים מזומנים משפחתי", layout="wide")
st.title("💰 סיכום תזרימי חודשי")

bank_up = st.file_uploader("העלה עו\"ש", type="csv")
credit_up = st.file_uploader("העלה אשראי", type="csv")

if bank_up and credit_up:
    summary_table = process_data(bank_up, credit_up)
    
    # תצוגת המדדים של החודש האחרון
    last_month = summary_table.index[0]
    cols = st.columns(3)
    cols[0].metric(f"הכנסות ({last_month})", f"₪{summary_table.loc[last_month, 'הכנסות']:,.0f}")
    cols[1].metric(f"הוצאות ({last_month})", f"₪{summary_table.loc[last_month, 'סה\"כ הוצאות']:,.0f}")
    cols[2].metric("יתרה לתזרים", f"₪{summary_table.loc[last_month, 'נטו (נשאר בכיס)']:,.0f}")

    # טבלת סיכום
    st.subheader("השוואה חודש מול חודש")
    st.table(summary_table.style.format("₪{:,.2f}"))
    
    # גרף תזרים
    st.bar_chart(summary_table[['הכנסות', 'סה"כ הוצאות']])
