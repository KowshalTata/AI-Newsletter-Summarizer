# AI-Newsletter-Summarizer

Local Gmail email summarizer with a simple web UI.  
Flow: list **today’s senders** → select → confirm → summaries appear.

## 1) Requirements
- Python 3.10+
- A Gmail account
- OpenAI API key

Install dependencies:
```bash
pip install -r requirements.txt
```

## 2) OpenAI API Key
Create an API key in your OpenAI account and store it in `.env`.

Create a `.env` file in the project root:
```
OPENAI_API_KEY=your_openai_api_key_here
```

You can copy `.env.example` and fill in your key.

## 3) Gmail Access (SimpleGmail)
This project uses `simplegmail` for Gmail access.

Steps:
1. Create a Google Cloud project.
2. Enable the **Gmail API**.
3. Create **OAuth Client ID** credentials (Desktop App).
4. Download the credentials JSON and save it as `client_secret.json` in the project root.
5. Run the app; you’ll be prompted to log in and authorize.  
   A token file `gmail_token.json` will be created automatically.

**Important:** Do not commit your `client_secret.json` or `gmail_token.json`.  
They are ignored by `.gitignore`.

## 4) Run the App
```bash
python app.py
```
Open `http://localhost:5000`.

## How It Works
1. The UI shows all **senders from today** (or the last 24 hours if none match today exactly).
2. You select senders and click **Summarize Selected**.
3. Each selected email is summarized with OpenAI.
4. Summaries are cached locally in `local_data/newsletters/` and won’t be re-sent to OpenAI on future runs.

## Local Storage
Each email is stored as a JSON file:
```
local_data/
  newsletters/
    <message_id>.json
```

## Common Issues
- **OpenAI quota error**: add billing or use a different API key.
- **Gmail invalid_grant**: delete `gmail_token.json` and re-authenticate.
- **No senders showing**: make sure you have emails today; the UI falls back to last 24 hours if none match.

## Security Notes
Never commit:
- `.env`
- `client_secret.json`
- `gmail_token.json`

They are already ignored by `.gitignore`.
