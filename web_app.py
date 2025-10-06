#!/usr/bin/env python3
"""
YouTube Downloader Web Interface

Flask-based web interface for multi-platform video downloads.
Features:
- Real-time progress tracking via Server-Sent Events (SSE)
- Multiple quality options
- Audio-only downloads
- Download history
- Secure file handling
"""

import os
import json
import threading
import sys
import uuid
import tempfile
import subprocess
import platform
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify, send_file, make_response, Response
import time

from youtube_downloader import YouTubeDownloader

# Initialize Flask app with optimized configuration
app = Flask(__name__)

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
                    # Persist file_path if present and not already stored
                    fp = progress.get('file_path')
                    if fp:
                        try:
                            # Save resolved absolute path into completed_downloads
                            resolved = str(Path(fp).resolve())
                            if download_id in completed_downloads:
                                completed_downloads[download_id]['file_path'] = resolved
                            elif download_id in active_downloads:
                                active_downloads[download_id]['file_path'] = resolved
                            progress['file_path'] = resolved
                        except Exception:
                            pass
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
    """Web version of the multi-platform downloader."""
    
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

# Security helper functions
def validate_safe_path(requested_path: str, base_dir: Path) -> Optional[Path]:
    """
    Validate that requested_path is safely within base_dir.
    Returns resolved Path if safe, None otherwise.
    Prevents path traversal attacks.
    """
    try:
        # Resolve both paths to absolute paths
        base_resolved = base_dir.resolve()
        requested_resolved = (base_dir / requested_path).resolve()
        
        # Check if requested path is within base directory
        requested_resolved.relative_to(base_resolved)
        
        return requested_resolved
    except (ValueError, Exception):
        return None

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

        # Allow client to request insecure SSL (skip certificate verification)
        insecure_ssl = bool(data.get('insecure_ssl')) if data else False

        # Use threading instead of signal for cross-platform timeout
        info_result = [None]
        error_result = [None]
        
        def get_info_thread():
            try:
                print(f"[DEBUG] Getting video info for URL: {url}")
                # Temporarily set insecure flag for this downloader
                prev_insecure = getattr(downloader, 'insecure_ssl', False)
                try:
                    downloader.insecure_ssl = insecure_ssl
                    info_result[0] = downloader.get_video_info(url)
                finally:
                    downloader.insecure_ssl = prev_insecure
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
        
        # Track available audio languages
        audio_languages = {}  # {language_code: language_name}
        
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
            
            # Extract audio language information
            if fmt.get('acodec') and fmt.get('acodec') != 'none':
                lang_code = fmt.get('language') or fmt.get('lang') or 'unknown'
                lang_name = fmt.get('language_name') or lang_code
                if lang_code and lang_code != 'unknown':
                    audio_languages[lang_code] = lang_name
        
        # Debug: Print found resolutions and formats for troubleshooting
        print(f"DEBUG: Found resolutions: {sorted(found_resolutions, reverse=True)}")
        print(f"DEBUG: Available qualities: {sorted(qualities, key=lambda x: {'4K': 2160, '1440p': 1440, '1080p': 1080, '720p': 720, '480p': 480, '360p': 360, '240p': 240, '144p': 144}.get(x, 0), reverse=True)}")
        print(f"DEBUG: Available audio languages: {audio_languages}")
        
        # Sort qualities by resolution
        quality_order = {'4K': 2160, '1440p': 1440, '1080p': 1080, '720p': 720, '480p': 480, '360p': 360, '240p': 240, '144p': 144}
        video_info['available_qualities'] = sorted(
            qualities, 
            key=lambda x: quality_order.get(x, 0), 
            reverse=True
        )
        
        # Add available audio languages to response
        video_info['available_audio_languages'] = [
            {'code': code, 'name': name} 
            for code, name in sorted(audio_languages.items())
        ]
        
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

        url = (data.get('url') or '').strip()
        if not url:
            resp = make_response(json.dumps({'error': 'URL cannot be empty'}), 400)
            resp.headers['Content-Type'] = 'application/json; charset=utf-8'
            return resp

        quality = data.get('quality', 'best')
        audio_only = data.get('audio_only', False)
        audio_language = data.get('audio_language')
        output_name = (data.get('output_name') or '').strip() or None
        insecure_ssl = bool(data.get('insecure_ssl'))

        print(f"[DEBUG] Received output_name for download: {output_name}")
        print(f"[DEBUG] Received audio_language for download: {audio_language}")

        download_id = str(uuid.uuid4())

        def download_task():
            prev_insecure = getattr(downloader, 'insecure_ssl', False)
            try:
                downloader.insecure_ssl = insecure_ssl
                downloader.audio_only = audio_only
                downloader.audio_language = audio_language
                downloader.set_download_id(download_id)

                if download_id in active_downloads:
                    state = active_downloads[download_id]
                    state['requested_quality'] = quality
                    state['insecure_ssl'] = insecure_ssl

                    notices = state.get('download_notice')
                    if insecure_ssl:
                        warning = 'SSL verification disabled for this download.'
                        notices = f"{notices} {warning}".strip() if notices else warning

                    if not downloader.merger.ffmpeg_available and quality.lower() not in ['360p', 'best']:
                        extra_notice = (
                            f'Requested {quality}, but only 360p available due to no FFmpeg. '
                            'Install FFmpeg for higher quality downloads.'
                        )
                        notices = f"{notices} {extra_notice}".strip() if notices else extra_notice

                    if notices:
                        state['download_notice'] = notices

                success = downloader.download_video(url, quality, audio_only, output_name)
                if not success and download_id in active_downloads:
                    active_downloads[download_id]['status'] = 'error'
                    active_downloads[download_id]['error'] = 'Download failed'
            except Exception as e:
                if download_id in active_downloads:
                    active_downloads[download_id]['status'] = 'error'
                    active_downloads[download_id]['error'] = str(e)
            finally:
                downloader.insecure_ssl = prev_insecure

        thread = threading.Thread(target=download_task, daemon=True)
        thread.start()

        resp = make_response(json.dumps({'download_id': download_id, 'insecure_ssl': insecure_ssl}), 200)
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp
    except Exception as e:
        resp = make_response(json.dumps({'error': f'Server error: {str(e)}'}), 500)
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp


@app.route('/api/progress/<download_id>')
def get_progress(download_id: str):
    """Get download progress efficiently."""
    try:
        if download_id in active_downloads:
            progress = active_downloads[download_id].copy()
        elif download_id in completed_downloads:
            progress = completed_downloads[download_id].copy()
        else:
            return jsonify({'error': 'Download not found'}), 404

        progress.setdefault('download_id', download_id)
        return jsonify(progress)
    except Exception as e:
        return jsonify({'error': f'Progress error: {str(e)}'}), 500


@app.route('/api/download/<download_id>/file', methods=['GET', 'HEAD', 'OPTIONS'])
def download_file(download_id: str):
    """Download completed file by ID."""
    try:
        if request.method == 'OPTIONS':
            response = make_response('', 204)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return response

        file_info = completed_downloads.get(download_id) or active_downloads.get(download_id)
        file_path = file_info.get('file_path') if file_info else None

        # If file_path is present but missing on disk, or not provided at all,
        # try to map the download id / filename to an actual file in the downloads directory.
        downloads_dir = Path('./downloads').resolve()
        def persist_found_path(found_path: Path):
            nonlocal file_path, file_info
            file_path = str(found_path)
            # Persist for future requests
            try:
                if download_id in completed_downloads:
                    completed_downloads[download_id]['file_path'] = file_path
                elif download_id in active_downloads:
                    active_downloads[download_id]['file_path'] = file_path
            except Exception:
                pass

        if file_path:
            try:
                p = Path(file_path).resolve()
                # Ensure it's inside our downloads dir
                try:
                    p.relative_to(downloads_dir)
                except ValueError:
                    # Not inside downloads dir - treat as missing for safety
                    p = None
                if not p or not p.exists():
                    file_path = None
                else:
                    file_path = str(p)
            except Exception:
                file_path = None

        # Try to locate by filename or download id if we don't have a valid file_path yet
        if (not file_path) and downloads_dir.exists():
            expected_names = set()
            if file_info:
                name = file_info.get('filename')
                if name:
                    expected_names.add(name)
                    expected_names.add(name.lower())

            # Walk the downloads directory for a best match
            for candidate in downloads_dir.glob('*'):
                if not candidate.is_file():
                    continue

                candidate_name = candidate.name
                match = False
                if expected_names:
                    if candidate_name in expected_names or candidate_name.lower() in expected_names:
                        match = True
                else:
                    if download_id in candidate_name:
                        match = True

                # Also accept case-insensitive or partial matches if nothing exact found
                if not match and expected_names:
                    for en in expected_names:
                        if en and (en in candidate_name or candidate_name in en or candidate_name.lower() == en.lower()):
                            match = True
                            break

                if match:
                    persist_found_path(candidate.resolve())
                    break

        if file_path and os.path.exists(file_path):
            if request.method == 'HEAD':
                response = make_response('', 200)
            else:
                filename = os.path.basename(file_path)
                if isinstance(filename, bytes):
                    filename = filename.decode('utf-8', errors='ignore')
                try:
                    response = send_file(file_path, as_attachment=True, download_name=filename)
                except TypeError:
                    response = send_file(file_path, as_attachment=True, attachment_filename=filename)

            notice = file_info.get('download_notice') if file_info else None
            if notice:
                response.headers['X-Download-Notice'] = notice

            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['Referrer-Policy'] = 'no-referrer'
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return response

        downloads_dir = Path('./downloads')
        if downloads_dir.exists():
            expected_names = set()
            if file_info:
                name = file_info.get('filename')
                if name:
                    expected_names.add(name)
                    expected_names.add(name.lower())
            for candidate in downloads_dir.glob('*'):
                if not candidate.is_file():
                    continue

                candidate_name = candidate.name
                if expected_names and candidate_name not in expected_names and candidate_name.lower() not in expected_names:
                    continue

                if not expected_names and download_id not in candidate_name:
                    continue

                if request.method == 'HEAD':
                    response = make_response('', 200)
                else:
                    filename = candidate_name
                    if isinstance(filename, bytes):
                        filename = filename.decode('utf-8', errors='ignore')
                    try:
                        response = send_file(str(candidate), as_attachment=True, download_name=filename)
                    except TypeError:
                        response = send_file(str(candidate), as_attachment=True, attachment_filename=filename)

                response.headers['X-Content-Type-Options'] = 'nosniff'
                response.headers['X-Frame-Options'] = 'DENY'
                response.headers['Referrer-Policy'] = 'no-referrer'
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
                response.headers['X-Fallback-Download'] = 'true'
                return response

        return jsonify({'error': 'File not found or no longer available'}), 404
    except Exception as e:
        print(f"Download error for {download_id}: {str(e)}")
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
        
        # Validate filename doesn't contain path separators
        if os.path.sep in safe_filename or (os.path.altsep and os.path.altsep in safe_filename):
            return jsonify({'error': 'Invalid filename'}), 400
        
        # Additional validation - reject suspicious patterns
        if '..' in safe_filename or safe_filename.startswith('.'):
            return jsonify({'error': 'Invalid filename'}), 400
        
        downloads_dir = Path('./downloads').resolve()
        file_path = validate_safe_path(safe_filename, downloads_dir)
        
        if not file_path or not file_path.exists() or not file_path.is_file():
            # Try to find files that might match closely
            if downloads_dir.exists():
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
        
        if not file_path or not file_path.exists() or not file_path.is_file():
            return jsonify({'error': 'File not found'}), 404 if request.method == 'GET' else ('', 404)
        
        # Double-check the file is still within downloads directory
        try:
            file_path.relative_to(downloads_dir)
        except ValueError:
            return jsonify({'error': 'Access denied'}), 403
        
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

@app.route('/api/open_file', methods=['POST'])
def open_file():
    """Open a downloaded file locally using the system default video player."""
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        file_path = data.get('file_path') or data.get('filePath')
        if not file_path:
            return jsonify({'error': 'file_path is required'}), 400
        
        # Sanitize and validate path
        downloads_dir = Path('./downloads').resolve()
        
        # Handle both absolute and relative paths
        if os.path.isabs(file_path):
            target_path = Path(file_path).resolve()
        else:
            target_path = (downloads_dir / file_path).resolve()
        
        # Validate path is within downloads directory (prevent path traversal)
        try:
            target_path.relative_to(downloads_dir)
        except ValueError:
            print(f"Security: Attempted access outside downloads directory: {file_path}")
            return jsonify({'error': 'File outside downloads directory is not allowed'}), 403

        if not target_path.exists() or not target_path.is_file():
            return jsonify({'error': 'File not found'}), 404

        system = platform.system()
        try:
            if system == 'Windows':
                os.startfile(str(target_path))  # type: ignore[attr-defined]
            elif system == 'Darwin':
                subprocess.Popen(['open', str(target_path)])
            else:  # Linux and other Unix-like systems
                subprocess.Popen(['xdg-open', str(target_path)])
        except Exception as open_err:
            print(f"Error opening file: {open_err}")
            return jsonify({'error': f'Unable to open file: {open_err}'}), 500

        return jsonify({'status': 'opened', 'file': target_path.name})

    except Exception as e:
        print(f"Unexpected error in open_file: {str(e)}")
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

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


@app.route('/api/completed_downloads', methods=['GET'])
def list_completed_downloads():
    """Return a JSON list of completed downloads. Secured with a token.

    Use environment variable DOWNLOADS_API_TOKEN or app.config['DOWNLOADS_API_TOKEN']
    to protect this endpoint.
    """
    try:
        token = os.environ.get('DOWNLOADS_API_TOKEN') or app.config.get('DOWNLOADS_API_TOKEN')
        if token:
            req_token = request.headers.get('X-API-Token') or request.args.get('token')
            if not req_token or req_token != token:
                return jsonify({'error': 'Unauthorized'}), 401

        # Build a minimal safe listing
        results = []
        for did, info in completed_downloads.items():
            results.append({
                'download_id': did,
                'filename': info.get('filename'),
                'file_path': info.get('file_path'),
                'status': info.get('status', 'completed'),
                'downloaded_bytes': info.get('downloaded_bytes'),
                'total_bytes': info.get('total_bytes'),
                'timestamp': info.get('started_at') or info.get('timestamp')
            })

        return jsonify({'completed': results}), 200
    except Exception as e:
        print(f'Error listing completed downloads: {e}')
        return jsonify({'error': f'Internal error: {e}'}), 500

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
    print("🔁 Press Ctrl+R to restart the server")
    
    try:
        # Try to use production server (Waitress)
        from waitress import serve
        print("\U0001f3ed Using production server (Waitress)")

        # Start a background thread to watch for Ctrl+R in console (Windows)
        def restart_watcher():
            try:
                if os.name == 'nt':
                    import msvcrt
                    while True:
                        if msvcrt.kbhit():
                            ch = msvcrt.getch()
                            # Ctrl+R sends ASCII 18 (0x12)
                            if ch == b'\x12':
                                print('\n[INFO] Ctrl+R detected — restarting server...')
                                time.sleep(0.2)
                                os.execv(sys.executable, [sys.executable] + sys.argv)
                        time.sleep(0.1)
                else:
                    # For POSIX, listen for SIGUSR1 as restart signal
                    import signal
                    def _handler(signum, frame):
                        print('\n[INFO] Restart signal received — restarting server...')
                        os.execv(sys.executable, [sys.executable] + sys.argv)
                    signal.signal(signal.SIGUSR1, _handler)
            except Exception as e:
                print(f'[WARN] restart_watcher error: {e}')

        watcher = threading.Thread(target=restart_watcher, daemon=True)
        watcher.start()
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