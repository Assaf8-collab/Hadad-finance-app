import streamlit as st
import pandas as pd
import json
import os
import re

# ניסיון לטעון את ספריית המרות המטבע
try:
    from currency_converter import CurrencyConverter
    c_conv = CurrencyConverter()
except ImportError:
    c_conv = None
    st.warning("שים לב: ספריית currencyconverter לא מותקנת. המרות מט\"ח יבוצעו לפי שערי גיבוי קבועים.")

# --- 1. הגדרות וזיכרון מערכת ---
SETTINGS_FILE = 'app_settings.json'

def load_settings():
    default_settings = {
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
                # וידוא שכל מפתחות החובה קיימים
                for key in default_settings:
                    if key not in data: data[key] = default_settings[key]
                return data
        except: return default_settings
    return default_settings

def save_settings(settings_dict):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings_dict, f, ensure_ascii=False, indent=4)

# --- 2. מנוע סיווג והמרות ---
CATEGORIES = ['אחר', 'קניות סופר', 'רכב', 'ביטוח', 'ביגוד', 'אוכל בחוץ', 'בילויים', 'מגורים ואחזקה', 'חסכון והשקעות']

def clean_and_detect_currency(v):
    if pd.isna(v) or str(v).strip() == '' or str(v) == 'תיאור התנועה': 
        return 0.0, 'ILS'
    v_str = str(v)
    curr = 'EUR' if ('€' in v_str or 'EUR' in v_str.upper()) else ('USD' if ('$' in v_str or 'USD' in v_str.upper()) else 'ILS')
    cleaned = re.sub(r'[^\d\.\-]', '', v_str)
    try: return float(cleaned), curr
    except: return 0.0, 'ILS'

def get_exchange_info(amt, curr, date):
    if curr == 'ILS' or amt == 0: return amt, 1.0
    if c_conv:
        try:
            ils_amt = c_conv.convert(amt, curr, 'ILS', date=date)
            return ils_amt, ils_amt / amt
        except: pass # יפול לשערי הגיבוי אם חסר תאריך במאגר
    
    rates = {'EUR': 4.1, 'USD': 3.7}
    fallback_rate = rates.get(curr, 1.0)
    return amt * fallback_rate, fallback_rate

def get_initial_category(desc, settings):
    desc_str = str(desc)
    # סדרי עדיפויות בסיווג:
    if desc_str in settings.get('savings_list', []): return 'חסכון והשקעות'
    if desc_str in settings.get('credit_categories', {}): return settings['credit_categories'][desc_str]
    
    mapping = {
        'קניות סופר': ['שופרסל', 'הכל כאן', 'יוחננוף', 'קשת טעמים', 'רמי לוי', 'ויקטורי', 'מחסני השוק'],
        'אוכל בחוץ': ['מסעדה', 'קפה', 'וולט', 'wolt', 'מקדונלד', 'פיצה', 'בורגר'],
        'רכב': ['פנגו', 'pango', 'פז', 'סונול', 'דור אלון', 'חניון', 'דלק', 'מוסך', 'כביש 6'],
        'ביגוד': ['זארה', 'zara', 'h&m', 'טרמינל', 'terminal', 'פוקס', 'fox'],
        'בילויים': ['קולנוע', 'סינמה', 'תיאטרון', 'הופעה'],
        'ביטוח': ['ביטוח', 'הראל', 'מגדל', 'כלל', 'הפניקס'],
        'מגורים ואחזקה': ['ארנונה', 'חשמל', 'ועד בית', 'מי שבע', 'גז']
    }
    
    d_low = desc_str.lower()
    for cat, keys in mapping.items():
        if any(k in d_low for k in keys): return cat
    
    if any(k in d_low for k in ['הפקדה', 'חסכון', 'גמל', 'פנסיה', 'השתלמות']): return 'חסכון והשקעות'
    return 'אחר'

# --- 3. בניית הממשק ---
st.set_page_config(page_title="תזרים משפחת חדד", layout="wide")

with st.sidebar:
    st.header("⚙️ הגדרות מערכת")
    if st.button("🗑️ איפוס ומחיקת נתונים"):
        if os.path.exists(SETTINGS_FILE): os.remove(SETTINGS_FILE)
        st.success("הנתונים נמחקו. טוען מחדש...")
        st.rerun()
    st.info("כפתור זה יאפס את כל הסיווגים וההגדרות ששמרת.")

st.title("💰 ניהול תזרים מזומנים חכם")

bank_up = st.file_uploader("העלה קובץ עו\"ש דיסקונט (CSV)", type="csv")
credit_up = st.file_uploader("העלה קובץ אשראי (CSV)", type="csv")

if bank_up and credit_up:
    settings = load_settings()
    
    # --- א. עיבוד בנק ---
    try:
        df_b = pd.read_csv(bank_up, skiprows=7)
        df_b['תאריך'] = pd.to_datetime(df_b['תאריך'], dayfirst=True, errors='coerce')
        df_b['סכום'] = df_b['₪ זכות/חובה '].apply(lambda x: clean_and_detect_currency(x)[0])
        df_b = df_b.dropna(subset=['תאריך']).rename(columns={'תיאור התנועה': 'מקור התנועה'})
        df_b['Month'] = df_b['תאריך'].dt.to_period('M')
        
        credit_keys = ['כ.א.ל', 'מקס', 'ישראכרט', 'חיוב לכרטיס', 'ויזה', 'cal', 'max']
        df_inc_raw = df_b[df_b['סכום'] > 0].copy()
        df_exp_raw = df_b[(df_b['סכום'] < 0) & (~df_b['מקור התנועה'].str.lower().str.contains('|'.join(credit_keys), na=False))].copy()
    except Exception as e:
        st.error(f"שגיאה בעיבוד קובץ העו\"ש. ודא שזהו הפורמט הנכון. פירוט: {e}")
        st.stop()

    # --- ב. עיבוד אשראי (עם המרת מט"ח) ---
    try:
        df_c_raw = pd.read_csv(credit_up, skiprows=8)
        c_processed = []
        for _, row in df_c_raw.iterrows():
            # מציאת עמודת הסכום הרלוונטית (סכום מקורי או חיוב)
            val = row.get('סכום מקורי', row.get('סכום חיוב', row.get('סכום החיוב', 0)))
            amt, curr = clean_and_detect_currency(val)
            dt = pd.to_datetime(row['תאריך עסקה'], dayfirst=True, errors='coerce')
            
            ils_amt, rate = get_exchange_info(amt, curr, dt)
            
            c_processed.append({
                'תאריך': dt, 
                'בית עסק': row.get('בית עסק', 'לא ידוע'), 
                'סכום': ils_amt, 
                'מטבע_מקור': curr, 
                'שער': rate if curr != 'ILS' else None,
                'Month': dt.to_period('M') if not pd.isna(dt) else None
            })
        df_c = pd.DataFrame(c_processed).dropna(subset=['תאריך'])
    except Exception as e:
        st.error(f"שגיאה בעיבוד קובץ האשראי. פירוט: {e}")
        st.stop()

    # --- ג. ממשק מיון וסיווג (שלב 1) ---
    curr_m = pd.Timestamp.now().to_period('M')
    available_months = sorted([m for m in df_b['Month'].unique() if m <= curr_m], reverse=True)
    
    st.divider()
    sel_month = st.selectbox("בחר חודש לסיווג תנועות:", available_months)
    st.subheader(f"🛠️ שלב 1: אישור וסיווג - {sel_month}")
    
    t1, t2, t3 = st.tabs(["🏦 הכנסות", "📉 הוצאות בנק", "💳 הוצאות אשראי"])
    
    with t1:
        m_inc = df_inc_raw[df_inc_raw['Month'] == sel_month].groupby('מקור התנועה')['סכום'].sum().reset_index()
        # אם הזיכרון ריק, מסמן הכל ב-V. אם לא, בודק מול הזיכרון.
        m_inc.insert(0, "אישור", m_inc['מקור התנועה'].isin(settings['approved_income']) if settings['approved_income'] else True)
        ed_inc = st.data_editor(m_inc, hide_index=True, key="inc_ed", column_config={"מקור התנועה": st.column_config.TextColumn(width="large")})
        
    with t2:
        m_exp = df_exp_raw[df_exp_raw['Month'] == sel_month].groupby('מקור התנועה')['סכום'].sum().abs().reset_index()
        m_exp.insert(0, "חסכון?", m_exp['מקור התנועה'].isin(settings['savings_list']))
        m_exp.insert(0, "אישור", m_exp['מקור התנועה'].isin(settings['approved_expenses']) if settings['approved_expenses'] else True)
        ed_exp = st.data_editor(m_exp, hide_index=True, key="exp_ed", column_config={"מקור התנועה": st.column_config.TextColumn(width="large")})

    with t3:
        m_c = df_c[df_c['Month'] == sel_month].groupby(['בית עסק', 'מטבע_מקור', 'שער'])['סכום'].sum().reset_index()
        m_c['קטגוריה'] = m_c['בית עסק'].apply(lambda x: get_initial_category(x, settings))
        m_c.insert(0, "תזרימי?", ~m_c['בית עסק'].isin(settings['excluded_credit']))
        ed_c = st.data_editor(m_c, hide_index=True, key="c_ed", 
                              column_config={
                                  "בית עסק": st.column_config.TextColumn(width="medium"),
                                  "קטגוריה": st.column_config.SelectboxColumn(options=CATEGORIES),
                                  "שער": st.column_config.NumberColumn(format="%.3f")
                              })

    if st.button("💾 שמור הגדרות"):
        # חישוב: מה שהיה בזיכרון, פחות מה שמוצג כרגע בטבלה, פלוס מה שסומן כעת
        settings['approved_income'] = list((set(settings['approved_income']) - set(m_inc['מקור התנועה'])) | set(ed_inc[ed_inc["אי
