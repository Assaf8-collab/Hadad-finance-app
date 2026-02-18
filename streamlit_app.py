import streamlit as st
import pandas as pd
import json
import os

# --- 1. ניהול הגדרות וזיכרון (JSON) ---
SETTINGS_FILE = 'app_settings.json'

def load_settings():
    default = {"approved_income": [], "approved_expenses": [], "savings_list": []}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for key in default:
                    if key not in data: data[key] = default[key]
                return data
        except:
            return default
    return default

def save_settings(inc_list, exp_list, sav_list):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            "approved_income": inc_list,
            "approved_expenses": exp_list,
            "savings_list": sav_list
        }, f, ensure_ascii=False, indent=4)

# --- 2. פונקציות עזר וסיווג ---
CATEGORY_MAP = {
    'מזון וסופר': ['שופרסל', 'הכל כאן', 'יוחננוף', 'קשת טעמים', 'רמי לוי', 'מאפיית'],
    'חינוך וחוגים': ['נוקדים', 'מוסדות חינוך', 'עירייה', 'מתנ"ס'],
    'תחבורה ורכב': ['פנגו', 'פז', 'סונול', 'דור אלון', 'חניון'],
    'פנאי ומסעדות': ['קורטושוק', 'מסעדה', 'קפה', 'וולט', 'WOLT'],
    'מגורים ואחזקה': ['ארנונה', 'חשמל', 'ועד בית', 'מי שבע', 'גז'],
}

def get_category(description, savings_list):
    if pd.isna(description): return 'אחר'
    desc = str(description)
    
    # 1. בדיקת סיווג ידני כחסכון מה-UI
    if desc in savings_list:
        return 'חסכון והשקעות'
    
    # 2. זיהוי לפי מילות מפתח קבועות
    desc_lower = desc.lower()
    for cat, keys in CATEGORY_MAP.items():
        if any(k in desc_lower for k in keys): return cat
    
    # 3. זיהוי חסכון גנרי ממילות מפתח (גיבוי)
    savings_keywords = ['הפקדה', 'חסכון', 'ניירות ערך', 'קופת גמל', 'פנסיה', 'השתלמות', 'פקדון']
    if any(k in desc_lower for k in savings_keywords):
        return 'חסכון והשקעות'
        
    return 'אחר'

def clean_amount(v):
    if pd.isna(v) or v == 'תיאור התנועה': return 0.0
    try:
        return float(str(v).replace('₪', '').replace(',', '').strip())
    except:
        return 0.0

# --- 3. ממשק משתמש ---
st.set_page_config(page_title="ניהול תקציב - משפחת חדד", layout="wide")

with st.sidebar:
    st.header("⚙️ הגדרות")
    if st.button("🗑️ איפוס כל ההגדרות"):
        if os.path.exists(SETTINGS_FILE):
            os.remove(SETTINGS_FILE)
            st.rerun()

st.title("💰 ניהול תזרים מזומנים וסיווג הוצאות")

bank_up = st.file_uploader("העלה קובץ עו\"ש (CSV)", type="csv")
credit_up = st.file_uploader("העלה קובץ אשראי (CSV)", type="csv")

if bank_up and credit_up:
    settings = load_settings()
    prev_inc = settings.get("approved_income", [])
    prev_exp = settings.get("approved_expenses", [])
    prev_sav = settings.get("savings_list", [])

    # עיבוד בנק (דיסקונט)
    df_bank = pd.read_csv(bank_up, skiprows=7)
    df_bank['תאריך'] = pd.to_datetime(df_bank['תאריך'], dayfirst=True, errors='coerce')
    df_bank['סכום'] = df_bank['₪ זכות/חובה '].apply(clean_amount)
    df_bank = df_bank.dropna(subset=['תאריך']).rename(columns={'תיאור התנועה': 'מקור התנועה'})
    df_bank['Month'] = df_bank['תאריך'].dt.to_period('M')
    
    # סינון חיובי אשראי מהעו"ש למניעת כפילות
    credit_keywords = ['כ.א.ל', 'מקס', 'ישראכרט', 'חיוב לכרטיס', 'ויזה']
    df_inc_raw = df_bank[df_bank['סכום'] > 0].copy()
    df_bank_exp_raw = df_bank[(df_bank['סכום'] < 0) & (~df_bank['מקור התנועה'].str.contains('|'.join(credit_keywords), na=False))].copy()

    # --- שלב המיון והסיווג האינטראקטיבי ---
    st.divider()
    st.subheader("🛠️ שלב 1: אישור וסיווג תנועות עו\"ש")
    
    available_months = sorted([m for m in df_bank['Month'].unique() if m < pd.Timestamp.now().to_period('M')], reverse=True)
    
    if available_months:
        selected_month = st.selectbox("בחר חודש לסיווג:", available_months)
        col_inc, col_exp = st.columns(2)
        
        with col_inc:
            st.write(f"**הכנסות - {selected_month}**")
            m_inc = df_inc_raw[df_inc_raw['Month'] == selected_month].groupby('מקור התנועה')['סכום'].sum().reset_index()
            m_inc.insert(0, "חסכון?", m_inc['מקור התנועה'].isin(prev_sav))
            m_inc.insert(0, "אישור", m_inc['מקור התנועה'].isin(prev_inc) if prev_inc else True)
            ed_inc = st.data_editor(m_inc, hide_index=True, key=f"inc_{selected_month}", column_config={"מקור התנועה": st.column_config.TextColumn(width="large")})

        with col_exp:
            st.write(f"**הוצאות עו\"ש - {selected_month}**")
            m_exp = df_bank_exp_raw[df_bank_exp_raw['Month'] == selected_month].groupby('מקור התנועה')['סכום'].sum().abs().reset_index()
            m_exp.insert(0, "חסכון?", m_exp['מקור התנועה'].isin(prev_sav))
            m_exp.insert(0, "אישור", m_exp['מקור התנועה'].isin(prev_exp) if prev_exp else True)
            ed_exp = st.data_editor(m_exp, hide_index=True, key=f"exp_{selected_month}", column_config={"מקור התנועה": st.column_config.TextColumn(width="large")})

        if st.button("💾 שמור הגדרות (המערכת תזכור את הבחירות לחודשים הבאים)"):
            # עדכון רשימות האישור והחסכון
            curr_inc_approved = set(ed_inc[ed_inc["אישור"] == True]['מקור התנועה'])
            curr_exp_approved = set(ed_exp[ed_exp["אישור"] == True]['מקור התנועה'])
            curr_inc_sav = set(ed_inc[ed_inc["חסכון?"] == True]['מקור התנועה'])
            curr_exp_sav = set(ed_exp[ed_exp["חסכון?"] == True]['מקור התנועה'])
            
            # לוגיקה לעדכון הזיכרון (מוסיף חדשים ומסיר את מה שבוטל בטבלה הנוכחית)
            final_inc = (set(prev_inc) - set(ed_inc['מקור התנועה'])) | curr_inc_approved
            final_exp = (set(prev_exp) - set(ed_exp['מקור התנועה'])) | curr_exp_approved
            final_sav = (set(prev_sav) - (set(ed_inc['מקור התנועה']) | set(ed_exp['מקור התנועה']))) | curr_inc_sav | curr_exp_sav
            
            save_settings(list(final_inc), list(final_exp), list(final_sav))
            st.success("ההגדרות נשמרו!")
            st.rerun()

    # --- עיבוד סופי וניתוח "לאן הולך הכסף" ---
    updated_settings = load_settings()
    approved_inc = updated_settings['approved_income']
    approved_exp = updated_settings['approved_expenses']
    savings_list = updated_settings['savings_list']

    df_inc_f = df_inc_raw[df_inc_raw['מקור התנועה'].isin(approved_inc)] if approved_inc else df_inc_raw
    df_exp_f = df_bank_exp_raw[df_bank_exp_raw['מקור התנועה'].isin(approved_exp)] if approved_exp else df_bank_exp_raw
    
    # הוספת קטגוריות
    df_inc_f = df_inc_f.copy()
    df_inc_f['קטגוריה'] = df_inc_f['מקור התנועה'].apply(lambda x: get_category(x, savings_list))
    df_exp_f = df_exp_f.copy()
    df_exp_f['קטגוריה'] = df_exp_f['מקור התנועה'].apply(lambda x: get_category(x, savings_list))

    # עיבוד אשראי
    df_c = pd.read_csv(credit_up, skiprows=8)
    df_c['סכום'] = df_c['סכום החיוב'].apply(clean_amount)
    df_c['תאריך עסקה'] = pd.to_datetime(df_c['תאריך עסקה'], dayfirst=True, errors='coerce')
    df_c['Month'] = df_c['תאריך עסקה'].dt.to_period('M')
    df_c['קטגוריה'] = df_c['בית עסק'].apply(lambda x: get_category(x, savings_list))

    # סיכום תזרימי
    summary = pd.DataFrame({
        'הכנסות': df_inc_f.groupby('Month')['סכום'].sum(),
        'הוצאות בנק': df_exp_f.groupby('Month')['סכום'].sum().abs(),
        'הוצאות אשראי': df_c.groupby('Month')['סכום'].sum()
    }).fillna(0)
    
    summary = summary[summary.index < pd.Timestamp.now().to_period('M')]
    
    if not summary.empty:
        summary['סה"כ הוצאות'] = summary['הוצאות בנק'] + summary['הוצאות אשראי']
        summary['נטו'] = summary['הכנסות'] - summary['סה"כ הוצאות']
        
        st.divider()
        st.subheader("📊 שלב 2: סיכום תזרים מזומנים סופי")
        st.table(summary.sort_index(ascending=False).style.format("₪{:,.2f}"))

        # --- ניתוח קטגוריות משולב ---
        last_m = summary.index[0]
        st.subheader(f"🔍 שלב 3: לאן הולך הכסף? (ניתוח חודש {last_m})")
        
        # איחוד כלל ההוצאות והחסכונות לצורך הגרף
        combined_analysis = pd.concat([
            df_c[df_c['Month'] == last_m][['קטגוריה', 'סכום']],
            df_exp_f[df_exp_f['Month'] == last_m][['קטגוריה', 'סכום']],
            df_inc_f[df_inc_f['Month'] == last_m][['קטגוריה', 'סכום']] # כולל הכנסות שסומנו כחסכון
        ])
        
        # סינון להצגת קטגוריות הוצאה וחיסכון בלבד (מתעלמים מהכנסה רגילה בגרף)
        cat_final = combined_analysis[combined_analysis['קטגוריה'] != 'אחר'].groupby('קטגוריה')['סכום'].sum().sort_values(ascending=False)
        
        
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.bar_chart(cat_final)
        with c2:
            if 'חסכון והשקעות' in cat_final:
                st.metric("סכום שנחסך", f"₪{cat_final['חסכון והשקעות']:,.0f}")
                
            # חישוב אחוז חסכון מההכנסה
            total_inc = summary.loc[last_m, 'הכנסות']
            if total_inc > 0 and 'חסכון והשקעות' in cat_final:
                savings_pct = (cat_analysis := cat_final['חסכון והשקעות'] / total_inc) * 100
                st.metric("שיעור חסכון", f"{savings_pct:.1f}%")
            
            st.write(cat_final.map("₪{:,.2f}".format))
