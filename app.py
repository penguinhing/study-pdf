import os
import json
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['STATE_FILE'] = 'state.json'

socketio = SocketIO(app, cors_allowed_origins="*")

# Server state: 현재 PDF 파일과 페이지 정보
def load_state():
    """상태 파일에서 상태 불러오기"""
    if os.path.exists(app.config['STATE_FILE']):
        try:
            with open(app.config['STATE_FILE'], 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {'filename': None, 'page': 1}

def save_state():
    """현재 상태를 파일에 저장"""
    with open(app.config['STATE_FILE'], 'w', encoding='utf-8') as f:
        json.dump(current_state, f, ensure_ascii=False, indent=2)

current_state = load_state()

# Allowed extensions
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # 업로드된 파일을 현재 공유 파일로 설정
            current_state['filename'] = filename
            current_state['page'] = 1
            save_state()  # 상태 저장

            # 모든 클라이언트에게 새로운 PDF 로드 알림
            socketio.emit('update_view', {
                'filename': filename,
                'page': 1
            }, namespace='/')

            return redirect(url_for('admin'))

    return render_template('upload.html')


@app.route('/admin')
def admin():
    return render_template('admin.html',
                         filename=current_state['filename'],
                         page=current_state['page'])


@app.route('/')
def index():
    return render_template('index.html',
                         filename=current_state['filename'],
                         page=current_state['page'])


# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """클라이언트 접속 시 현재 상태 전송"""
    print(f'Client connected')
    emit('current_status', {
        'filename': current_state['filename'],
        'page': current_state['page']
    })


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@socketio.on('admin_page_change')
def handle_page_change(data):
    """관리자가 페이지를 변경했을 때"""
    page = data.get('page', 1)

    # 서버 상태 업데이트
    current_state['page'] = page
    save_state()  # 상태 저장

    print(f'Page changed to: {page}')

    # 모든 클라이언트에게 브로드캐스트
    emit('update_view', {
        'filename': current_state['filename'],
        'page': page
    }, broadcast=True)


if __name__ == '__main__':
    # uploads 폴더가 없으면 생성
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # SocketIO 서버 실행
    socketio.run(app, debug=True, host='0.0.0.0', port=80, allow_unsafe_werkzeug=True)
