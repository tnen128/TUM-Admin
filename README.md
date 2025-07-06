# TUM Admin Assistant (Flat Structure for Streamlit Cloud)

## Overview
This is a reorganized, flat version of the TUM Admin Assistant project, suitable for deployment on Streamlit Community Cloud.

## How to Run Locally
1. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
2. Set your environment variables in a `.env` file or use Streamlit secrets for deployment.
3. Run the Streamlit app:
   ```sh
   streamlit run streamlit_app.py
   ```

## Streamlit Cloud Deployment
- Place your API keys and backend URL in the Streamlit Cloud secrets UI:
  ```toml
  GOOGLE_API_KEY = "your_gemini_api_key_here"
  BACKEND_URL = "https://your-backend-url.com"
  ```
- The app will use these secrets automatically.

## Project Structure
- `streamlit_app.py` — Main Streamlit entry point
- `llm_service.py`, `export_service.py`, `document_models.py`, etc. — All logic and models in the root directory 