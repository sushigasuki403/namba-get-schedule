import os
import base64
import requests
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from bs4 import BeautifulSoup

INFO_URL = "https://cs-plaza.co.jp/naniwa-sc/information/3106"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def download_image():
    response = requests.get(INFO_URL)
    soup = BeautifulSoup(response.content, "html.parser")
    target_article = soup.find("article", class_="entry-body")
    if not target_article:
        print("❌ 記事が見つかりませんでした")
        return None

    img_tag = target_article.find("img")
    if not img_tag or not img_tag.get("src"):
        print("❌ 画像が見つかりませんでした")
        return None

    img_url = requests.compat.urljoin(INFO_URL, img_tag.get("src"))
    img_data = requests.get(img_url).content
    with open("calendar_image.png", "wb") as f:
        f.write(img_data)

    return "calendar_image.png"

def extract_events_with_gemini(image_path):
    with open(image_path, "rb") as img_file:
        image_data = base64.b64encode(img_file.read()).decode("utf-8")

    prompt = (
        "この画像には営業日程が書かれています。"
        "画像から、月・日にち・営業している時間帯（例：10:00～19:00）を各日にちごとに抽出してください。"
        "結果は以下のようにJSON形式で返してください："
        "[{\"date\": \"2025-04-10\", \"start\": \"10:00\", \"end\": \"19:00\"}, ...]"
    )

    body = {
        "contents": [
            {"parts": [{"text": prompt}]},
            {"parts": [{"inlineData": {
                "mimeType": "image/png",
                "data": image_data
            }}]}
        ]
    }

    headers = {"Content-Type": "application/json"}
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro-vision:generateContent?key={GEMINI_API_KEY}"

    res = requests.post(url, headers=headers, json=body)
    res.raise_for_status()

    text = res.json()["candidates"][0]["content"]["parts"][0]["text"]

    # JSON抽出
    import json
    try:
        start_idx = text.find("[")
        end_idx = text.rfind("]") + 1
        events_json = text[start_idx:end_idx]
        return json.loads(events_json)
    except Exception as e:
        print("❌ JSONパースに失敗:", e)
        print("レスポンス:", text)
        return []

def register_to_google_calendar(events):
    credentials = service_account.Credentials.from_service_account_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/calendar"]
    )

    service = build("calendar", "v3", credentials=credentials)
    calendar_id = "rikushiomi.kfsc@gmail.com"

    for event in events:
        start_datetime = f"{event['date']}T{event['start']}:00"
        end_datetime = f"{event['date']}T{event['end']}:00"

        event_body = {
            'summary': f"一般営業 ({event['start']}～{event['end']})",
            'start': {'dateTime': start_datetime, 'timeZone': 'Asia/Tokyo'},
            'end': {'dateTime': end_datetime, 'timeZone': 'Asia/Tokyo'}
        }

        service.events().insert(calendarId=calendar_id, body=event_body).execute()

    print("✅ Googleカレンダーへの登録完了")

def main():
    image_path = download_image()
    if not image_path:
        return

    events = extract_events_with_gemini(image_path)
    if not events:
        print("❌ イベント情報が抽出できませんでした")
        return

    register_to_google_calendar(events)

if __name__ == "__main__":
    main()

