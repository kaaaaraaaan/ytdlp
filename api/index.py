import yt_dlp
import json
import urllib.parse
import os
import tempfile
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from functools import lru_cache
import time
import asyncio
from threading import Lock
import uuid
import imageio_ffmpeg

app = Flask(__name__)
CORS(app)

# Get FFmpeg executable path
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
print(f"Using FFmpeg from: {FFMPEG_PATH}")

# Cache and rate limiting configuration
CACHE_DURATION = 3600  # 1 hour in seconds
REQUEST_DELAY = 0.5  # 0.5 seconds between requests
last_request_time = 0
request_lock = Lock()
video_cache = {}
download_dir = tempfile.gettempdir()  # Use system temp directory for downloads

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

def download_youtube_to_mp3(youtube_url):
    """
    Download a YouTube video as MP3 using yt-dlp
    """
    # Generate a unique filename using UUID
    unique_id = str(uuid.uuid4())
    output_path = os.path.join(download_dir, f"{unique_id}.%(ext)s")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output_path,
        'quiet': False,
        'no_warnings': False,
        # Additional options to bypass restrictions
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'geo_bypass': True,
        'extractor_retries': 3,
        'socket_timeout': 30,
        # Add user-agent to avoid some restrictions
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        },
        # Specify FFmpeg executable path
        'ffmpeg_location': FFMPEG_PATH
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading from URL: {youtube_url}")
            info = ydl.extract_info(youtube_url, download=True)
            
            if info:
                # Get the actual filename after download and processing
                mp3_filename = os.path.join(download_dir, f"{unique_id}.mp3")
                title = info.get('title', 'downloaded_audio')
                
                # Check if the file was actually created
                if os.path.exists(mp3_filename):
                    return {
                        'success': True,
                        'file_path': mp3_filename,
                        'title': title,
                        'info': {
                            'id': info.get('id', ''),
                            'title': title,
                            'duration': info.get('duration', 0),
                            'uploader': info.get('uploader', ''),
                            'view_count': info.get('view_count', 0)
                        }
                    }
                else:
                    return {
                        'success': False,
                        'error': 'File was not created after download',
                        'info': {
                            'id': info.get('id', ''),
                            'title': title,
                            'url': youtube_url
                        }
                    }
            else:
                return {
                    'success': False,
                    'error': 'Failed to extract video information'
                }
                
    except Exception as e:
        error_message = str(e)
        print(f"Error during YouTube download: {error_message}")
        
        # Provide more specific error messages for common issues
        if "Sign in to confirm" in error_message:
            error_message = "YouTube requires authentication for this video. Try another video or use a different method."
        elif "HTTP Error 403" in error_message:
            error_message = "Access forbidden by YouTube. This might be due to region restrictions or YouTube's anti-bot measures."
        elif "ffmpeg" in error_message.lower():
            error_message = "FFmpeg is required but not found. Please install FFmpeg and add it to your PATH."
        
        return {
            'success': False,
            'error': error_message,
            'url': youtube_url
        }

@app.route('/download', methods=['GET'])
def download():
    youtube_url = request.args.get('url', '')
    json_response = request.args.get('json', 'false').lower() == 'true'
    
    if not youtube_url:
        return jsonify({'error': 'Missing YouTube URL parameter'}), 400
    
    # Validate the URL (basic check)
    if not youtube_url.startswith(('https://www.youtube.com/', 'https://youtu.be/', 'http://www.youtube.com/', 'http://youtu.be/')):
        return jsonify({'error': 'Invalid YouTube URL'}), 400
    
    # Download the video as MP3
    result = download_youtube_to_mp3(youtube_url)
    
    # If json response is requested or download failed, return JSON
    if json_response or not result['success']:
        if not result['success']:
            return jsonify({'error': result['error'], 'url': youtube_url}), 500
        else:
            return jsonify({
                'success': True,
                'title': result['title'],
                'info': result.get('info', {})
            })
    
    # Return the file as an attachment
    try:
        # Get the filename from the path
        filename = os.path.basename(result['file_path'])
        
        # Clean the title for use in Content-Disposition
        safe_title = result['title'].replace('"', '_').replace("'", '_')
        
        # Send the file with the video title as the suggested filename
        response = send_file(
            result['file_path'],
            as_attachment=True,
            download_name=f"{safe_title}.mp3",
            mimetype='audio/mpeg'
        )
        
        # Add a callback to remove the file after sending
        @response.call_on_close
        def remove_file():
            try:
                if os.path.exists(result['file_path']):
                    os.remove(result['file_path'])
                    print(f"Removed temporary file: {result['file_path']}")
            except Exception as e:
                print(f"Error removing temporary file: {str(e)}")
        
        return response
        
    except Exception as e:
        print(f"Error sending file: {str(e)}")
        # Try to clean up the file if there was an error
        if os.path.exists(result['file_path']):
            try:
                os.remove(result['file_path'])
            except:
                pass
        return jsonify({'error': f'Error sending file: {str(e)}'}), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'YouTube search and download service is running'})

if __name__ == '__main__':
    print("Starting YouTube search and download service...")  # Debug log
    app.run(port=3001, debug=True)
