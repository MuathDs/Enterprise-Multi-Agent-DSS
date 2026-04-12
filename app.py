import streamlit as st
import time

# --- 1. إعدادات الهوية الرسمية (تعديل العنوان هنا) ---
# ملاحظة: ضع عنوانك المسجل في الجامعة هنا حرفياً
OFFICIAL_PROJECT_TITLE = "ضع هنا عنوان مشروعك الرسمي المعتمد في الجامعة"

st.set_page_config(page_title=OFFICIAL_PROJECT_TITLE, layout="wide", page_icon="🏢")

# --- 2. سحب مفاتيح الأمان (Security First) ---
# ملاحظة: الكود بيبحث عن هذي القيم في ملف secrets.toml اللي بجهازك أو في إعدادات Cloud
# إذا ما كنت رابط Azure حالياً، الكود بيكمل بنظام "المحاكاة الذكية" بدون ما ينهار
try:
    AZURE_OPENAI_KEY = st.secrets["AZURE_OPENAI_KEY"]
    AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
    CONNECTION_TYPE = "LIVE"
except:
    CONNECTION_TYPE = "SIMULATED"

# --- 3. التنسيق الجمالي (CSS) ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Cairo', sans-serif; text-align: right; }}
    .main {{ background-color: #0e1117; color: white; }}
    .stChatMessage {{ border-radius: 12px; border: 1px solid #30363d; margin-bottom: 15px; background-color: #161b22; }}
    .agent-header {{ color: #58a6ff; font-weight: bold; font-size: 0.9em; margin-bottom: 5px; }}
    </style>
    """, unsafe_allow_html=True)

# --- 4. إدارة اللغات والواجهة ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3061/3061341.png", width=80)
    st.title("الإعدادات / Settings")
    lang = st.radio("Language / اللغة", ["العربية", "English"])
    st.divider()
    st.success(f"Mode: {CONNECTION_TYPE} 🟢")

T = {
    "العربية": {
        "title": OFFICIAL_PROJECT_TITLE,
        "sub": "إصدار متطور معزز بالوكلاء المتعددين - شركة معاذ لتقنية المعلومات",
        "input": "اسأل النظام عن الميزانية، التوظيف، الأمن، أو العقود...",
        "thinking": "جاري استشارة الوكلاء وفحص قواعد البيانات...",
        "dir": "rtl"
    },
    "English": {
        "title": OFFICIAL_PROJECT_TITLE,
        "sub": "Advanced Multi-Agent Edition - Muath IT Solutions",
        "input": "Ask about budget, hiring, security, or legal contracts...",
        "thinking": "Consulting specialized agents...",
        "dir": "ltr"
    }
}[lang]

st.title(f"🚀 {T['title']}")
st.caption(T["sub"])

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 5. منطق الذكاء والتوجيه (Core Logic) ---
if prompt := st.chat_input(T["input"]):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status(T["thinking"]) as status:
            time.sleep(1)
            p_low = prompt.lower()
            
            # مصفوفة التوجيه (Routing Logic)
            if any(x in p_low for x in ["ميزانية", "budget", "ريال", "مالية"]):
                agent, tag = ("الوكيل المالي", "Finance Agent"), "[Finance]"
            elif any(x in p_low for x in ["موظف", "توظيف", "hr", "راتب"]):
                agent, tag = ("مدير الموارد البشرية", "HR Manager"), "[HR]"
            elif any(x in p_low for x in ["أمن", "it", "تقنية", "security"]):
                agent, tag = ("خبير الأمن التقني", "IT Expert"), "[IT]"
            elif any(x in p_low for x in ["محامي", "قانون", "عقد", "legal"]):
                agent, tag = ("المستشار القانوني", "Legal Consultant"), "[Legal]"
            else:
                agent, tag = ("المساعد العام", "General Assistant"), "[General]"
            
            disp_agent = agent[0] if lang == "العربية" else agent[1]
            st.write(f"✅ تم التوجيه إلى: **{disp_agent}**")
            time.sleep(0.5)
            status.update(label="Complete / اكتمل", state="complete")

        # صياغة الرد (هنا يتم الربط بـ Azure مستقبلاً عبر AZURE_OPENAI_KEY)
        if "[Finance]" in tag:
            ans = "الميزانية المتوفرة هي 2.5 مليون ريال." if lang == "العربية" else "Total budget is 2.5M SAR."
        elif "[HR]" in tag:
            ans = "الحاجة الحالية هي 3 مهندسين ذكاء اصطناعي." if lang == "العربية" else "We need 3 AI Engineers."
        elif "[IT]" in tag:
            ans = "نظام الأمن مشفر بالكامل وتحت حماية Azure." if lang == "العربية" else "Security is fully encrypted on Azure."
        else:
            ans = "كيف يمكنني مساعدتك في إدارة شركة معاذ اليوم؟" if lang == "العربية" else "How can I assist you today?"

        st.markdown(f"<div class='agent-header'>{disp_agent}:</div>", unsafe_allow_html=True)
        st.markdown(ans)
        st.session_state.messages.append({"role": "assistant", "content": f"**{disp_agent}:** {ans}"})

st.divider()
st.caption("Graduation Project - MIS Department © 2026")
