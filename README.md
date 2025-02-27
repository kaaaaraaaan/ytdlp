# YouTube Downloader API

This application provides a simple API for searching YouTube videos and downloading them as MP3 files. It uses Flask, yt-dlp, and FFmpeg to handle the search and download functionality.

## Features

- Search for YouTube videos by song name and artist
- Download YouTube videos as MP3 files
- Caching to improve performance and reduce API calls
- Rate limiting to prevent abuse
- Error handling for common issues

## API Endpoints

### Search Endpoint

```
GET /search?song=SONG_NAME&artist=ARTIST_NAME
```

Returns information about the most relevant YouTube video for the given song and artist.

### Download Endpoint

```
GET /download?url=YOUTUBE_URL
```

Downloads the YouTube video as an MP3 file and returns it as an attachment.

For JSON response instead of file download:

```
GET /download?url=YOUTUBE_URL&json=true
```

## Dependencies

- Flask 3.0.0
- flask-cors 4.0.0
- yt-dlp 2025.02.19
- ffmpeg-python 0.2.0
- imageio-ffmpeg 0.6.0

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python api/index.py
```

Your application is now available at `http://localhost:3001`.

## Deployment

This application is configured for deployment on Vercel with Serverless Functions.

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fkaaaaraaaan%2Fytdlp)
