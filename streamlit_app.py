import streamlit as st
import pandas as pd
import json
import os
import re
from currency_converter import CurrencyConverter

# --- 1. אתחול ומערכת זיכרון ---
SETTINGS_FILE = 'app_settings.json'

def load_settings():
    default = {
        "approved_income": [], 
        "approved_expenses": [], 
        "savings_list": [],
        "credit_categories": {}, 
        "excluded_credit": []
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for key in default:
                    if key not in data: data[key] = default[key]
                return data
        except: return default
    return default

def save_settings(settings_dict):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings_dict, f, ensure_ascii=False, indent=4)

# אתחול ממיר מט"ח
try:
    c_conv = CurrencyConverter()
except:
    c_conv = None

# --- 2. פונקציות עזר (סיווג, ניקוי והמרה) ---
CATEGORIES = ['אחר', 'קניות סופר', 'רכב', 'ביטוח', 'ביגוד', 'אוכל בחוץ', 'בילויים', 'חסכון והשקעות']

def clean_and_detect(v):
    if pd.isna(v) or v == '': return 0.0, 'ILS'
    v_str = str(v)
    if '€' in v_str or 'EUR' in v_str.upper(): curr = 'EUR'
    elif '$' in v_str or 'USD' in v_str.upper(): curr = 'USD'
    else: curr = 'ILS'
    cleaned = re.sub(r'[^\d\.\-]', '', v_str)
    try: return float(cleaned), curr
    except: return 0.0, 'ILS'

def convert_to_ils(amt, curr, date):
    if curr == 'ILS' or not c_conv or amt == 0: return amt
    try:
        return c_conv.convert(amt, curr, 'ILS', date=date)
    except:
        rates = {'EUR': 4.1, 'USD': 3.7}
        return amt * rates.get(curr, 1.0)

def get_initial_cat(desc, settings):
    if desc in settings['credit_categories']: return settings['credit_categories'][desc]
    mapping = {
        'קניות סופר': ['שופרסל', 'הכל כאן', 'יוחננוף', 'קשת טעמים', 'רמי לוי', 'ויקטורי'],
        'אוכל בחוץ': ['מסעדה', 'קפה', 'וולט', 'WOLT', 'מקדונלד'],
        'רכב': ['פנגו', 'פז', 'סונול', 'דור אלון', 'חניון', 'דלק'],
        'ביגוד': ['זארה', 'ZARA', 'H&M', 'טרמינל']
    }
    d_low = desc.lower()
    for cat, keys in mapping.items():
        if any(k in d_low for k in keys): return cat
    return 'אחר'

# --- 3. ממשק משתמש ---
st.set_page_config(page_title="תזרים משפחת חדד", layout="wide")

with st.sidebar:
    st.header("⚙️ הגדרות")
    if st.button("🗑️ איפוס הגדרות"):
        if os.path.exists(SETTINGS_FILE): os.remove(SETTINGS_FILE)
        st.rerun()

st.title("💰 ניהול תזרים מזומנים מאוחד")

bank_up = st.file_uploader("העלה עו\"ש (CSV)", type="csv")
credit_up = st.file_uploader("העלה אשראי (CSV)", type="csv")

if bank_up and credit_up:
    settings = load_settings()
    
    # א. עיבוד בנק
    df_b = pd.read_csv(bank_up, skiprows=7)
    df_b['תאריך'] = pd.to_datetime(df_b['תאריך'], dayfirst=True, errors='coerce')
    df_b['סכום'] = df_b['₪ זכות/חובה '].apply(lambda x: clean_and_detect(x)[0])
    df_b = df_b.dropna(subset=['תאריך']).rename(columns={'תיאור התנועה': 'מקור התנועה'})
    df_b['Month'] = df_b['תאריך'].dt.to_period('M')
    
    credit_keys = ['כ.א.ל', 'מקס', 'ישראכרט', 'חיוב לכרטיס', 'ויזה']
    df_inc_raw = df_b[df_b['סכום'] > 0].copy()
    df_exp_raw = df_b[(df_b['סכום'] < 0) & (~df_b['מקור התנועה'].str.contains('|'.join(credit_keys), na=False))].copy()

    # ב. עיבוד אשראי (כולל המרת מט"ח)
    df_c_raw = pd.read_csv(credit_up, skiprows=8)
    c_processed = []
    for _, row in df_c_raw.iterrows():
        val = row.get('סכום מקורי', row.get('סכום חיוב', row.get('סכום החיוב', 0)))
        amt, curr = clean_and_detect(val)
        dt = pd.to_datetime(row['תאריך עסקה'], dayfirst=True, errors='coerce')
        ils_amt = convert_to_ils(amt, curr, dt)
        c_processed.append({'תאריך': dt, 'בית עסק': row.get('בית עסק', 'לא ידוע'), 'סכום': ils_amt, 'מטבע': curr, 'Month': dt.to_period('M') if not pd.isna(dt) else None})
    df_c = pd.DataFrame(c_processed).dropna(subset=['תאריך'])

    # ג. שלב המיון (UI)
    curr_m = pd.Timestamp.now().to_period('M')
    available_months = sorted([m for m in df_b['Month'].unique() if m < curr_m], reverse=True)
    sel_month = st.selectbox("בחר חודש לסיווג:", available_months)

    st.subheader(f"🛠️ שלב 1: מיון תנועות - {sel_month}")
    t1, t2, t3 = st.tabs(["הכנסות", "הוצאות בנק", "הוצאות אשראי"])
    
    with t1:
        m_inc = df_inc_raw[df_inc_raw['Month'] == sel_month].groupby('מקור התנועה')['סכום'].sum().reset_index()
        m_inc.insert(0, "אישור", m_inc['מקור התנועה'].isin(settings['approved_income']) if settings['approved_income'] else True)
        ed_inc = st.data_editor(m_inc, hide_index=True, key="inc_ed")
        
    with t2:
        m_exp = df_exp_raw[df_exp_raw['Month'] == sel_month].groupby('מקור התנועה')['סכום'].sum().abs().reset_index()
        m_exp.insert(0, "חסכון?", m_exp['מקור התנועה'].isin(settings['savings_list']))
        m_exp.insert(0, "אישור", m_exp['מקור התנועה'].isin(settings['approved_expenses']) if settings['approved_expenses'] else True)
        ed_exp = st.data_editor(m_exp, hide_index=True, key="exp_ed")

    with t3:
        m_c = df_c[df_c['Month'] == sel_month].groupby('בית עסק')['סכום'].sum().reset_index()
        m_c['קטגוריה'] = m_c['בית עסק'].apply(lambda x: get_initial_cat(x, settings))
        m_c.insert(0, "תזרימי?", ~m_c['בית עסק'].isin(settings['excluded_credit']))
        ed_c = st.data_editor(m_c, hide_index=True, key="c_ed", column_config={"קטגוריה": st.column_config.SelectboxColumn(options=CATEGORIES)})

    if st.button("💾 שמור הגדרות"):
        settings['approved_income'] = list((set(settings['approved_income']) - set(m_inc['מקור התנועה'])) | set(ed_inc[ed_inc["אישור"]]['מקור התנועה']))
        settings['approved_expenses'] = list((set(settings['approved_expenses']) - set(m_exp['מקור התנועה'])) | set(ed_exp[ed_exp["אישור"]]['מקור התנועה']))
        settings['savings_list'] = list((set(settings['savings_list']) - set(m_exp['מקור התנועה'])) | set(ed_exp[ed_exp["חסכון?"]]['מקור התנועה']))
        for _, row in ed_c.iterrows():
            settings['credit_categories'][row['בית עסק']] = row['קטגוריה']
            if not row['תזרימי?']: 
                if row['בית עסק'] not in settings['excluded_credit']: settings['excluded_credit'].append(row['בית עסק'])
            elif row['בית עסק'] in settings['excluded_credit']: settings['excluded_credit'].remove(row['בית עסק'])
        save_settings(settings)
        st.rerun()

    # ד. סיכום תזרים סופי
    st.divider()
    f_inc = df_inc_raw[df_inc_raw['מקור התנועה'].isin(settings['approved_income'])]
    f_bank_exp = df_exp_raw[df_exp_raw['מקור התנועה'].isin(settings['approved_expenses'])]
    f_c = df_c[~df_c['בית עסק'].isin(settings['excluded_credit'])].copy()
    f_c['קטגוריה'] = f_c['בית עסק'].apply(lambda x: settings['credit_categories'].get(x, get_initial_cat(x, settings)))

    summary = pd.DataFrame({
        'הכנסות': f_inc.groupby('Month')['סכום'].sum(),
        'הוצאות בנק': f_bank_exp.groupby('Month')['סכום'].sum().abs(),
        'הוצאות אשראי': f_c.groupby('Month')['סכום'].sum()
    }).fillna(0)
    summary = summary[summary.index < curr_m]
    
    if not summary.empty:
        summary['סה"כ הוצאות'] = summary['הוצאות בנק'] + summary['הוצאות אשראי']
        summary['נטו'] = summary['הכנסות'] - summary['סה"כ הוצאות']
        st.subheader("📊 סיכום תזרים")
        st.table(summary.sort_index(ascending=False).style.format("₪{:,.2f}"))

        # ה. ניתוח קטגוריות
        st.subheader(f"🔍 התפלגות הוצאות - {sel_month}")
        c_cat = f_c[f_c['Month'] == sel_month][['קטגוריה', 'סכום']]
        b_cat = f_bank_exp[f_bank_exp['Month'] == sel_month].assign(קטגוריה=lambda x: x['מקור התנועה'].apply(lambda y: 'חסכון והשקעות' if y in settings['savings_list'] else 'אחר'))[['קטגוריה', 'סכום']]
        total_cat = pd.concat([c_cat, b_cat]).groupby('קטגוריה')['סכום'].sum().sort_values(ascending=False)
        st.bar_chart(total_cat)
