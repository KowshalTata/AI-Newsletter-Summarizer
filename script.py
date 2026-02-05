from simplegmail import Gmail
from simplegmail.query import construct_query
from bs4 import BeautifulSoup
import re
from datetime import datetime
from openai import OpenAI
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
import numpy as np

# Load variables from .env file
load_dotenv()

# OpenAI
openai_api_key = os.environ.get("OPENAI_API_KEY")
openai_client = OpenAI(api_key=openai_api_key)
gpt_model = "gpt-3.5-turbo-0125"

personality_env = """Generate a news letters analysis script on the topic of [User Custom Topic]. Provide an engaging and well-structured narrative, similar to a professional news letters analyzer. Ensure the response is suitable for narration through a Text-to-Speech (TTS) system API. The goal is to deliver informative content with a conversational tone, drawing exclusively from the provided topic and without incorporating outside knowledge.
Please note:
- Do not include any stage directions such as [Opening Music], [Transition Music], [Host]. Those will be manually added as per the requirements into the TTS generated audio file.
- Keep it short and informative by limiting the response to a few points, covering all the highlights from the topic, so that users listening to this as a voice clip will stay attentive to details and will not be irritated."""

tag_gen_env = """Generate concise and engaging keyword tags for a newsletter, offering users a preview of the content. Craft tags based on the provided newsletter content to create an enticing snapshot. Each highlight should be represented by a single tag. Format: #tag."""

background_color = "white"

# Local storage
DATA_DIR = Path("local_data")
NEWS_DIR = DATA_DIR / "newsletters"
WORDCLOUD_DIR = DATA_DIR / "word_cloud"
DATA_DIR.mkdir(exist_ok=True)
NEWS_DIR.mkdir(exist_ok=True)
WORDCLOUD_DIR.mkdir(exist_ok=True)


###### Stage Zero - Extract the filtered message from my gmail inbox
def get_filtered_messages():
    gmail = Gmail()

    # Define query parameters
    query_params = {
        "newer_than": (1, "day"),
    }

    # Get filtered messages
    messages = gmail.get_messages(query=construct_query(query_params))
    return messages


def extract_name_from_sender(sender_str):
    # Dictionary to map sender names to replacements
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
        # Add more mappings here as needed
    }

    # Extract only the name from the "From" field
    match = re.match(r"(.+?)\s*<", sender_str)
    if match:
        name = match.group(1).strip()
        # Check if the name needs to be replaced
        if name in sender_replacements:
            name = sender_replacements[name]
        return name
    else:
        return sender_str.strip()


def get_local_record_path(message_id):
    return NEWS_DIR / f"{message_id}.json"


def load_local_record(message_id):
    record_path = get_local_record_path(message_id)
    if not record_path.exists():
        return None
    with record_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_local_record(record):
    record_path = get_local_record_path(record["id"])
    with record_path.open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def is_message_ID_body_already_inserted(message_id):
    record = load_local_record(str(message_id))
    return bool(record and record.get("body_summary"))


# Allowed sender names
allowed_senders = [
    "THE MARKETING MILLENNIALS",
    "Public Notice",
    "threetimeswiser",
    "Go_To_Millions",
    "theDailySkimm",
    "Demand Curve",
    "TLDR",
    "TLDR AI",
    "TLDR Marketing",
    "Techpresso",
    "The Neuron",
    "The Average Joe",
    "Morning Brew",
    "Axios Pro Rata",
    "CFO Brew",
    "10almonds",
    "Game Rant",
    "Axios AM PM",
    "Axios Vitals",
    "DTC Daily",
]


def format_date(date_value):
    if isinstance(date_value, datetime):
        return date_value.strftime("%b %d %Y")
    if isinstance(date_value, str):
        try:
            dt = datetime.strptime(date_value, "%Y-%m-%d %H:%M:%S%z")
            return dt.strftime("%b %d %Y")
        except ValueError:
            return date_value
    return str(date_value)


def process_html_to_text(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    plain_text_content = soup.get_text()
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F700-\U0001F77F"  # alchemical symbols
        u"\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        u"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        u"\U0001FA00-\U0001FA6F"  # Chess Symbols
        u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        u"\U00002702-\U000027B0"  # Dingbats
        u"\U000024C2-\U0001F251"
        u"\U0000200D"
        "]+",
        flags=re.UNICODE,
    )
    plain_text_content = emoji_pattern.sub(r"", plain_text_content)
    # Remove extra whitespaces
    plain_text_content = re.sub(r"\s+", " ", plain_text_content)
    return plain_text_content


def get_publisher_id(sender_str):
    sender_mapping = {
        "TLDR AI": 10,
        "Techpresso": 11,
        "TLDR": 12,
        "The Neuron": 13,
        "CFO Brew": 20,
        "The Average Joe": 21,
        "Axios Pro Rata": 22,
        "Game Rant": 30,
        "10almonds": 40,
        "Axios Vitals": 41,
        "THE MARKETING MILLENNIALS": 50,
        "DTC Daily": 51,
        "TLDR Marketing": 52,
        "Go_To_Millions": 53,
        "Morning Brew": 60,
        "Axios AM PM": 61,
        "theDailySkimm": 62,
        "Public Notice": 63,
        "Demand Curve": 70,
        "threetimeswiser": 71,
    }
    return sender_mapping.get(sender_str, None)


def is_message_already_inserted(message_id):
    return get_local_record_path(str(message_id)).exists()


def store_message_locally(message):
    try:
        sender_str = extract_name_from_sender(str(message.sender))
        id_str = str(message.id)
        subject_str = str(message.subject)
        date_str = format_date(message.date)
        date_time_str = message.date

        if is_message_already_inserted(id_str):
            print(f"Skipping duplicate message with ID: {id_str}_{sender_str}_{date_str}")
            return

        plain_text_content = process_html_to_text(message.html)
        plain_text_content = sender_str + " " + "Newsletter" + "-" + plain_text_content

        record = {
            "id": id_str,
            "subject": subject_str,
            "received_day": date_str,
            "received_date_time": str(date_time_str),
            "body": plain_text_content,
            "publisher_id": get_publisher_id(sender_str),
            "sender": sender_str,
        }

        save_local_record(record)
        print(f"Details of {sender_str} saved locally")

    except Exception as e:
        print(f"Error storing message locally: {e}")


## Stage two summarize body and generate summary_image
personality = personality_env


def generate_summary(plain_text_content):
    response = openai_client.chat.completions.create(
        model=gpt_model,
        messages=[
            {"role": "system", "content": f"{personality}"},
            {"role": "user", "content": plain_text_content},
        ],
    )

    total_tokens = response.usage.total_tokens
    summary = response.choices[0].message.content

    # Clean up the response
    summary = summary.replace("\n", " ")
    summary = summary.replace("\\", "")
    summary = re.sub(r"\*+", "", summary)

    return summary, total_tokens


def generate_summary_tags(summary):
    response = openai_client.chat.completions.create(
        model=gpt_model,
        messages=[
            {"role": "system", "content": f"{tag_gen_env}"},
            {"role": "user", "content": summary},
        ],
    )

    tags = response.choices[0].message.content
    tags = tags.replace("\n", " ")
    tags = tags.replace("\\", "")
    tags = re.sub(r"\*+", "", tags)
    return tags


def generate_word_cloud(body_summary, id_str, sender_str, date_str):
    word_cloud_text = body_summary
    colormap = np.random.choice(
        [
            "viridis",
            "plasma",
            "inferno",
            "magma",
            "cividis",
            "Reds",
            "Purples",
            "Oranges",
            "twilight",
            "tab10",
            "seismic",
            "Set1",
        ]
    )

    wordcloud = WordCloud(
        width=800,
        height=400,
        background_color=background_color,
        stopwords=set(STOPWORDS),
        collocations=False,
        colormap=colormap,
        contour_width=np.random.uniform(0.5, 3.0),
        contour_color=np.random.choice(["black", "white", "gray", "red", "blue"]),
    ).generate(word_cloud_text)

    plt.figure(figsize=(10, 5))
    plt.imshow(wordcloud, interpolation="bilinear")
    plt.axis("off")
    plt.tight_layout()
    output_path = WORDCLOUD_DIR / f"{id_str}_{sender_str}_{date_str}_wordcloud.png"
    plt.savefig(output_path)
    wordcloud.to_file(output_path)
    print(f"Word cloud image saved for message {id_str}_{sender_str}_{date_str}")
    return str(output_path)


# Get filtered messages
messages = get_filtered_messages()

# Filter messages based on sender name
Messages = []
for message in messages:
    if not is_message_ID_body_already_inserted(message.id):
        sender_name = extract_name_from_sender(message.sender)
        if sender_name in allowed_senders:
            Messages.append(message)

# Print sender names along with subjects
for message in Messages:
    sender_name = extract_name_from_sender(message.sender)
    subject = message.subject
    print("                                                                                                      ")
    print(f"{sender_name}: {subject}")
    print("                                                                                                      ")

# Store each message locally
for message in Messages:
    store_message_locally(message)

# Iterate over records and generate summaries
for message in Messages:
    sender_str = extract_name_from_sender(message.sender)
    id_str = str(message.id)
    date_str = format_date(str(message.date))

    record = load_local_record(id_str)
    if not record:
        print(f"Skipping message {id_str} because local record not found.")
        continue

    if not record.get("body_summary"):
        plain_text_content = process_html_to_text(message.html)
        plain_text_content = sender_str + " " + "Newsletter" + "-" + plain_text_content

        summary, total_tokens = generate_summary(plain_text_content)
        tags = generate_summary_tags(summary)

        record["body_summary"] = summary
        record["summary_token_count"] = total_tokens
        record["tags"] = tags

        wordcloud_path = generate_word_cloud(summary, id_str, sender_str, date_str)
        record["summary_image_path"] = wordcloud_path

        save_local_record(record)
    else:
        print(f"Skipping message {id_str} because Body_Summary is not empty.")
