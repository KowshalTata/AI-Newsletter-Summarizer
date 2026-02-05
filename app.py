import json
import os
import re
from datetime import datetime, date, time
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, render_template, request
from openai import OpenAI
from simplegmail import Gmail
from simplegmail.query import construct_query

# Load variables from .env file
load_dotenv()

# OpenAI
openai_api_key = os.environ.get("OPENAI_API_KEY")
openai_client = OpenAI(api_key=openai_api_key)
gpt_model = "gpt-3.5-turbo-0125"

personality_env = """Generate a short, well-structured summary script based on the provided email content. Provide an engaging and clear narrative, similar to a professional analyst. Ensure the response is suitable for narration through a Text-to-Speech (TTS) system API. The goal is to deliver informative content with a conversational tone, drawing exclusively from the provided email content and without incorporating outside knowledge.
Please note:
- Do not include any stage directions such as [Opening Music], [Transition Music], [Host]. Those will be manually added as per the requirements into the TTS generated audio file.
- Keep it short and informative by limiting the response to a few points, covering all the highlights from the topic, so that users listening to this as a voice clip will stay attentive to details and will not be irritated."""

tag_gen_env = """Generate concise and engaging keyword tags for an email summary, offering users a preview of the content. Craft tags based on the provided summary to create an enticing snapshot. Each highlight should be represented by a single tag. Format: #tag."""

# Local storage
DATA_DIR = Path("local_data")
NEWS_DIR = DATA_DIR / "newsletters"
DATA_DIR.mkdir(exist_ok=True)
NEWS_DIR.mkdir(exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")


def extract_name_from_sender(sender_str):
    sender_replacements = {
        "Mike Allen": "Axios AM PM",
        "Kia Kokalitcheva": "Axios Pro Rata",
        "Dan Primack": "Axios Pro Rata",
        "Neal from Demand Curve": "Demand Curve",
        "The Daily Skimm": "theDailySkimm",
        "Ari Murray": "Go_To_Millions",
        "Kpaxs": "threetimeswiser",
        "Liz Dye from Public Notice": "Public Notice",
        "Daniel Murray": "THE MARKETING MILLENNIALS",
    }
    match = re.match(r"(.+?)\s*<", sender_str)
    if match:
        name = match.group(1).strip()
        return sender_replacements.get(name, name)
    return sender_str.strip()


def process_html_to_text(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    plain_text_content = soup.get_text()
    plain_text_content = re.sub(r"\s+", " ", plain_text_content)
    return plain_text_content


def start_of_today_for(dt_value):
    if isinstance(dt_value, datetime) and dt_value.tzinfo:
        return datetime(dt_value.year, dt_value.month, dt_value.day, tzinfo=dt_value.tzinfo)
    now = datetime.now()
    return datetime.combine(now.date(), time.min)


def is_today_message(msg_date, start_of_day):
    if isinstance(msg_date, datetime):
        return msg_date >= start_of_day
    return True


def get_today_messages():
    gmail = Gmail()
    query_params = {"newer_than": (1, "day")}
    messages = gmail.get_messages(query=construct_query(query_params))
    today_start = start_of_today_for(messages[0].date) if messages else start_of_today_for(None)
    todays_messages = []
    for message in messages:
        if is_today_message(message.date, today_start):
            todays_messages.append(message)
    if todays_messages:
        return todays_messages, False
    return messages, True


def load_local_record(message_id):
    record_path = NEWS_DIR / f"{message_id}.json"
    if not record_path.exists():
        return None
    with record_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_local_record(record):
    record_path = NEWS_DIR / f"{record['id']}.json"
    with record_path.open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def generate_summary(plain_text_content):
    response = openai_client.chat.completions.create(
        model=gpt_model,
        messages=[
            {"role": "system", "content": personality_env},
            {"role": "user", "content": plain_text_content},
        ],
    )
    total_tokens = response.usage.total_tokens
    summary = response.choices[0].message.content
    summary = summary.replace("\n", " ")
    summary = summary.replace("\\", "")
    summary = re.sub(r"\*+", "", summary)
    return summary, total_tokens


def generate_summary_tags(summary):
    response = openai_client.chat.completions.create(
        model=gpt_model,
        messages=[
            {"role": "system", "content": tag_gen_env},
            {"role": "user", "content": summary},
        ],
    )
    tags = response.choices[0].message.content
    tags = tags.replace("\n", " ")
    tags = tags.replace("\\", "")
    tags = re.sub(r"\*+", "", tags)
    return tags


def get_today_senders(messages):
    senders = {}
    for message in messages:
        sender = extract_name_from_sender(message.sender)
        senders[sender] = senders.get(sender, 0) + 1
    return sorted(senders.items(), key=lambda item: item[0].lower())


def parse_datetime_safe(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def load_today_summaries(selected_senders=None, fallback_used=False):
    summaries = []
    today_date = date.today()
    for path in NEWS_DIR.glob("*.json"):
        try:
            with path.open("r", encoding="utf-8") as f:
                record = json.load(f)
        except Exception:
            continue
        if not fallback_used:
            record_dt = parse_datetime_safe(record.get("received_date_time"))
            if record_dt and record_dt.date() != today_date:
                continue
        if selected_senders and record.get("sender") not in selected_senders:
            continue
        summaries.append(record)
    summaries.sort(key=lambda r: r.get("received_date_time") or "", reverse=True)
    return summaries


@app.route("/", methods=["GET"])
def index():
    messages, fallback_used = get_today_messages()
    senders = get_today_senders(messages)
    return render_template(
        "index.html",
        senders=senders,
        summaries=[],
        selected_senders=[],
        fallback_used=fallback_used,
    )


@app.route("/summarize", methods=["POST"])
def summarize():
    selected_senders = request.form.getlist("senders")
    messages, fallback_used = get_today_messages()

    for message in messages:
        sender = extract_name_from_sender(message.sender)
        if sender not in selected_senders:
            continue

        record = load_local_record(str(message.id))
        if record and record.get("body_summary"):
            continue

        subject = str(message.subject)
        received_day = message.date.strftime("%b %d %Y") if isinstance(message.date, datetime) else str(message.date)
        received_date_time = str(message.date)
        body = process_html_to_text(message.html)
        body = f"{sender} Email - {body}"

        summary, total_tokens = generate_summary(body)
        tags = generate_summary_tags(summary)

        record = {
            "id": str(message.id),
            "sender": sender,
            "subject": subject,
            "received_day": received_day,
            "received_date_time": received_date_time,
            "body": body,
            "body_summary": summary,
            "summary_token_count": total_tokens,
            "tags": tags,
        }
        save_local_record(record)

    summaries = load_today_summaries(
        selected_senders=selected_senders,
        fallback_used=fallback_used,
    )
    senders = get_today_senders(messages)
    return render_template(
        "index.html",
        senders=senders,
        summaries=summaries,
        selected_senders=selected_senders,
        fallback_used=fallback_used,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
