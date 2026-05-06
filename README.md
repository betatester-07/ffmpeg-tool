# HLS Fixer & Merger

A professional, easy-to-use GUI tool for fixing and merging HLS video segments (.ts) into a single MP4 file. This tool is designed to handle broken playlists or missing `.m3u8` files by automatically reconstructing the video sequence.

## Features
- **Auto-Playlist Fixer**: Automatically resolves relative paths for video segments in subfolders.
- **Auto-Build**: No `.m3u8`? No problem. The tool will scan for `.ts` chunks and build the video for you.
- **Drag & Drop**: Simply drop a folder into the window to start.
- **Modern UI**: Clean dark-themed interface with real-time logs and a progress bar.
- **Cross-Platform**: Works on Windows, macOS, and Linux.

## Prerequisites
Before running the tool, ensure you have the following installed:
1. **Python 3.x**
2. **FFmpeg**: Must be installed and added to your system's PATH.
   - [Download FFmpeg](https://ffmpeg.org/download.html)

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/betatester-07/ffmpeg-tool.git
   cd ffmpeg-tool
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
1. Run the application:
   ```bash
   python main.py
   ```
2. **Select Folder**: Click "Select Folder" or drag and drop a folder containing your video segments.
3. **Fix & Merge**: Click the button and wait for the process to complete.
4. **Output**: The merged video will be saved as `output.mp4` inside the selected folder.

## License
MIT License
