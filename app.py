import streamlit as st
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from dotenv import load_dotenv

# 1. تحميل المتغيرات البيئية (تأكد أن ملف .env في نفس المجلد)
load_dotenv()

# 2. إعدادات الصفحة
st.set_page_config(page_title="Strategic AI Dashboard", layout="wide", page_icon="🤖")

# --- الإعدادات التقنية لشركة معاذ الرقمية ---
endpoint = "https://muath-ds-0446-resource.services.ai.azure.com/api/projects/muath-ds-0446"

# تهيئة الاتصال (تأكد من عمل az login في التيرمينال أولاً)
try:
    project_client = AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
    )
    openai_client = project_client.get_openai_client()
except Exception as e:
    st.error(f"خطأ في الاتصال بأزور: {e}")
    st.stop()

# --- خريطة الوكلاء (The Agents Mapping) ---
agents_config = {
    "المنسق (DataMaster)": {"name": "DataMaster-DSS", "version": "1"},
    "المدير التنفيذي (CEO)": {"name": "Strategic-CEO-Agent", "version": "2"},
    "المحلل المالي (Finance)": {"name": "Financial-Analyst-Agent", "version": "2"},
    "الموارد البشرية (HR)": {"name": "HR-Talent-Agent", "version": "2"}
}

# --- الواجهة الجانبية (Sidebar) ---
with st.sidebar:
    st.header("🏢 إدارة الأقسام")
    choice = st.selectbox(
        "اختر المستشار الإداري:",
        list(agents_config.keys())
    )
    
    selected_agent = agents_config[choice]
    
    st.markdown("---")
    st.info(f"📍 أنت الآن متصل بـ: **{selected_agent['name']}**")
    st.caption(f"الإصدار الفعلي: {selected_agent['version']}")
    
    if st.button("🗑️ مسح المحادثة"):
        st.session_state.messages = []
        st.rerun()

# --- الواجهة الرئيسية ---
st.title(f"🤖 نظام {choice}")
st.write(f"مرحباً بك في وحدة دعم القرار - تحت إشراف المهندس معاذ")

# إدارة ذاكرة المحادثة (Session State)
if "messages" not in st.session_state:
    st.session_state.messages = []

# عرض الرسائل القديمة
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# استقبال سؤال المستخدم
if prompt := st.chat_input("سجل استفسارك الإداري هنا..."):
    # إضافة سؤال المستخدم للذاكرة والعرض
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # طلب الرد من الوكيل المحدد في أزور
    with st.chat_message("assistant"):
        with st.spinner("جاري تحليل البيانات..."):
            try:
                response = openai_client.responses.create(
                    input=[{"role": "user", "content": prompt}],
                    extra_body={
                        "agent_reference": {
                            "name": selected_agent["name"],
                            "version": selected_agent["version"],
                            "type": "agent_reference"
                        }
                    },
                )
                
                answer = response.output_text
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
            except Exception as e:
                st.error(f"حدث خطأ أثناء استدعاء الوكيل: {e}")