import os
import uuid
import glob
from flask import Flask, render_template, request, jsonify, send_file, after_this_request
import yt_dlp

app = Flask(__name__)
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ✅ Path to cookies.txt
COOKIE_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")

# Home page
@app.route('/')
def index():
    return render_template('index.html')

# Return available formats for a given URL (AJAX)
@app.route('/api/formats', methods=['POST'])
def list_formats():
    url = request.form.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    ydl_opts = { 
        'skip_download': True, 
        'quiet': True,
        'cookiefile': COOKIE_FILE   # ✅ use cookies
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    formats = []
    for f in info.get('formats', []):
        formats.append({
            'format_id': f.get('format_id'),
            'ext': f.get('ext'),
            'acodec': f.get('acodec'),
            'vcodec': f.get('vcodec'),
            'height': f.get('height'),
            'width': f.get('width'),
            'filesize': f.get('filesize'),
            'format_note': f.get('format_note'),
        })

    seen = set()
    uniq = []
    for f in formats:
        if f['format_id'] in seen:
            continue
        seen.add(f['format_id'])
        uniq.append(f)

    uniq.sort(key=lambda x: (x['height'] or -1), reverse=True)

    return jsonify({
        'title': info.get('title'),
        'thumbnail': info.get('thumbnail'),
        'formats': uniq,
    })

# Download endpoint
@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    format_id = request.form.get('format_id')
    convert_audio = request.form.get('audio') == '1'

    if not url or not format_id:
        return "Missing url or format_id", 400

    temp_id = str(uuid.uuid4())
    outtmpl = os.path.join(DOWNLOAD_DIR, f"{temp_id}.%(ext)s")

    ydl_opts = {
        'format': format_id,
        'outtmpl': outtmpl,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'cookiefile': COOKIE_FILE   # ✅ use cookies
    }

    if convert_audio:
        ydl_opts['format'] = format_id
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:
        return f"Download error: {e}", 500

    files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{temp_id}.*"))
    if not files:
        return "No file produced", 500
    filepath = files[0]

    @after_this_request
    def remove_file(response):
        try:
            os.remove(filepath)
        except Exception:
            pass
        return response

    filename = os.path.basename(filepath)
    return send_file(filepath, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
