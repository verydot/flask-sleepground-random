import sqlite3
import subprocess
import json
from datetime import datetime
from flask import Flask, render_template, jsonify
import threading

# 데이터베이스 초기화
def init_db():
    conn = sqlite3.connect("videos.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            thumbnail TEXT NOT NULL,
            published_date TEXT NOT NULL,
            duration INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# yt-dlp를 사용하여 비디오 세부 정보 가져오기
def fetch_video_details(video_url):
    command = ["yt-dlp", "--dump-json", video_url]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        video_data = json.loads(result.stdout)
        duration = int(video_data.get("duration", 0)) // 60  # 초를 분으로 변환
        return {
            "title": video_data.get("title"),
            "url": video_data.get("webpage_url"),
            "thumbnail": video_data.get("thumbnail"),
            "published_date": video_data.get("upload_date"),
            "duration": duration
        }
    else:
        print(f"Error fetching details for {video_url}: {result.stderr}")
        return None

# 비디오 데이터를 데이터베이스에 저장
def save_video_to_db(title, url, thumbnail, published_date, duration):
    conn = sqlite3.connect("videos.db")
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO videos (title, url, thumbnail, published_date, duration)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, url, thumbnail, published_date, duration))
        conn.commit()
    except sqlite3.IntegrityError:
        print(f"Skipping duplicate video: {url}")
    conn.close()

# 플레이리스트에서 모든 비디오 데이터를 가져와 저장
def fetch_and_save_all_videos(playlist_urls):
    for playlist_url in playlist_urls:
        command = ["yt-dlp", "--flat-playlist", "--dump-json", playlist_url]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                video_data = json.loads(line)
                video_url = f"https://www.youtube.com/watch?v={video_data['id']}"
                details = fetch_video_details(video_url)
                if details:
                    published_date = datetime.strptime(details["published_date"], "%Y%m%d")
                    if published_date >= datetime(2019, 12, 15) and details["duration"] >= 5:
                        save_video_to_db(
                            title=details["title"],
                            url=details["url"],
                            thumbnail=details["thumbnail"],
                            published_date=published_date.strftime("%Y-%m-%d"),
                            duration=details["duration"]
                        )
        else:
            print(f"Error fetching playlist: {playlist_url}")

# 백그라운드에서 비디오 데이터 가져오기
def fetch_videos_in_background(playlist_urls):
    def background_task():
        fetch_and_save_all_videos(playlist_urls)  # 모든 비디오 데이터를 저장
        print("Background task completed.")  # 디버깅 메시지
    threading.Thread(target=background_task, daemon=True).start()

# 랜덤으로 비디오 추천
def get_random_video():
    conn = sqlite3.connect("videos.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, url, thumbnail FROM videos ORDER BY RANDOM() LIMIT 1")
    video = cursor.fetchone()
    conn.close()
    if video:
        return {
            "title": video[0],
            "url": video[1],
            "thumbnail": video[2]
        }
    return None

# Flask 앱 설정
app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/recommend', methods=['GET'])
def recommend_video():
    video = get_random_video()
    if video:
        return jsonify(video)
    return jsonify({"error": "No videos available"}), 404

if __name__ == '__main__':
    init_db()  # 데이터베이스 초기화

    # 플레이리스트 URL 목록
    playlist_urls = [
        "https://www.youtube.com/playlist?list=PLbeHrp_B4_oOTMtp-mnX59mAIppEFvedH",
        "https://www.youtube.com/playlist?list=PLbeHrp_B4_oPUVJHzv4cRfk2OxYRWwftr",
        "https://www.youtube.com/playlist?list=PLbeHrp_B4_oO6zbDWpH6CWvVL_OLSls38",
        # 나머지 플레이리스트 URL 추가
    ]

    # 비디오 저장을 백그라운드에서 실행
    fetch_videos_in_background(playlist_urls)

    # Flask 서버 실행
    print("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000, debug=True)
