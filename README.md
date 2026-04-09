# Enterprise Multi-Agent Decision Support System (DSS)

## 🚀 Overview
This project demonstrates an advanced **Multi-Agent Orchestration** architecture designed for corporate environments. It utilizes a central **Orchestrator (Manager Agent)** to analyze user intent and dynamically route queries to specialized **Sub-Agents** (HR, Finance, and IT).

## 🏗️ System Architecture
The system is built on a "Decoupled Logic" principle to ensure data security and operational efficiency:
- **Orchestrator Node:** Acts as a router, classifying the input and managing the workflow.
- **Specialized Agents:** Independent agents with specific system prompts and domain-focused knowledge.
- **RAG Integration:** Each agent is designed to interact with its own isolated vector database (Retrieval-Augmented Generation).

## 🛠️ Tech Stack
- **Engine:** Azure OpenAI (GPT-4o)
- **Framework:** Streamlit (Frontend Interface)
- **Orchestration:** Azure Foundry Workflows Logic
- **Security:** Environment variable masking via `python-dotenv`

## 🔒 Security & Data Privacy
**Note:** For confidentiality and compliance reasons, the internal datasets (CSV/PDF files) and API Credentials have been excluded from this repository. The code demonstrates the **Architectural Logic** and **Agent Mapping** rather than the raw data.

## 📁 Repository Structure
- `app.py`: The core application and UI logic.
- `requirements.txt`: Necessary dependencies to replicate the environment.
- `.gitignore`: Ensures sensitive environment files are not exposed.
