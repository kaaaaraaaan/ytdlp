import yt_dlp
import json
import urllib.parse
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import lru_cache
import time
import asyncio
from threading import Lock

app = Flask(__name__)
CORS(app)

# Cache and rate limiting configuration
CACHE_DURATION = 3600  # 1 hour in seconds
REQUEST_DELAY = 0.5  # 0.5 seconds between requests
last_request_time = 0
request_lock = Lock()
video_cache = {}

@lru_cache(maxsize=100)
def search_youtube_video(song_name: str, artist_name: str) -> dict:
    """
    Search for a YouTube video using yt-dlp with rate limiting
    """
    global last_request_time
    
    # Rate limiting
    with request_lock:
        current_time = time.time()
        time_since_last_request = current_time - last_request_time
        if time_since_last_request < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - time_since_last_request)
        last_request_time = time.time()
    
    query = f"ytsearch1:{song_name} {artist_name} official music video"
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'force_generic_extractor': False
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Searching with query: {query}")  # Debug log
            
            # Extract info using ytsearch format
            search_results = ydl.extract_info(query, download=False)
            
            if search_results and 'entries' in search_results and len(search_results['entries']) > 0:
                video = search_results['entries'][0]
                return {
                    'id': video.get('id', ''),
                    'url': f"https://www.youtube.com/watch?v={video.get('id', '')}",
                    'title': video.get('title', ''),
                    'thumbnail': video.get('thumbnail', ''),
                    'duration': video.get('duration', 0)
                }
            else:
                print("No results found")
                return {}
                
    except Exception as e:
        print(f"Error during YouTube search: {str(e)}")
        return {}

@app.route('/search', methods=['GET'])
def search():
    song = request.args.get('song', '')
    artist = request.args.get('artist', '')
    
    if not song or not artist:
        return jsonify({'error': 'Missing song or artist parameter'}), 400
    
    # Check memory cache first
    cache_key = f"{song}-{artist}"
    cached_result = video_cache.get(cache_key)
    if cached_result and (time.time() - cached_result['timestamp']) < CACHE_DURATION:
        return jsonify(cached_result['data'])
    
    # If not in cache, perform search
    result = search_youtube_video(song, artist)
    
    # Update cache
    if result:
        video_cache[cache_key] = {
            'data': result,
            'timestamp': time.time()
        }
    
    return jsonify(result)

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'YouTube search service is running'})

if __name__ == '__main__':
    print("Starting YouTube search service...")  # Debug log
    app.run(port=3001, debug=True)
