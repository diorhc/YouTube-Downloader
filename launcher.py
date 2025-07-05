#!/usr/bin/env python3
"""
Universal Cross-Platform Launcher for YouTube Downloader
Works on Windows, macOS, and Linux without installation
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

class CrossPlatformLauncher:
    def __init__(self):
        self.script_dir = Path(__file__).parent.absolute()
        self.system = platform.system().lower()
        self.python_cmd = self.find_python()
        
    def find_python(self):
        """Find the best Python executable to use"""
        # Check for embedded Python first (Windows)
        embedded_python = self.script_dir / "python_embedded" / "python.exe"
        if embedded_python.exists():
            return str(embedded_python)
            
        # Check for system Python
        python_commands = ["python3", "python"]
        for cmd in python_commands:
            if shutil.which(cmd):
                try:
                    result = subprocess.run([cmd, "--version"], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0 and "Python 3" in result.stdout:
                        return cmd
                except:
                    continue
                    
        return None
    
    def check_dependencies(self):
        """Check if required dependencies are installed"""
        try:
            import flask
            import youtube_downloader
            return True
        except ImportError:
            return False
    
    def install_dependencies(self):
        """Install dependencies using pip"""
        if not self.python_cmd:
            print("❌ Python not found. Please install Python 3.7+ first.")
            return False
            
        print("📦 Installing dependencies...")
        try:
            cmd = [self.python_cmd, "-m", "pip", "install", "-r", "requirements.txt"]
            result = subprocess.run(cmd, cwd=self.script_dir, check=True)
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            return False
    
    def start_web_interface(self):
        """Start the web interface"""
        if not self.python_cmd:
            print("❌ Python not found!")
            return False
            
        print("🚀 Starting web interface...")
        try:
            subprocess.run([self.python_cmd, "web_app.py"], cwd=self.script_dir)
            return True
        except KeyboardInterrupt:
            print("\n👋 Web interface stopped.")
            return True
        except Exception as e:
            print(f"❌ Failed to start web interface: {e}")
            return False
    
    def show_cli_help(self):
        """Show command line help"""
        print("""
📖 Command Line Usage:
   python youtube_downloader.py "VIDEO_URL" [options]

🔧 Options:
   -q, --quality     Video quality (best, 4k, 1080p, 720p, 480p, 360p)
   -m, --mode        Download mode (auto, ultra, standard)
   -o, --output      Output filename
   --audio-only      Download audio only

💡 Examples:
   python youtube_downloader.py "https://youtube.com/watch?v=dQw4w9WgXcQ"
   python youtube_downloader.py "URL" -q 1080p -m ultra
   python youtube_downloader.py "URL" --audio-only
        """)
    
    def create_downloads_dir(self):
        """Create downloads directory if it doesn't exist"""
        downloads_dir = self.script_dir / "downloads"
        downloads_dir.mkdir(exist_ok=True)
    
    def print_header(self):
        """Print application header"""
        print("╔" + "═" * 60 + "╗")
        print("║" + " " * 18 + "YouTube Downloader" + " " * 23 + "║")
        print("║" + " " * 15 + "Cross-Platform Edition" + " " * 22 + "║")
        print("╚" + "═" * 60 + "╝")
        print()
        print(f"🖥️  Platform: {platform.system()} {platform.release()}")
        print(f"🐍 Python: {self.python_cmd or 'Not found'}")
        print(f"📁 Location: {self.script_dir}")
        print()
    
    def main_menu(self):
        """Show main menu and handle user input"""
        while True:
            self.print_header()
            
            print("🎯 Choose an option:")
            print("   1. 🌐 Start Web Interface")
            print("   2. 📖 Command Line Help")
            print("   3. 📦 Setup Dependencies")
            print("   4. 🔍 Check System Status")
            print("   5. 🚪 Exit")
            print()
            
            try:
                choice = input("Enter choice (1-5): ").strip()
                
                if choice == "1":
                    self.create_downloads_dir()
                    if not self.check_dependencies():
                        print("❌ Dependencies not installed. Installing now...")
                        if not self.install_dependencies():
                            input("\nPress Enter to continue...")
                            continue
                    self.start_web_interface()
                    
                elif choice == "2":
                    self.show_cli_help()
                    input("\nPress Enter to continue...")
                    
                elif choice == "3":
                    self.install_dependencies()
                    input("\nPress Enter to continue...")
                    
                elif choice == "4":
                    self.show_system_status()
                    input("\nPress Enter to continue...")
                    
                elif choice == "5":
                    print("👋 Goodbye!")
                    break
                    
                else:
                    print("❌ Invalid choice. Please try again.")
                    input("\nPress Enter to continue...")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except EOFError:
                break
    
    def show_system_status(self):
        """Show system status and diagnostics"""
        print("\n🔍 System Status:")
        print("=" * 50)
        
        # Python status
        if self.python_cmd:
            try:
                result = subprocess.run([self.python_cmd, "--version"], 
                                      capture_output=True, text=True, timeout=5)
                print(f"✅ Python: {result.stdout.strip()}")
            except:
                print(f"⚠️  Python: Found but version check failed")
        else:
            print("❌ Python: Not found")
        
        # Dependencies status
        deps_status = self.check_dependencies()
        print(f"{'✅' if deps_status else '❌'} Dependencies: {'Installed' if deps_status else 'Missing'}")
        
        # FFmpeg status (for moviepy)
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            print(f"✅ FFmpeg: {ffmpeg_path}")
        else:
            # Check embedded ffmpeg
            embedded_ffmpeg = self.script_dir / "python_embedded" / "bin" / "ffmpeg.exe"
            if embedded_ffmpeg.exists():
                print(f"✅ FFmpeg: {embedded_ffmpeg} (embedded)")
            else:
                print("⚠️  FFmpeg: Not found (ultra mode may not work)")
        
        # yt-dlp status
        ytdlp_path = shutil.which("yt-dlp")
        if ytdlp_path:
            print(f"✅ yt-dlp: {ytdlp_path}")
        else:
            embedded_ytdlp = self.script_dir / "python_embedded" / "Scripts" / "yt-dlp.exe"
            if embedded_ytdlp.exists():
                print(f"✅ yt-dlp: {embedded_ytdlp} (embedded)")
            else:
                print("⚠️  yt-dlp: Not found in PATH (but may be installed via pip)")
        
        # Downloads directory
        downloads_dir = self.script_dir / "downloads"
        print(f"{'✅' if downloads_dir.exists() else '📁'} Downloads: {downloads_dir}")
        
        print()

if __name__ == "__main__":
    launcher = CrossPlatformLauncher()
    launcher.main_menu()