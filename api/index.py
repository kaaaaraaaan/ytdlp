import yt_dlp
import json
import urllib.parse
import os
import tempfile
from flask import Flask, request, jsonify, send_file, Response, redirect
from flask_cors import CORS
from functools import lru_cache
import time
import asyncio
from threading import Lock
import uuid
import imageio_ffmpeg
import subprocess
import shutil
import base64
import random
import string

app = Flask(__name__)
CORS(app)

# Get FFmpeg executable path
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
print(f"Using FFmpeg from: {FFMPEG_PATH}")

# Check if running on Vercel
IS_VERCEL = 'VERCEL' in os.environ
print(f"Running on Vercel: {IS_VERCEL}")

# Generate a fake cookie for YouTube
def generate_fake_cookies():
    # These are common YouTube cookie names
    cookie_names = ['VISITOR_INFO1_LIVE', 'YSC', 'PREF', 'LOGIN_INFO', 'APISID', 'HSID', 'SAPISID', 'SID', 'SSID']
    cookies = []
    
    for name in cookie_names:
        # Generate random value
        value = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
        cookies.append(f"{name}={value}")
    
    return "; ".join(cookies)

# Create a temporary cookie file for YouTube
def create_cookie_file():
    cookie_content = f"""# Netscape HTTP Cookie File
.youtube.com\tTRUE\t/\tFALSE\t2147483647\tCONSENT\tYES+cb.20210328-17-p0.en+FX+{random.randint(100, 999)}
.youtube.com\tTRUE\t/\tFALSE\t2147483647\t{generate_fake_cookies()}
www.youtube.com\tTRUE\t/\tFALSE\t2147483647\t{generate_fake_cookies()}
"""
    cookie_file = os.path.join(tempfile.gettempdir(), f"youtube_cookies_{uuid.uuid4()}.txt")
    with open(cookie_file, 'w') as f:
        f.write(cookie_content)
    return cookie_file

# Check if FFmpeg is actually available
def is_ffmpeg_available():
    """Check if FFmpeg is available on the system"""
    global FFMPEG_PATH
    try:
        # First try the path from imageio_ffmpeg
        if os.path.exists(FFMPEG_PATH):
            return True
            
        # Then try to find ffmpeg in PATH
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            FFMPEG_PATH = ffmpeg_path
            return True
            
        # Try running ffmpeg command
        result = subprocess.run(['ffmpeg', '-version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True, 
                               check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"FFmpeg check error: {str(e)}")
        return False

# Check FFmpeg availability at startup
FFMPEG_AVAILABLE = is_ffmpeg_available()
print(f"FFmpeg available: {FFMPEG_AVAILABLE}")

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
    
    # Check if we're running on Vercel
    is_vercel = IS_VERCEL
    
    if is_vercel:
        # Create a cookie file for YouTube
        cookie_file = create_cookie_file()
        print(f"Created cookie file at: {cookie_file}")
        
        # Aggressive options for Vercel environment
        ydl_opts = {
            # Request only audio formats to minimize download size
            'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best',
            'outtmpl': output_path,
            'quiet': False,
            'verbose': True,  # Enable verbose output for debugging
            'no_warnings': False,
            # Additional options to bypass restrictions
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': True,
            'geo_bypass': True,
            'geo_bypass_country': 'US',  # Try US-based IP
            'extractor_retries': 10,
            'socket_timeout': 120,
            # Enhanced options for bypassing restrictions
            'skip_download_archive': True,
            'no_cache_dir': True,
            'rm_cache_dir': True,
            'cookiefile': cookie_file,  # Use generated cookies
            'age_limit': 30,  # Set high age limit to bypass some restrictions
            'referer': 'https://www.youtube.com/',
            'sleep_interval': 1,  # Add delay between requests
            'max_sleep_interval': 5,
            'external_downloader_args': ['-timeout', '60'],
            # Add user-agent to avoid some restrictions - use a more recent Chrome version
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.youtube.com/',
                'Origin': 'https://www.youtube.com',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'DNT': '1',
            },
            # Try to use a proxy if available (Vercel doesn't support this, but we'll try)
            'proxy': None,
        }
    else:
        # Full options with FFmpeg audio extraction for local environment
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
            'extractor_retries': 5,
            'socket_timeout': 60,
            # Enhanced options for bypassing restrictions
            'skip_download_archive': True,
            'no_cache_dir': True,
            'rm_cache_dir': True,
            'cookiefile': None,  # Don't use cookies
            'age_limit': 21,  # Set high age limit to bypass some restrictions
            'referer': 'https://www.youtube.com/',  # Set referer to YouTube
            # Add user-agent to avoid some restrictions - use a more recent Chrome version
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.youtube.com/',
                'Origin': 'https://www.youtube.com',
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
                if is_vercel:
                    # If we're on Vercel, the filename will be in the format {unique_id}.m4a or {unique_id}.mp3
                    filename = os.path.join(download_dir, f"{unique_id}.{info['ext']}")
                else:
                    filename = os.path.join(download_dir, f"{unique_id}.mp3")
                
                title = info.get('title', 'downloaded_audio')
                
                # Check if the file was actually created
                if os.path.exists(filename):
                    return {
                        'success': True,
                        'file_path': filename,
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
        
        # If we're on Vercel and the standard download failed, try to extract direct URLs
        if is_vercel:
            try:
                print("Attempting fallback method: extracting direct audio URL...")
                # Configure yt-dlp to only extract info, not download
                extract_opts = {
                    'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio',
                    'quiet': False,
                    'no_warnings': False,
                    'nocheckcertificate': True,
                    'geo_bypass': True,
                    'cookiefile': create_cookie_file(),  # Use generated cookies
                    'skip_download': True,  # Don't download, just extract info
                    'http_headers': ydl_opts['http_headers'],
                }
                
                with yt_dlp.YoutubeDL(extract_opts) as ydl:
                    info = ydl.extract_info(youtube_url, download=False)
                    
                    if info and 'formats' in info:
                        # Find the best audio format
                        audio_formats = [f for f in info['formats'] 
                                        if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                        
                        if not audio_formats:
                            # If no audio-only format, take any format with audio
                            audio_formats = [f for f in info['formats'] if f.get('acodec') != 'none']
                        
                        if audio_formats:
                            # Sort by quality (typically bitrate)
                            audio_formats.sort(key=lambda x: x.get('abr', 0), reverse=True)
                            best_audio = audio_formats[0]
                            
                            return {
                                'success': True,
                                'direct_url': True,  # Flag that this is a direct URL, not a file
                                'url': best_audio.get('url'),
                                'title': info.get('title', 'audio'),
                                'info': {
                                    'id': info.get('id', ''),
                                    'title': info.get('title', ''),
                                    'duration': info.get('duration', 0),
                                    'uploader': info.get('uploader', ''),
                                    'format': best_audio.get('format', ''),
                                    'ext': best_audio.get('ext', 'mp3')
                                }
                            }
                
                print("Fallback method failed: No suitable audio formats found")
            except Exception as fallback_error:
                print(f"Fallback method failed: {str(fallback_error)}")
        
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
    if not FFMPEG_AVAILABLE and not IS_VERCEL:
        return jsonify({'error': 'FFmpeg is not available on the system'}), 500
    
    youtube_url = request.args.get('url', '')
    json_response = request.args.get('json', 'false').lower() == 'true'
    
    if not youtube_url:
        return jsonify({'error': 'Missing YouTube URL parameter'}), 400
    
    # Validate the URL (basic check)
    if not youtube_url.startswith(('https://www.youtube.com/', 'https://youtu.be/', 'http://www.youtube.com/', 'http://youtu.be/')):
        return jsonify({'error': 'Invalid YouTube URL'}), 400
    
    # Download the video as MP3
    result = download_youtube_to_mp3(youtube_url)
    
    # If this is a direct URL result from the fallback method
    if result.get('success') and result.get('direct_url'):
        if json_response:
            return jsonify({
                'success': True,
                'direct_url': True,
                'url': result['url'],
                'title': result['title'],
                'info': result.get('info', {})
            })
        else:
            # Redirect to the direct URL
            return redirect(result['url'])
    
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
            download_name=f"{safe_title}{os.path.splitext(filename)[1]}",
            mimetype='audio/mpeg' if os.path.splitext(filename)[1] == '.mp3' else 'audio/x-m4a'
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
