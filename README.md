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

### Vercel Deployment Notes

When deploying to Vercel, there are some limitations to be aware of:

1. **FFmpeg Availability**: Vercel serverless functions don't have FFmpeg pre-installed. The application will automatically detect this and switch to a mode that doesn't require FFmpeg, downloading the best available audio format directly.

2. **Execution Time Limits**: Vercel has a maximum execution time for serverless functions (typically 10-60 seconds). Some larger videos may not download successfully due to this limitation.

3. **Memory Constraints**: Vercel serverless functions have memory limits that may affect downloading larger videos.

4. **IP Restrictions**: YouTube may sometimes block or require authentication from Vercel's IP addresses. The application includes enhanced options to bypass these restrictions, but some videos may still be inaccessible.

### Troubleshooting

If you encounter issues with the Vercel deployment:

1. Try downloading a different video - some videos have stricter restrictions than others.
2. If a specific video works locally but not on Vercel, it may be due to one of the limitations mentioned above.
3. For production use, consider deploying to a platform that supports installing system dependencies like FFmpeg (e.g., a VPS or container-based service).

## License

MIT
