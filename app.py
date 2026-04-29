import streamlit as st
import time

# --- 1. OFFICIAL PROJECT IDENTITY ---
OFFICIAL_PROJECT_TITLE = "DataMaster-DSS"
PROJECT_SUBTITLE = "Multi-Agent AI Decision Support System"

st.set_page_config(page_title=OFFICIAL_PROJECT_TITLE, layout="wide", page_icon="🤖")

# --- 2. CSS FOR PROFESSIONAL ENTERPRISE LOOK ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #0e1117; color: white; }
    .stChatMessage { border-radius: 10px; border: 1px solid #30363d; background-color: #161b22; }
    .agent-tag { 
        background-color: #1f6feb; color: white; padding: 2px 8px; 
        border-radius: 5px; font-size: 0.8em; font-weight: bold; margin-bottom: 10px; display: inline-block;
    }
    .citation-box {
        background-color: #0d1117; border-left: 3px solid #238636; 
        padding: 10px; margin-top: 15px; font-size: 0.85em; color: #8b949e;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. SIDEBAR & SETTINGS ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2103/2103633.png", width=70)
    st.title("Control Panel")
    lang = st.radio("System Interface Language", ["English", "العربية"])
    st.divider()
    st.info("Backend: Azure AI Foundry 🌐")
    st.info("Architecture: Multi-Agent RAG 🧠")

# Translation Dictionary
T = {
    "English": {
        "title": OFFICIAL_PROJECT_TITLE,
        "sub": PROJECT_SUBTITLE,
        "input": "Enter your organizational query here...",
        "thinking": "Orchestrating agents & retrieving data...",
        "source_title": "Sources & References:"
    },
    "العربية": {
        "title": "داتا ماستر - نظام دعم القرار",
        "sub": "نظام دعم قرار معزز بالذكاء الاصطناعي متعدد الوكلاء",
        "input": "أدخل استفسارك هنا...",
        "thinking": "جاري التنسيق بين الوكلاء واسترجاع البيانات...",
        "source_title": "المصادر والمرجعيات:"
    }
}[lang]

st.title(f" {T['title']}")
st.caption(T["sub"])

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"], unsafe_allow_html=True)

# --- 4. CORE LOGIC & SIMULATED RAG ---
if prompt := st.chat_input(T["input"]):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status(T["thinking"]) as status:
            time.sleep(1.5) # Simulate Orchestration
            p_low = prompt.lower()
            
            # --- ROUTING LOGIC ---
            if any(x in p_low for x in ["budget", "finance", "financial", "ميزانية"]):
                agent_name, agent_id = "Financial Analyst Agent", "FINANCE"
            elif any(x in p_low for x in ["hr", "leave", "policy", "hiring", "موظف"]):
                agent_name, agent_id = "HR Specialist Agent", "HR"
            else:
                agent_name, agent_id = "Master Orchestrator", "GENERAL"

            st.write(f"✅ Query routed to: **{agent_name}**")
            time.sleep(1)
            status.update(label="Analysis Complete", state="complete")

        # --- SIMULATED RESPONSE LOGIC ---
        # Note: In production, this calls Azure OpenAI with the prompt and retrieved context
        if agent_id == "FINANCE":
            response = "The 2024 budget allocation for the IT department is **SAR 2.5 Million**. 80% has been utilized for cloud infrastructure."
            sources = "Source: Finance_Report_Q1_2024.pdf (Page 12)"
        elif agent_id == "HR":
            response = "The Annual Leave policy allows for **30 calendar days** per year. Carry-over is limited to 15 days."
            sources = "Source: Employee_Handbook_v2.pdf (Section 4.1)"
        else:
            response = "I am the DataMaster Orchestrator. How can I assist you with your business data today?"
            sources = "System Documentation"

        # Final Formatting
        full_response = f"""
        <div class='agent-tag'>{agent_name}</div><br>
        {response}
        <div class='citation-box'>
            <strong>{T['source_title']}</strong><br>
            {sources}
        </div>
        """
        st.markdown(full_response, unsafe_allow_html=True)
        st.session_state.messages.append({"role": "assistant", "content": full_response})

st.divider()
st.caption("Graduation Project | MIS Department | © 2026")
