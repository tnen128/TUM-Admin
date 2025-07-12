
# 🧠 TUM Admin Document Generator

An AI-powered assistant for generating formal university documents such as announcements, student communications, and meeting summaries—designed specifically for administrative staff at TUM.

---

## 📌 Project Overview

Administrative staff often spend significant time drafting repetitive messages.  
This project leverages GPT-4 via the OpenAI API to automate the generation of:

- 📣 Announcements  
- 📬 Student messages (approvals, warnings, info notes)  
- 📝 Meeting summaries or official notices  

The system allows tone customization, supports editable previews, and provides quick export to PDF or Word formats.

---

## 🎯 Key Features

- **Tone Customization:** Neutral, Friendly, Polite, or Firm  
- **Document Types:** Announcement, Student Communication, Meeting Summary  
- **Language Options:** English, German (future support: Turkish, French)  
- **Editable Preview:** Modify output before export  
- **Export Formats:** PDF & Word  
- **Response History:** Review and reuse previous outputs  

---

## 🧑‍💻 Tech Stack

| Component     | Technology            |
|---------------|------------------------|
| Frontend      | Streamlit              |
| Backend       | Python + GPT-4 API     |
| Deployment    | Docker (containerized) |

---

## 🚀 Quick Start

1. **Clone the Repository**
```bash
git clone https://github.com/yourusername/TUM-Admin.git
cd TUM-Admin
````

2. **Set up API Key**
   Create a `.env` file:

```bash
OPENAI_API_KEY=your_openai_key_here
```

3. **Run Locally with Streamlit**

```bash
pip install -r requirements.txt
streamlit run app.py
```

4. **Access the App**
   Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 📈 Impact Metrics

| Metric                      | Value                    |
| --------------------------- | ------------------------ |
| Avg. Document Generation    | < 20 seconds             |
| Estimated Weekly Time Saved | \~2–3 hours per staff    |
| User Satisfaction Score     | 4.7 / 5 (pilot feedback) |

---

## 📷 Demo Preview

<img src="assets/interface_demo.png" width="700">

---

## 📌 Example Use Case

> “Write an announcement to inform students about the extension of registration deadline until Oct 15. Use friendly tone.”

📤 Output:

> "Dear Students,
> We’re happy to inform you that the registration deadline has been extended until October 15..."

---

## 🤝 Authors

* Ahmet Cemil Yazıcı
* Pelin Elbin Günay
* Banu Uygun
* Mohammed Ezzat
* Yiğit Ertör
* Ramazan Tuncel

📍 TUM – School of Computation, Information and Technology
🗓️ July 2025

