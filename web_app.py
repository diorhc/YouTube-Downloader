#!/usr/bin/env python3
"""
YouTube Downloader Web Interface
Flask-based web interface with improved performance.
"""

import os
import json
import threading
import sys
import uuid  # Import before numpy to avoid shadowing
import tempfile
from datetime import datetime  # Import before numpy to avoid shadowing
from typing import Dict, Any, Optional  # Import before numpy to avoid shadowing
from pathlib import Path

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify, send_file, make_response
from youtube_downloader import YouTubeDownloader

# Initialize Flask app with optimized configuration
app = Flask(__name__)
from flask import Response
import time

# SSE: Stream download progress updates
@app.route('/api/progress_sse/<download_id>')
def progress_sse(download_id: str):
    def event_stream():
        last_progress = None
        while True:
            if download_id in active_downloads:
                progress = active_downloads[download_id]
            elif download_id in completed_downloads:
                progress = completed_downloads[download_id]
            else:
                yield f"event: error\ndata: Download not found\n\n"
                break
            # Only send if progress changed
            if progress != last_progress:
                # Always include download_id and filename in the final event if possible
                if progress.get('status') == 'completed':
                    progress = progress.copy()
                    progress['download_id'] = download_id
                    if 'filename' not in progress or not progress['filename']:
                        # Try to get filename from completed_downloads
                        cd = completed_downloads.get(download_id)
                        if cd and 'filename' in cd:
                            progress['filename'] = cd['filename']
                yield f"data: {json.dumps(progress)}\n\n"
                last_progress = progress.copy()
            if progress.get('status') in ['completed', 'error']:
                break
            time.sleep(1)
    return Response(event_stream(), mimetype='text/event-stream')
app.config.update(
    SECRET_KEY=os.urandom(24),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB max
    JSON_SORT_KEYS=False,
    JSONIFY_PRETTYPRINT_REGULAR=False,  # Optimize JSON responses
)

# Global variables for tracking downloads (optimized structure)
active_downloads: Dict[str, Dict[str, Any]] = {}
completed_downloads: Dict[str, Dict[str, Any]] = {}

class WebDownloader(YouTubeDownloader):
    """Web version of YouTube downloader."""
    
    def __init__(self, download_path: str = "./downloads"):
        super().__init__(download_path)
        self.download_id: Optional[str] = None
    
    def set_download_id(self, download_id: str) -> None:
        """Set download ID for progress tracking."""
        self.download_id = download_id
        # Store audio_only flag for frontend display
        active_downloads[download_id] = {
            'status': 'starting',
            'progress': 0,
            'filename': '',
            'ultra_mode': self.merger.available,
            'error': None,
            'started_at': datetime.now().isoformat(),
            'downloaded_bytes': 0,
            'total_bytes': 0,
            'audio_only': getattr(self, 'audio_only', False)
        }
        # Set up progress callback
        self.set_progress_hook(self._web_progress_hook)
    
    def _web_progress_hook(self, d: Dict[str, Any]) -> None:
        """Optimized progress hook for web interface."""
        if not self.download_id or self.download_id not in active_downloads:
            return
        download_info = active_downloads[self.download_id]
        try:
            if d['status'] == 'downloading':
                download_info['status'] = 'downloading'
                download_info['downloaded_bytes'] = d.get('downloaded_bytes', 0)
                # Propagate audio_only flag for frontend
                if hasattr(self, 'audio_only'):
                    download_info['audio_only'] = self.audio_only
                if 'total_bytes' in d and d['total_bytes']:
                    download_info['total_bytes'] = d['total_bytes']
                    download_info['progress'] = (d['downloaded_bytes'] / d['total_bytes']) * 100
            elif d['status'] == 'finished':
                # Check if this is just a segment finishing or the entire download
                if 'fragment_index' in d or 'fragment_count' in d:
                    # This is just a fragment/segment finishing, not the entire download
                    return
                
                # For video downloads, don't mark as complete if this is just audio finishing
                # Check if filename suggests this is just one part of a multi-part download
                filename = d.get('filename', '')
                # Check if this is a temp file (indicating separate stream download)
                is_temp_file = 'temp' in filename.lower() or 'tmp' in filename.lower()
                is_partial_stream = ('audio' in filename.lower() or 'video' in filename.lower() or 
                                   filename.endswith('.webm') or filename.endswith('.m4a') or is_temp_file)
                
                if (not getattr(self, 'audio_only', False) and is_partial_stream):
                    # This is likely just audio/video portion finishing, not complete download
                    download_info['status'] = 'processing'
                    return
                
                # Only mark as completed when the entire download is actually finished
                filename = Path(d['filename']).name
                download_info.update({
                    'status': 'completed',
                    'progress': 100,  # Ensure 100% progress
                    'filename': filename,
                    'file_path': d['filename']
                })
                # Propagate audio_only flag for frontend
                if hasattr(self, 'audio_only'):
                    download_info['audio_only'] = self.audio_only
                # Move to completed downloads only when truly finished
                completed_downloads[self.download_id] = download_info.copy()
                del active_downloads[self.download_id]
        except Exception as e:
            print(f'[ERROR] Exception in _web_progress_hook: {e}')
            import traceback
            traceback.print_exc()


# Global downloader instance
downloader = WebDownloader()

# Cancel download endpoint
@app.route('/api/cancel_download', methods=['POST'])
def cancel_download():
    """Cancel an active download by ID."""
    data = request.get_json()
    download_id = data.get('download_id') if data else None
    if not download_id or download_id not in active_downloads:
        return jsonify({'error': 'Invalid or missing download_id'}), 400
    active_downloads[download_id]['cancelled'] = True
    return jsonify({'status': 'cancelled'})

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')

@app.route('/api/video_info', methods=['POST'])
def get_video_info():
    """Get video information efficiently with timeout handling."""
    import signal
    import threading
    
    def timeout_handler(signum, frame):
        raise TimeoutError("Video info request timed out")
    
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            resp = make_response(json.dumps({'error': 'URL is required'}), 400)
            resp.headers['Content-Type'] = 'application/json; charset=utf-8'
            return resp
        url = data['url']
        if not url:
            resp = make_response(json.dumps({'error': 'URL is required'}), 400)
            resp.headers['Content-Type'] = 'application/json; charset=utf-8'
            return resp
        url = url.strip()
        if not url:
            resp = make_response(json.dumps({'error': 'URL cannot be empty'}), 400)
            resp.headers['Content-Type'] = 'application/json; charset=utf-8'
            return resp
        
        # Use threading instead of signal for cross-platform timeout
        info_result = [None]
        error_result = [None]
        
        def get_info_thread():
            try:
                print(f"[DEBUG] Getting video info for URL: {url}")
                info_result[0] = downloader.get_video_info(url)
                print(f"[DEBUG] Video info retrieved successfully")
            except Exception as e:
                print(f"[DEBUG] Error in get_info_thread: {e}")
                error_result[0] = str(e)
        
        thread = threading.Thread(target=get_info_thread, daemon=True)
        thread.start()
        thread.join(timeout=45)  # 45 second timeout
        
        if thread.is_alive():
            resp = make_response(json.dumps({'error': 'Request timed out. Please try again.'}), 408)
            resp.headers['Content-Type'] = 'application/json; charset=utf-8'
            return resp
        
        if error_result[0]:
            resp = make_response(json.dumps({'error': f'Error: {error_result[0]}'}), 500)
            resp.headers['Content-Type'] = 'application/json; charset=utf-8'
            return resp
        
        info = info_result[0]
        if not info:
            resp = make_response(json.dumps({'error': 'Could not retrieve video information'}), 400)
            resp.headers['Content-Type'] = 'application/json; charset=utf-8'
            return resp
            
        # Extract and optimize video information
        video_info = {
            'title': info.get('title', 'Unknown'),
            'duration': info.get('duration_string', 'Unknown'),
            'uploader': info.get('uploader', 'Unknown'),
            'view_count': info.get('view_count', 0),
            'thumbnail': info.get('thumbnail', ''),
        }
        # Extract available qualities efficiently with improved resolution detection
        formats = info.get('formats', [])
        qualities = set()
        
        # Track actual resolutions found to avoid duplicates
        found_resolutions = set()
        
        for fmt in formats:
            height = fmt.get('height')
            if height and isinstance(height, int):
                # Map heights to standard quality names with ranges
                if height >= 2000:  # 4K range (2160p and above)
                    qualities.add('4K')
                    found_resolutions.add(2160)
                elif height >= 1350:  # 1440p range
                    qualities.add('1440p')
                    found_resolutions.add(1440)
                elif height >= 1000:  # 1080p range
                    qualities.add('1080p')
                    found_resolutions.add(1080)
                elif height >= 650:  # 720p range
                    qualities.add('720p')
                    found_resolutions.add(720)
                elif height >= 420:  # 480p range (420-649)
                    qualities.add('480p')
                    found_resolutions.add(480)
                elif height >= 300:  # 360p range (300-419)
                    qualities.add('360p')
                    found_resolutions.add(360)
                elif height >= 200:  # 240p range
                    qualities.add('240p')
                    found_resolutions.add(240)
                elif height >= 100:  # 144p range
                    qualities.add('144p')
                    found_resolutions.add(144)
        
        # Debug: Print found resolutions and formats for troubleshooting
        print(f"DEBUG: Found resolutions: {sorted(found_resolutions, reverse=True)}")
        print(f"DEBUG: Available qualities: {sorted(qualities, key=lambda x: {'4K': 2160, '1440p': 1440, '1080p': 1080, '720p': 720, '480p': 480, '360p': 360, '240p': 240, '144p': 144}.get(x, 0), reverse=True)}")
        
        # Sort qualities by resolution
        quality_order = {'4K': 2160, '1440p': 1440, '1080p': 1080, '720p': 720, '480p': 480, '360p': 360, '240p': 240, '144p': 144}
        video_info['available_qualities'] = sorted(
            qualities, 
            key=lambda x: quality_order.get(x, 0), 
            reverse=True
        )
        # Debug: Show available formats for troubleshooting
        debug_info = downloader.debug_available_formats(url)
        
        resp = make_response(json.dumps(video_info), 200)
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp
    except Exception as e:
        resp = make_response(json.dumps({'error': f'Server error: {str(e)}'}), 500)
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp

@app.route('/api/download', methods=['POST'])
def start_download():
    """Start video download with optimized error handling."""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            resp = make_response(json.dumps({'error': 'URL is required'}), 400)
            resp.headers['Content-Type'] = 'application/json; charset=utf-8'
            return resp
        url = data['url']
        if not url:
            resp = make_response(json.dumps({'error': 'URL is required'}), 400)
            resp.headers['Content-Type'] = 'application/json; charset=utf-8'
            return resp
        url = url.strip()
        quality = data.get('quality', 'best')
        audio_only = data.get('audio_only', False)
        output_name = data.get('output_name') or ''
        output_name = output_name.strip() if output_name else None
        print(f"[DEBUG] Received output_name for download: {output_name}")
        if not url:
            resp = make_response(json.dumps({'error': 'URL cannot be empty'}), 400)
            resp.headers['Content-Type'] = 'application/json; charset=utf-8'
            return resp
        # Generate unique download ID
        download_id = str(uuid.uuid4())
        # Start download in background thread
        def download_task():
            try:
                # Store audio_only flag for progress reporting
                downloader.audio_only = audio_only
                downloader.set_download_id(download_id)
                # Add quality limitation tracking
                if download_id in active_downloads:
                    active_downloads[download_id]['requested_quality'] = quality
                    # Check merging capability and add notice
                    if not downloader.merger.ffmpeg_available and quality.lower() not in ['360p', 'best']:
                        active_downloads[download_id]['download_notice'] = f'Requested {quality}, but only 360p available due to no FFmpeg. Install FFmpeg for higher quality downloads.'
                success = downloader.download_video(url, quality, audio_only, output_name)
                if not success and download_id in active_downloads:
                    active_downloads[download_id]['status'] = 'error'
                    active_downloads[download_id]['error'] = 'Download failed'
            except Exception as e:
                if download_id in active_downloads:
                    active_downloads[download_id]['status'] = 'error'
                    active_downloads[download_id]['error'] = str(e)
        # Start thread with daemon flag for cleanup
        thread = threading.Thread(target=download_task, daemon=True)
        thread.start()
        resp = make_response(json.dumps({'download_id': download_id}), 200)
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp
    except Exception as e:
        resp = make_response(json.dumps({'error': f'Server error: {str(e)}'}), 500)
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp

@app.route('/api/progress/<download_id>')
def get_progress(download_id: str):
    """Get download progress efficiently."""
    if download_id in active_downloads:
        resp = make_response(json.dumps(active_downloads[download_id]), 200)
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp
    elif download_id in completed_downloads:
        resp = make_response(json.dumps(completed_downloads[download_id]), 200)
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp
    else:
        resp = make_response(json.dumps({'error': 'Download not found'}), 404)
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp

@app.route('/api/downloads')
def list_downloads():
    """List all downloads efficiently."""
    # Combine and limit downloads for performance
    all_downloads = {}
    # Add recent completed downloads (limit to last 10)
    recent_completed = dict(list(completed_downloads.items())[-10:])
    all_downloads.update(recent_completed)
    all_downloads.update(active_downloads)
    resp = make_response(json.dumps(all_downloads), 200)
    resp.headers['Content-Type'] = 'application/json; charset=utf-8'
    return resp

@app.route('/api/files')
def list_files():
    """List available files in downloads directory (for debugging)."""
    try:
        downloads_dir = Path('./downloads')
        if not downloads_dir.exists():
            return jsonify({'files': []})
        
        files = []
        for file_path in downloads_dir.glob('*'):
            if file_path.is_file():
                files.append({
                    'name': file_path.name,
                    'size': file_path.stat().st_size,
                    'modified': file_path.stat().st_mtime
                })
        
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<download_id>', methods=['GET', 'HEAD'])
def download_file(download_id: str):
    """Download completed file with error handling and fallback to direct file serving."""
    try:
        # Handle HEAD request - just check if file exists
        if request.method == 'HEAD':
            if download_id in completed_downloads:
                file_info = completed_downloads[download_id]
                file_path = file_info.get('file_path')
                if file_path and os.path.exists(file_path):
                    return '', 200
            
            # Fallback: Check if file exists in downloads directory
            downloads_dir = Path('./downloads')
            if downloads_dir.exists():
                for file_path in downloads_dir.glob('*'):
                    if file_path.is_file():
                        return '', 200
            
            return '', 404
        
        # Handle GET request - actual file download
        if download_id in completed_downloads:
            file_info = completed_downloads[download_id]
            file_path = file_info.get('file_path')
            if file_path and os.path.exists(file_path):
                try:
                    filename = os.path.basename(file_path)
                    # Ensure filename is properly encoded
                    if isinstance(filename, bytes):
                        filename = filename.decode('utf-8', errors='ignore')
                    
                    try:
                        # Try newer Flask version parameter first
                        response = send_file(file_path, as_attachment=True, download_name=filename)
                    except TypeError:
                        # Fallback to older Flask version parameter
                        response = send_file(file_path, as_attachment=True, attachment_filename=filename)
                    
                    # Add notice header if present
                    notice = file_info.get('download_notice')
                    if notice:
                        response.headers['X-Download-Notice'] = notice
                    
                    # Add security headers
                    response.headers['X-Content-Type-Options'] = 'nosniff'
                    response.headers['X-Frame-Options'] = 'DENY'
                    response.headers['Referrer-Policy'] = 'no-referrer'
                    # Add CORS headers for better compatibility
                    response.headers['Access-Control-Allow-Origin'] = '*'
                    response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
                    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
                    
                    return response
                except Exception as e:
                    print(f"Download error for {download_id}: {str(e)}")
                    return jsonify({'error': f'Download error: {str(e)}'}), 500
        
        # Fallback: Try to find file in downloads directory by matching filename pattern
        # This helps when server restarts but files still exist
        downloads_dir = Path('./downloads')
        if downloads_dir.exists():
            # Look for any file that might match the download_id pattern
            for file_path in downloads_dir.glob('*'):
                if file_path.is_file():
                    try:
                        filename = file_path.name
                        # Ensure filename is properly encoded
                        if isinstance(filename, bytes):
                            filename = filename.decode('utf-8', errors='ignore')
                        
                        try:
                            response = send_file(str(file_path), as_attachment=True, download_name=filename)
                        except TypeError:
                            response = send_file(str(file_path), as_attachment=True, attachment_filename=filename)
                        
                        response.headers['X-Content-Type-Options'] = 'nosniff'
                        response.headers['X-Frame-Options'] = 'DENY'
                        response.headers['Referrer-Policy'] = 'no-referrer'
                        response.headers['Access-Control-Allow-Origin'] = '*'
                        response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
                        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
                        # Add a header to indicate this was a fallback
                        response.headers['X-Fallback-Download'] = 'true'
                        return response
                    except Exception as e:
                        print(f"Fallback download error for {file_path}: {str(e)}")
                        continue
        
        # No file found
        return jsonify({'error': 'File not found or no longer available'}), 404
    
    except Exception as e:
        print(f"General download error for {download_id}: {str(e)}")
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@app.route('/download_by_filename/<path:filename>', methods=['GET', 'HEAD'])
def download_by_filename(filename: str):
    """Download file by filename - backup method when download ID is not available."""
    try:
        # Sanitize filename to prevent directory traversal
        safe_filename = os.path.basename(filename)
        # Handle URL encoding/decoding
        try:
            from urllib.parse import unquote
            safe_filename = unquote(safe_filename)
        except Exception:
            pass
        
        file_path = Path('./downloads') / safe_filename
        
        # Also try to find files that might match closely
        if not file_path.exists():
            downloads_dir = Path('./downloads')
            if downloads_dir.exists():
                # Try to find a file that matches the filename pattern
                for existing_file in downloads_dir.glob('*'):
                    if existing_file.is_file():
                        existing_name = existing_file.name
                        # Try exact match first
                        if existing_name == safe_filename:
                            file_path = existing_file
                            break
                        # Try case-insensitive match
                        elif existing_name.lower() == safe_filename.lower():
                            file_path = existing_file
                            break
                        # Try partial match (useful for files with special characters)
                        elif safe_filename in existing_name or existing_name in safe_filename:
                            file_path = existing_file
                            break
        
        if not file_path.exists() or not file_path.is_file():
            return jsonify({'error': 'File not found'}), 404 if request.method == 'GET' else ('', 404)
        
        # Handle HEAD request - just check if file exists
        if request.method == 'HEAD':
            return '', 200
        
        # Handle GET request - actual file download
        try:
            filename_to_send = file_path.name
            # Ensure filename is properly encoded
            if isinstance(filename_to_send, bytes):
                filename_to_send = filename_to_send.decode('utf-8', errors='ignore')
            
            try:
                # Try newer Flask version parameter first
                response = send_file(str(file_path), as_attachment=True, download_name=filename_to_send)
            except TypeError:
                # Fallback to older Flask version parameter
                response = send_file(str(file_path), as_attachment=True, attachment_filename=filename_to_send)
            
            # Add security headers
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['Referrer-Policy'] = 'no-referrer'
            # Add CORS headers for better compatibility
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            
            return response
        except Exception as e:
            print(f"Error sending file {file_path}: {str(e)}")
            return jsonify({'error': f'Download error: {str(e)}'}), 500
    
    except Exception as e:
        print(f"General error in download_by_filename for {filename}: {str(e)}")
        return jsonify({'error': f'Download error: {str(e)}'}), 500

@app.route('/api/debug_formats', methods=['POST'])
def debug_formats():
    """Debug endpoint to show available formats for a video."""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400
        
        url = data['url'].strip()
        if not url:
            return jsonify({'error': 'URL cannot be empty'}), 400
        
        # Get debug format information
        debug_info = downloader.debug_available_formats(url)
        
        return jsonify({
            'url': url,
            'debug_info': debug_info,
            'message': 'Debug information logged to console'
        })
    
    except Exception as e:
        return jsonify({'error': f'Debug error: {str(e)}'}), 500

@app.errorhandler(404)
def not_found(error):
    resp = make_response(json.dumps({'error': 'Not found'}), 404)
    resp.headers['Content-Type'] = 'application/json; charset=utf-8'
    return resp

@app.errorhandler(500)
def internal_error(error):
    resp = make_response(json.dumps({'error': 'Internal server error'}), 500)
    resp.headers['Content-Type'] = 'application/json; charset=utf-8'
    return resp

@app.after_request
def add_security_headers(response):
    # Add security and cache headers for all responses
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    # Remove deprecated/undesired headers
    response.headers.pop('X-XSS-Protection', None)
    response.headers.pop('Expires', None)
    # Cache control for static files
    if request.path.startswith('/static/') or request.path.endswith('.js') or request.path.endswith('.css'):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response

if __name__ == '__main__':
    import platform
    
    # Ensure templates directory exists
    templates_dir = Path('templates')
    templates_dir.mkdir(exist_ok=True)
    
    # Ensure downloads directory exists
    downloads_dir = Path('downloads')
    downloads_dir.mkdir(exist_ok=True)
    
    # Platform information
    system_info = f"{platform.system()} {platform.release()}"
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    print("╔" + "═" * 60 + "╗")
    print("║" + " " * 18 + "YouTube Downloader" + " " * 24 + "║")
    print("║" + " " * 15 + "Cross-Platform Edition" + " " * 23 + "║")
    print("╚" + "═" * 60 + "╝")
    print()
    # Print platform icon and info
    platform_icons = {
        'Windows': '🪟',
        'Linux': '🐧',
        'Darwin': '🍏',
        'macOS': '🍏'
    }
    icon = platform_icons.get(platform.system(), '💻')
    print(f"{icon} Platform: {system_info}")
    print(f"🐍 Python: {python_version}")
    print("🚀 Starting YouTube Downloader Web Interface...")
    print("📱 Open your browser and go to: http://localhost:5005")
    print("🛑 Press Ctrl+C to stop the server")
    
    try:
        # Try to use production server (Waitress)
        from waitress import serve
        print("\U0001f3ed Using production server (Waitress)")
        serve(app, host='0.0.0.0', port=5005, threads=6)
    except ImportError:
        # Fallback to Flask development server with optimized settings
        print("\u26a0\ufe0f Using development server (install waitress for production)")
        app.run(
            debug=False,
            host='0.0.0.0',
            port=5005,
            threaded=True,
            use_reloader=False
        )