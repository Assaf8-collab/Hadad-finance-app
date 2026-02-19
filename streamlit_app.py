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
        "excluded_credit": [],
        "hard_income_list": [],    # זיכרון להכנסות קשיחות
        "hard_expense_list": []    # זיכרון להוצאות קשיחות (בנק ואשראי)
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for key in default_settings:
                    if key not in data: data[key] = default_settings[key]
                return data
        except: return default_settings
    return default_settings

def save_settings(settings_dict):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings_dict, f, ensure_ascii=False, indent=4)

# --- 2. מנוע סיווג, המרות וחישובי תאריכים ---
CATEGORIES = ['אחר', 'קניות סופר', 'רכב', 'ביטוח', 'ביגוד', 'אוכל בחוץ', 'בילויים', 'מגורים ואחזקה', 'חסכון והשקעות', 'מסגרות וחינוך']

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
        except: pass
    
    rates = {'EUR': 4.1, 'USD': 3.7}
    fallback_rate = rates.get(curr, 1.0)
    return amt * fallback_rate, fallback_rate

def get_initial_category(desc, settings):
    desc_str = str(desc)
    if desc_str in settings.get('savings_list', []): return 'חסכון והשקעות'
    if desc_str in settings.get('credit_categories', {}): return settings['credit_categories'][desc_str]
    
    mapping = {
        'קניות סופר': ['שופרסל', 'הכל כאן', 'יוחננוף', 'קשת טעמים', 'רמי לוי', 'ויקטורי', 'מחסני השוק', 'am:pm', 'טיב טעם'],
        'אוכל בחוץ': ['מסעדה', 'קפה', 'וולט', 'wolt', 'מקדונלד', 'פיצה', 'בורגר', 'גלידה'],
        'רכב': ['פנגו', 'pango', 'פז', 'סונול', 'דור אלון', 'חניון', 'דלק', 'מוסך', 'כביש 6'],
        'ביגוד': ['זארה', 'zara', 'h&m', 'טרמינל', 'terminal', 'פוקס', 'fox', 'קסטרו'],
        'בילויים': ['קולנוע', 'סינמה', 'תיאטרון', 'הופעה', 'זאפה'],
        'ביטוח': ['ביטוח', 'הראל', 'מגדל', 'כלל', 'הפניקס', 'שירביט'],
        'מגורים ואחזקה': ['ארנונה', 'חשמל', 'ועד בית', 'מי שבע', 'גז', 'מים'],
        'מסגרות וחינוך': ['גן', 'בית ספר', 'צהרון', 'מעון', 'חוג', 'מתנס']
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
        
        date_col = 'תאריך'
        if 'יום ערך' in df_b.columns:
            date_col = 'יום ערך'
        elif 'תאריך ערך' in df_b.columns:
            date_col = 'תאריך ערך'
            
        df_b['תאריך_קובע'] = pd.to_datetime(df_b[date_col], dayfirst=True, errors='coerce')
        if 'תאריך' in df_b.columns and date_col != 'תאריך':
            df_b['תאריך_קובע'] = df_b['תאריך_קובע'].fillna(pd.to_datetime(df_b['תאריך'], dayfirst=True, errors='coerce'))
            
        df_b['סכום'] = df_b['₪ זכות/חובה '].apply(lambda x: clean_and_detect_currency(x)[0])
        df_b = df_b.dropna(subset=['תאריך_קובע']).rename(columns={'תיאור התנועה': 'מקור התנועה'})
        
        df_b['Month'] = df_b['תאריך_קובע'].dt.to_period('M')
        
        detailed_cards = ['1723', '1749', '1097']
        is_detailed_cc = df_b['מקור התנועה'].str.contains('|'.join(detailed_cards), na=False)
        
        df_inc_raw = df_b[df_b['סכום'] > 0].copy()
        df_exp_raw = df_b[(df_b['סכום'] < 0) & (~is_detailed_cc)].copy()
    except Exception as e:
        st.error(f"שגיאה בעיבוד קובץ העו\"ש. פירוט: {e}")
        st.stop()

    # --- ב. עיבוד אשראי ---
    try:
        df_c_raw = pd.read_csv(credit_up, skiprows=8)
        
        col_h = 'תאריך החיוב' if 'תאריך החיוב' in df_c_raw.columns else ('תאריך חיוב' if 'תאריך חיוב' in df_c_raw.columns else df_c_raw.columns[7])
        col_i = 'סכום החיוב' if 'סכום החיוב' in df_c_raw.columns else ('סכום חיוב' if 'סכום חיוב' in df_c_raw.columns else df_c_raw.columns[8])
        
        c_processed = []
        for _, row in df_c_raw.iterrows():
            val = row[col_i]
            amt, curr = clean_and_detect_currency(val)
            
            tx_date = pd.to_datetime(row.get('תאריך עסקה', row[col_h]), dayfirst=True, errors='coerce')
            ils_amt, rate = get_exchange_info(amt, curr, tx_date)
            
            bill_date = pd.to_datetime(row[col_h], dayfirst=True, errors='coerce')
            
            c_processed.append({
                'תאריך חיוב': bill_date, 
                'בית עסק': row.get('בית עסק', 'לא ידוע'), 
                'סכום': ils_amt, 
                'מטבע_מקור': curr, 
                'שער': rate,
                'Month': bill_date.to_period('M') if not pd.isna(bill_date) else None
            })
        
        df_c = pd.DataFrame(c_processed).dropna(subset=['Month'])
    except Exception as e:
        st.error(f"שגיאה בעיבוד קובץ האשראי. פירוט: {e}")
        st.stop()

    # --- ג. ממשק מיון וסיווג (שלב 1) ---
    curr_m = pd.Timestamp.now().to_period('M')
    
    all_months = set(df_b['Month'].dropna().unique()).union(set(df_c['Month'].dropna().unique()))
    available_months = sorted([m for m in all_months if m <= curr_m], reverse=True)
    
    st.divider()
    if available_months:
        sel_month = st.selectbox("בחר חודש לסיווג תנועות:", available_months)
        st.subheader(f"🛠️ שלב 1: אישור וסיווג - {sel_month}")
        
        t1, t2, t3 = st.tabs(["🏦 הכנסות", "📉 הוצאות בנק (וחיוב כרטיסים אחרים)", "💳 הוצאות אשראי מפורטות"])
        
        with t1:
            m_inc = df_inc_raw[df_inc_raw['Month'] == sel_month].groupby('מקור התנועה')['סכום'].sum().reset_index()
            m_inc.insert(0, "הכנסה קשיחה?", m_inc['מקור התנועה'].isin(settings['hard_income_list']))
            m_inc.insert(0, "אישור", m_inc['מקור התנועה'].isin(settings['approved_income']) if settings['approved_income'] else True)
            ed_inc = st.data_editor(m_inc, hide_index=True, key="inc_ed", column_config={"מקור התנועה": st.column_config.TextColumn(width="large")})
            
        with t2:
            m_exp = df_exp_raw[df_exp_raw['Month'] == sel_month].groupby('מקור התנועה')['סכום'].sum().abs().reset_index()
            m_exp.insert(0, "הוצאה קשיחה?", m_exp['מקור התנועה'].isin(settings['hard_expense_list']))
            m_exp.insert(0, "חסכון?", m_exp['מקור התנועה'].isin(settings['savings_list']))
            m_exp.insert(0, "אישור", m_exp['מקור התנועה'].isin(settings['approved_expenses']) if settings['approved_expenses'] else True)
            ed_exp = st.data_editor(m_exp, hide_index=True, key="exp_ed", column_config={"מקור התנועה": st.column_config.TextColumn(width="large")})

        with t3:
            m_c = df_c[df_c['Month'] == sel_month].groupby(['בית עסק', 'מטבע_מקור', 'שער'], dropna=False)['סכום'].sum().reset_index()
            m_c['קטגוריה'] = m_c['בית עסק'].apply(lambda x: get_initial_category(x, settings))
            m_c.insert(0, "הוצאה קשיחה?", m_c['בית עסק'].isin(settings['hard_expense_list']))
            m_c.insert(0, "תזרימי?", ~m_c['בית עסק'].isin(settings['excluded_credit']))
            ed_c = st.data_editor(m_c, hide_index=True, key="c_ed", 
                                  column_config={
                                      "בית עסק": st.column_config.TextColumn(width="medium"),
                                      "קטגוריה": st.column_config.SelectboxColumn(options=CATEGORIES),
                                      "שער": st.column_config.NumberColumn(format="%.3f")
                                  })

        if st.button("💾 שמור הגדרות"):
            # עדכון רשימות אישור וחסכון
            settings['approved_income'] = list((set(settings['approved_income']) - set(m_inc['מקור התנועה'])) | set(ed_inc[ed_inc["אישור"]]['מקור התנועה']))
            settings['approved_expenses'] = list((set(settings['approved_expenses']) - set(m_exp['מקור התנועה'])) | set(ed_exp[ed_exp["אישור"]]['מקור התנועה']))
            settings['savings_list'] = list((set(settings['savings_list']) - set(m_exp['מקור התנועה'])) | set(ed_exp[ed_exp["חסכון?"]]['מקור התנועה']))
            
            # עדכון רשימות הוצאות/הכנסות קשיחות
            settings['hard_income_list'] = list((set(settings['hard_income_list']) - set(m_inc['מקור התנועה'])) | set(ed_inc[ed_inc["הכנסה קשיחה?"]]['מקור התנועה']))
            all_displayed_exp = set(m_exp['מקור התנועה']) | set(m_c['בית עסק'])
            curr_hard_exp = set(ed_exp[ed_exp["הוצאה קשיחה?"]]['מקור התנועה']) | set(ed_c[ed_c["הוצאה קשיחה?"]]['בית עסק'])
            settings['hard_expense_list'] = list((set(settings['hard_expense_list']) - all_displayed_exp) | curr_hard_exp)
            
            # עדכון קטגוריות אשראי
            for _, row in ed_c.iterrows():
                settings['credit_categories'][row['בית עסק']] = row['קטגוריה']
                if not row['תזרימי?']: 
                    if row['בית עסק'] not in settings['excluded_credit']: settings['excluded_credit'].append(row['בית עסק'])
                elif row['בית עסק'] in settings['excluded_credit']: 
                    settings['excluded_credit'].remove(row['בית עסק'])
            
            save_settings(settings)
            st.success("ההגדרות נשמרו בהצלחה!")
            st.rerun()

        # --- ד. סיכום התזרים ---
        st.divider()
        
        f_inc = df_inc_raw[df_inc_raw['מקור התנועה'].isin(settings['approved_income']) if settings['approved_income'] else [True]*len(df_inc_raw)]
        f_bank_exp = df_exp_raw[df_exp_raw['מקור התנועה'].isin(settings['approved_expenses']) if settings['approved_expenses'] else [True]*len(df_exp_raw)]
        
        f_credit = df_c[~df_c['בית עסק'].isin(settings['excluded_credit'])].copy()
        f_credit['קטגוריה'] = f_credit['בית עסק'].apply(lambda x: get_initial_category(x, settings))

        summary = pd.DataFrame({
            'הכנסות': f_inc.groupby('Month')['סכום'].sum(),
            'הוצאות בנק (ללא 1723,1749,1097)': f_bank_exp.groupby('Month')['סכום'].sum().abs(),
            'הוצאות אשראי (מפורטות)': f_credit.groupby('Month')['סכום'].sum()
        }).fillna(0)
        
        summary_past = summary[summary.index < curr_m].copy()
        
        if not summary_past.empty:
            summary_past['סה"כ הוצאות'] = summary_past['הוצאות בנק (ללא 1723,1749,1097)'] + summary_past['הוצאות אשראי (מפורטות)']
            summary_past['נטו לתזרים'] = summary_past['הכנסות'] - summary_past['סה"כ הוצאות']
            
            st.subheader("📊 שלב 2: סיכום תזרים מזומנים (חודשים מלאים)")
            st.table(summary_past.sort_index(ascending=False).style.format("₪{:,.0f}"))

            if available_months:
                st.subheader(f"🔍 שלב 3: התפלגות הוצאות ותקציב בסיס - {sel_month}")
                
                # --- חישוב תקציב קשיח (בסיס) ---
                st.markdown("##### 📌 תקציב קשיח (בסיס)")
                
                hard_inc_sum = f_inc[(f_inc['Month'] == sel_month) & (f_inc['מקור התנועה'].isin(settings['hard_income_list']))]['סכום'].sum()
                hard_bank_sum = f_bank_exp[(f_bank_exp['Month'] == sel_month) & (f_bank_exp['מקור התנועה'].isin(settings['hard_expense_list']))]['סכום'].sum()
                hard_credit_sum = f_credit[(f_credit['Month'] == sel_month) & (f_credit['בית עסק'].isin(settings['hard_expense_list']))]['סכום'].sum()
                total_hard_exp = hard_bank_sum + hard_credit_sum
                
                c_hard1, c_hard2, c_hard3 = st.columns(3)
                c_hard1.metric("הכנסות קשיחות (משכורת וכו')", f"₪{hard_inc_sum:,.0f}")
                c_hard2.metric("הוצאות קשיחות (חובה)", f"₪{total_hard_exp:,.0f}")
                c_hard3.metric("הכנסה פנויה (אחרי חובה)", f"₪{hard_inc_sum - total_hard_exp:,.0f}")
                
                st.markdown("---")
                
                # --- גרף חלוקה לקטגוריות ---
                c_cat = f_credit[f_credit['Month'] == sel_month][['קטגוריה', 'סכום']]
                b_cat = f_bank_exp[f_bank_exp['Month'] == sel_month].copy()
                b_cat['קטגוריה'] = b_cat['מקור התנועה'].apply(lambda y: 'חסכון והשקעות' if y in settings['savings_list'] else 'אחר')
                b_cat = b_cat[['קטגוריה', 'סכום']]
                
                combined_cats = pd.concat([c_cat, b_cat]).groupby('קטגוריה')['סכום'].sum().sort_values(ascending=False)

                col_chart, col_data = st.columns([2, 1])
                with col_chart:
                    st.bar_chart(combined_cats)
                with col_data:
                    if 'חסכון והשקעות' in combined_cats:
                        st.metric("סכום שנחסך החודש", f"₪{combined_cats['חסכון והשקעות']:,.0f}")
                        total_income_month = summary.loc[sel_month, 'הכנסות'] if sel_month in summary.index else 0
                        if total_income_month > 0:
                            st.metric("שיעור חסכון מתוך כלל ההכנסות", f"{(combined_cats['חסכון והשקעות'] / total_income_month * 100):.1f}%")
                    
                    st.write(combined_cats.map("₪{:,.0f}".format))
