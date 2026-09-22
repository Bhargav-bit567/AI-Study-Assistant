# PythonAnywhere Deployment Guide for AI Study Assistant

## 1. Sign up / Log in
- Go to https://www.pythonanywhere.com/
- Create a free account or log in

## 2. Open a Bash console
- Go to **Consoles** → **Bash**

## 3. Clone the repository
```bash
cd ~
git clone https://github.com/Bhargav-bit567/AI-Study-Assistant.git
cd AI-Study-Assistant
```

## 4. Create a virtual environment and install dependencies
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 5. Create the .env file
```bash
nano .env
```
Paste your environment variables:
```
AZURE_AI_ENDPOINT=https://ai-study-assistant-resource.services.ai.azure.com/api/projects/ai-study-assistant
AZURE_OPENAI_ENDPOINT=https://ai-study-assistant-resource.services.ai.azure.com/api/projects/ai-study-assistant/openai/v1/
AZURE_AI_API_KEY=your-azure-key
AZURE_AI_AGENT_NAME=AI-Study-Assistant
AZURE_AI_AGENT_VERSION=2
AZURE_MODEL_DEPLOYMENT=gpt-5-mini
SUPABASE_URL=https://posrgyifwrohogqcacpt.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
JWT_SECRET_KEY=your-jwt-secret
```
Press `Ctrl+O`, `Enter`, `Ctrl+X` to save and exit.

## 6. Configure the Web App
- Go to **Web** → **Add a new web app**
- Choose **Manual configuration** → **Python 3.12**
- Set the working directory to `/home/yourusername/AI-Study-Assistant`
- Set the WSGI configuration file to use `/home/yourusername/AI-Study-Assistant/wsgi.py`
- In the WSGI file, make sure it points to:
  ```python
  from wsgi import application
  ```

## 7. Set environment variables in PythonAnywhere
Go to **Web** → your app → **WSGI configuration file** or set them in the **Web** tab under **Environment variables**.

Alternatively, the app will read them from `.env` if present.

## 8. Reload the web app
- Click the **Reload** button
- Visit your app at `https://yourusername.pythonanywhere.com`

## Notes
- Free tier: app sleeps after 3 months of inactivity
- File upload limit: 32 MB total request size
- Static files are served automatically by FastAPI
