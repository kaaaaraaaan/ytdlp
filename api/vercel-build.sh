#!/bin/bash

# Create the bin directory
mkdir -p .vercel/bin

# Download a static build of FFmpeg
curl -L https://github.com/eugeneware/ffmpeg-static/releases/download/b4.4.0/ffmpeg-linux-x64 -o .vercel/bin/ffmpeg
curl -L https://github.com/eugeneware/ffmpeg-static/releases/download/b4.4.0/ffprobe-linux-x64 -o .vercel/bin/ffprobe

# Make them executable
chmod +x .vercel/bin/ffmpeg
chmod +x .vercel/bin/ffprobe

# List the files to verify they exist
ls -la .vercel/bin/
