![Demo (screenshot)](https://i.imgur.com/ANZOcKP.png)
# 🎬 YouTube Downloader

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-web%20interface-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20Android-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

A modern, feature-rich YouTube downloader with a beautiful web interface and powerful command-line tools. Download videos up to 8K quality with intelligent fallback mechanisms and advanced error recovery.

> **⚠️ Legal Notice**: This tool is for educational and personal use only. Please respect YouTube's Terms of Service and copyright laws. Only download content you have permission to download.

## ✨ Key Features

- **High-Quality Downloads:** Up to 8K (7680x4320), multiple quality options, audio-only MP3, metadata embedding
- **Modern Web Interface:** Responsive design, dark/light mode, real-time progress, download history, clipboard integration, mobile-friendly
- **Advanced Technology:** Dual-mode (Ultra/Standard), intelligent error recovery, rate limiting protection, multi-threaded downloads, FFmpeg integration
- **Reliability & Robustness:** Multiple retry mechanisms, cookie-based sessions, format fallback, production-ready WSGI server
- **Multi-Platform:** Full support for Windows, macOS, Linux, and Android (Termux)

## 🚀 Quick Start

### 🖥️ Windows (One-Click Setup)

```batch
# Clone repository
git clone https://github.com/diorhc/YTDL.git
cd YTDL

$desktop = "$env:USERPROFILE\Desktop"
if (-not (Test-Path $desktop)) {
    New-Item -ItemType Directory -Path $desktop | Out-Null
}
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$desktop\YouTube Downloader.lnk")
$Shortcut.TargetPath = "$(Resolve-Path 'launcher.bat')"
$Shortcut.WorkingDirectory = (Get-Location).Path
$Shortcut.Description = "YouTube Downloader Launcher"
$Shortcut.Save()
Write-Host "Shortcut created on Desktop: YouTube Downloader.lnk"

# Start application
"2`n1" | cmd /c launcher.bat

```

### 🐧 Linux / 🍎 macOS

```bash
# Clone repository
sudo apt update
sudo apt install -y git curl
git clone https://github.com/diorhc/YTDL.git
cd YTDL

# Make launcher executable
chmod +x launcher.sh

# Start application
./launcher.sh
# Choose option 2 (Setup / Install Dependencies)
# Choose option 1 (Launch Web Interface)
```

**📖 See [README_UNIX.md](README_UNIX.md) for detailed Mac/Linux installation guide**

### 🤖 Android (Termux)

```bash
# Install Termux from F-Droid (not Google Play!)
# https://f-droid.org/packages/com.termux/

# Update packages
pkg update -y && pkg upgrade -y

# Clone repository
pkg install git -y
git clone https://github.com/diorhc/YTDL.git
cd YTDL

# Make launcher executable
chmod +x launcher_termux.sh

# Start application
./launcher_termux.sh
# Choose option 3 (Install Termux Dependencies)
# Choose option 4 (Install Python Dependencies)
# Choose option 5 (Setup Storage Access)
# Choose option 1 (Launch Web Interface)
```

**📱 See [README_TERMUX.md](README_TERMUX.md) for detailed Android/Termux installation guide**

### 🌐 Web Interface Usage

1. **Start the server:** `python web_app.py` or `launcher.bat`
2. **Open your browser:** Go to [http://localhost:5005]
3. **Paste YouTube URL:** Enter any YouTube video URL
4. **Select quality:** Choose video quality or audio-only
5. **Download:** Click download and watch real-time progress
6. **Access history:** View and re-download previous downloads

## 🖱️ Command Line Interface

### Basic Usage

```bash
# Download best quality
python youtube_downloader.py "https://youtu.be/VIDEO_ID"

# Download specific quality
python youtube_downloader.py "https://youtu.be/VIDEO_ID" -q 1080p

# Audio only download
python youtube_downloader.py "https://youtu.be/VIDEO_ID" --audio-only

# Custom filename
python youtube_downloader.py "https://youtu.be/VIDEO_ID" -o "My Custom Video"

# List available formats
python youtube_downloader.py "https://youtu.be/VIDEO_ID" --list-formats
```

### Advanced Options

```bash
# Ultra mode (separate video/audio streams)
python youtube_downloader.py "https://youtu.be/VIDEO_ID" --mode ultra -q 4k

# Standard mode (single stream)
python youtube_downloader.py "https://youtu.be/VIDEO_ID" --mode standard -q 1080p

# Custom download directory
python youtube_downloader.py "https://youtu.be/VIDEO_ID" --download-path "./my_videos/"

# Show capabilities
python youtube_downloader.py --capabilities
```

## 🏗️ Project Structure

```
YouTube Downloader/
├── youtube_downloader.py     # Core download engine
├── web_app.py                # Flask web application
├── test_quality_fix.py       # Quality detection
├── launcher.bat              # Windows launcher
├── launcher.sh               # Mac/Linux launcher (chmod +x required)
├── launcher_termux.sh        # Android/Termux launcher (chmod +x required)
├── setup_termux.sh           # Quick setup for Termux
├── requirements.txt          # Python dependencies
├── LICENSE                   # MIT license
├── README.md                 # Main documentation
├── README_UNIX.md            # Mac/Linux installation guide
├── README_TERMUX.md          # Android/Termux installation guide
│
├── templates/
│   └── index.html            # Web interface template
│
└── downloads/                # Downloaded videos (auto-created)
```

## 🛠️ Configuration

### Environment Variables

Create a `.env` file for custom configuration:

```env
FLASK_HOST=0.0.0.0
FLASK_PORT=5005
FLASK_DEBUG=False
DEFAULT_QUALITY=1080p
DOWNLOAD_PATH=./downloads/
MAX_RETRIES=3
ENABLE_COOKIES=True
USER_AGENT=Custom User Agent
```

### Custom Settings

Edit `web_app.py`:

```python
DOWNLOAD_DIR = "D:/MyVideos/"
HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 8080       # Custom port
```

## Auto-update of requirements

On startup the launcher will attempt to refresh `requirements.txt` from the
current Python environment using a small whitelist of core packages. This runs
in dry-run mode by default so it only prints the proposed changes.

- Disable automatic checks by setting the environment variable
  `AUTO_UPDATE_REQUIREMENTS=0`.
- Force a real write by setting `AUTO_UPDATE_DRY_RUN=0` before running the
  launcher.
- Or pass the CLI flag `--no-auto-update` when starting `launcher.py`.

The feature is conservative: it updates a short, maintainable list of core
packages instead of a full `pip freeze` to avoid adding transitive dependencies.

Launcher "Update" (option 4) now checks the active Python environment (embedded
first, then system Python) for outdated packages and will offer to upgrade them
automatically. This runs `pip list --outdated` and upgrades packages one-by-one.

## 🐛 Troubleshooting

| Problem                | Solution                                      |
| ---------------------- | --------------------------------------------- |
| `ModuleNotFoundError`  | Run `pip install -r requirements.txt`         |
| Web server won't start | Check if port 5005 is in use, try another     |
| Download fails         | Update yt-dlp: `pip install --upgrade yt-dlp` |
| No audio in video      | Install FFmpeg and ensure it's in PATH        |
| 403 Forbidden errors   | Tool retries automatically                    |
| Slow downloads         | Check internet, YouTube may be rate limiting  |

### Debug Mode

```bash
python web_app.py --debug
```

### Updating yt-dlp

```bash
pip install --upgrade yt-dlp
yt-dlp -U
```

## 🔒 Security & Privacy

- **No data collection:** All processing is local
- **No external dependencies:** Self-contained app
- **Safe downloads:** Validates URLs and file types
- **Sandboxed execution:** Downloads in isolated directory

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch:** `git checkout -b feature/amazing-feature`
3. **Make your changes** (follow code style)
4. **Add tests**
5. **Commit:** `git commit -m 'Add amazing feature'`
6. **Push:** `git push origin feature/amazing-feature`
7. **Open a Pull Request**

### Development Setup

```bash
git clone https://github.com/diorhc/YTDL.git
cd YTDL
pip install -r requirements.txt
pip install pytest black flake8
python -m pytest
black *.py
flake8 *.py
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

### Quick Links by Platform

| Platform   | Quick Start            | Full Guide                           |
| ---------- | ---------------------- | ------------------------------------ |
| 🖥️ Windows | Run `launcher.bat`     | [README.md](README.md)               |
| 🐧 Linux   | `./launcher.sh`        | [README_UNIX.md](README_UNIX.md)     |
| 🍎 macOS   | `./launcher.sh`        | [README_UNIX.md](README_UNIX.md)     |
| 🤖 Android | `./launcher_termux.sh` | [README_TERMUX.md](README_TERMUX.md) |

## �🙏 Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Download engine
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [FFmpeg](https://ffmpeg.org/) - Video processing
- [MoviePy](https://zulko.github.io/moviepy/) - Video editing

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/diorhc/YouTube-Downloader/issues)
- **Discussions:** [GitHub Discussions](https://github.com/diorhc/YouTube-Downloader/discussions)
- **Documentation:** This README and inline code comments

---

<p align="center">
<strong>🎬 Made with ❤️ for the YouTube downloading community</strong><br>
<em>Star ⭐ this repository if you find it useful!</em>
</p>
