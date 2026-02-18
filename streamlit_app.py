import streamlit as st
import pandas as pd
import json
import os
import re
from currency_converter import CurrencyConverter

# אתחול ממיר המטבעות
c = CurrencyConverter()

# --- 1. פונקציית המרה חכמה ---
def convert_to_ils(amount, currency_symbol, date):
    """ממירה סכום לשקל לפי תאריך העסקה. אם זה יורו, מבצעת המרה."""
    if pd.isna(amount) or amount == 0:
        return 0.0
    
    # אם המטבע הוא יורו
    if '€' in str(currency_symbol) or 'EUR' in str(currency_symbol).upper():
        try:
            # המרה מאירו לדולר (הספרייה תומכת בדולר כבסיס חזק יותר) ואז לשקל
            # או ישירות ליורו-שקל אם הנתונים קיימים
            rate = c.convert(amount, 'EUR', 'ILS', date=date)
            return rate
        except:
            # גיבוי במקרה שהתאריך רחוק מדי או חסר נתון - משתמש בשער ממוצע/אחרון
            return amount * 4.0 # שער הגנה מוערך ליורו
    
    return amount

# --- 2. פונקציית ניקוי משופרת ---
def clean_and_detect_currency(v):
    if pd.isna(v) or v == '': return 0.0, 'ILS'
    v_str = str(v)
    currency = 'EUR' if '€' in v_str else 'ILS'
    cleaned = re.sub(r'[^\d\.\-]', '', v_str)
    try:
        return float(cleaned), currency
    except:
        return 0.0, 'ILS'

# --- 3. ממשק משתמש (חלק העיבוד המעודכן) ---
st.set_page_config(page_title="ניהול תקציב משפחתי", layout="wide")

# ... (חלקי טעינת הקבצים וההגדרות נשארים דומים) ...

if bank_up and credit_up:
    # עיבוד אשראי עם המרת מט"ח
    df_c_raw = pd.read_csv(credit_up, skiprows=8)
    
    processed_rows = []
    for _, row in df_c_raw.iterrows():
        # זיהוי סכום ומטבע (בודק בעמודת סכום חיוב או סכום מקורי)
        val_to_clean = row.get('סכום מקורי', row.get('סכום חיוב', 0))
        amt, curr = clean_and_detect_currency(val_to_clean)
        
        # תאריך העסקה לצורך ההמרה
        tx_date = pd.to_datetime(row['תאריך עסקה'], dayfirst=True, errors='coerce')
        
        # המרה לשקלים אם צריך
        if curr == 'EUR' and not pd.isna(tx_date):
            ils_amount = convert_to_ils(amt, curr, tx_date)
            is_converted = True
        else:
            ils_amount = amt
            is_converted = False
            
        processed_rows.append({
            'תאריך': tx_date,
            'בית עסק': row.get('בית עסק', 'לא ידוע'),
            'סכום מקורי': f"{amt} {curr}",
            'סכום בשקלים': ils_amount,
            'הוסב?': "✅" if is_converted else "❌",
            'Month': tx_date.to_period('M') if not pd.isna(tx_date) else None
        })
    
    df_processed_credit = pd.DataFrame(processed_rows).dropna(subset=['תאריך'])

    # תצוגה בשלב הסיווג
    st.subheader("💳 פירוט עסקאות אשראי (כולל המרת יורו)")
    st.dataframe(
        df_processed_credit[['תאריך', 'בית עסק', 'סכום מקורי', 'סכום בשקלים', 'הוסב?']],
        column_config={
            "סכום בשקלים": st.column_config.NumberColumn("סכום סופי (ILS)", format="₪%.2f")
        }
    )
