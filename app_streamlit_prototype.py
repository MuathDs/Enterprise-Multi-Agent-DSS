import streamlit as st
import time

# --- 1. إعدادات الصفحة والجماليات (CSS) ---
st.set_page_config(page_title="Muath IT - DSS", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Cairo', sans-serif; }
    .main { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .agent-tag { background-color: #e1f5fe; color: #01579b; padding: 2px 8px; border-radius: 5px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. قاموس اللغات (Bilingual Dictionary) ---
TEXTS = {
    "العربية": {
        "title": "مركز قيادة شركة معاذ لتقنية المعلومات",
        "sub": "نظام دعم اتخاذ القرار الذكي | Multi-Agent DSS",
        "lang_label": "اختر اللغة",
        "input_placeholder": "اسأل عن الميزانية، التوظيف، الأمن، أو العقود القانونية...",
        "status_thinking": "جاري استشارة الوكيل المختص وفحص قواعد البيانات...",
        "routed_to": "🎯 الوكيل النشط حالياً:",
        "footer": "مشروع تخرج - قسم نظم المعلومات الإدارية (MIS) © 2026",
        "dir": "rtl"
    },
    "English": {
        "title": "Muath IT Command Center",
        "sub": "Intelligent Decision Support System | Multi-Agent DSS",
        "lang_label": "Select Language",
        "input_placeholder": "Ask about budget, hiring, security, or legal contracts...",
        "status_thinking": "Consulting specialized agent and scanning databases...",
        "routed_to": "🎯 Currently Active Agent:",
        "footer": "Graduation Project - MIS Department © 2026",
        "dir": "ltr"
    }
}

# --- 3. الشريط الجانبي ---
with st.sidebar:
    st.header("⚙️ Settings")
    selected_lang = st.radio("Language", ["العربية", "English"], index=0)
    T = TEXTS[selected_lang]
    st.divider()
    st.info("System Status: Online 🟢\nCloud: Azure AI Ready")

# --- 4. واجهة المستخدم الرئيسية ---
st.title(T["title"])
st.caption(T["sub"])

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 5. منطق المعالجة والذكاء (The Intelligence Logic) ---
if prompt := st.chat_input(T["input_placeholder"]):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status(T["status_thinking"]) as status:
            time.sleep(1)
            p_low = prompt.lower()
            
            # --- مصفوفة توجيه الوكلاء (Agent Routing Matrix) ---
            if any(x in p_low for x in ["ميزانية", "budget", "فلوس", "مالية", "ريال"]):
                agent, tag = "Finance", "[Finance]"
            elif any(x in p_low for x in ["موظف", "راتب", "hr", "توظيف", "salary"]):
                agent, tag = "HR", "[HR]"
            elif any(x in p_low for x in ["قرار", "strategy", "ceo", "استراتيجية", "رؤية"]):
                agent, tag = "CEO", "[CEO]"
            elif any(x in p_low for x in ["قانون", "محامي", "عقد", "legal", "نظام", "امتثال"]):
                agent, tag = "Legal", "[Legal]"
            elif any(x in p_low for x in ["أمن", "معلومات", "it", "تقنية", "سيرفر", "security", "اختراق"]):
                agent, tag = "IT", "[IT]"
            elif any(x in p_low for x in ["سلاسل", "إمداد", "ops", "عمليات", "لوجستي", "مخزن"]):
                agent, tag = "Ops", "[Ops]"
            elif any(x in p_low for x in ["سوق", "مبيعات", "sales", "منافسين"]):
                agent, tag = "Sales", "[Sales]"
            else:
                agent, tag = "General Assistant", "[General]"
            
            st.write(f"{T['routed_to']} <span class='agent-tag'>{agent}</span>", unsafe_allow_html=True)
            time.sleep(0.5)
            status.update(label="Response Generated!", state="complete", expanded=False)

        # --- توليد الرد بناءً على القسم المختص ---
        if agent == "Finance":
            col1, col2 = st.columns(2)
            col1.metric("Total Budget", "2,500,000 SAR")
            col2.metric("IT Allocation", "600,000 SAR")
            ans = "بناءً على التقرير المالي لشركة معاذ، الميزانية المعتمدة للربع الأول هي 2.5 مليون ريال." if selected_lang == "العربية" else "Based on Muath IT Q1 report, the approved budget is 2.5M SAR."
        
        elif agent == "HR":
            ans = "سياسة التوظيف الحالية تتطلب 3 مهندسين ذكاء اصطناعي براتب أساسي 12,000 ريال." if selected_lang == "العربية" else "Current hiring policy requires 3 AI Engineers with a 12,000 SAR base salary."
            
        elif agent == "IT":
            ans = "نظام أمن المعلومات مفعل. جاري تحديث جدار الحماية (Firewall) وتجديد تراخيص Azure." if selected_lang == "العربية" else "IT Security is active. Updating Firewall and renewing Azure licenses."
            
        elif agent == "Legal":
            ans = "جميع العقود الحالية متوافقة مع نظام العمل السعودي الجديد لسنة 2026." if selected_lang == "العربية" else "All current contracts comply with the new 2026 Saudi Labor Law."
            
        elif agent == "Ops":
            ans = "خطة تجهيز فرع أبها الجديد تسير وفق الجدول الزمني، والميزانية المحددة 400 ألف ريال." if selected_lang == "العربية" else "Abha branch setup is on schedule with a 400k SAR budget."
            
        elif agent == "Sales":
            ans = "نستهدف الاستحواذ على 15% من حصة السوق في المنطقة الجنوبية بنهاية العام." if selected_lang == "العربية" else "Targeting 15% market share in the Southern Region by year-end."
            
        else:
            ans = "أنا المساعد العام لشركة معاذ، كيف يمكنني خدمتك اليوم؟" if selected_lang == "العربية" else "I am Muath IT General Assistant, how can I help you today?"

        st.markdown(ans)
        st.session_state.messages.append({"role": "assistant", "content": ans})

# --- 6. التذييل ---
st.divider()
st.markdown(f"<div style='text-align: center; color: gray; direction: {T['dir']};'>{T['footer']}</div>", unsafe_allow_html=True)