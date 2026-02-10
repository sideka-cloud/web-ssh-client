from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from config import Config
from database import db
from auth import User, SSHConnection
from ssh_manager import ssh_manager
import eventlet
import os
import logging
import threading
from persistent_ssh import persistent_manager
from datetime import datetime, timedelta
from sqlalchemy import or_
import random

# Setup logging
import warnings
warnings.filterwarnings("ignore")

# Matikan semua log yang tidak penting
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('socketio').setLevel(logging.ERROR)
logging.getLogger('engineio').setLevel(logging.ERROR)
logging.getLogger('paramiko').setLevel(logging.ERROR)
logging.getLogger('eventlet').setLevel(logging.ERROR)

# Setup logging untuk aplikasi kita
logging.basicConfig(
    level=logging.WARNING,  # Hanya tampilkan WARNING dan ERROR
    format='%(levelname)s: %(message)s'
)

# Hanya tampilkan log dari aplikasi utama (level INFO atau lebih tinggi untuk app kita)
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # Hanya log penting

# Optional: Redirect paramiko logs to a file atau disable completely
paramiko_logger = logging.getLogger('paramiko.transport')
paramiko_logger.setLevel(logging.WARNING)

# Disable paramiko debug messages completely
import paramiko
paramiko.common.logging.basicConfig(level=paramiko.common.ERROR)

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please login to access this page.'
login_manager.login_message_category = 'warning'

# Initialize SocketIO for real-time communication
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=False, engineio_logger=False)

# ========== LIVE SESSION TRACKING ==========
active_ssh_sessions = {}  # Format: {session_id: {"user_id": X, "connection_id": Y, "start_time": datetime}}
user_active_sessions = {}  # Format: {user_id: set(session_ids)}
session_lock = threading.Lock()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Timezone offset untuk Indonesia (WIB = UTC+7)
WIB_OFFSET = timedelta(hours=7)

def to_wib_time(utc_dt):
    """Convert UTC to WIB (Indonesia) time"""
    if not utc_dt:
        return None
    return utc_dt + WIB_OFFSET

# Template filters sederhana
@app.template_filter('wib_time')
def wib_time_filter(dt):
    if dt:
        wib_dt = dt + WIB_OFFSET
        return wib_dt.strftime('%H:%M')
    return None

@app.template_filter('wib_date')
def wib_date_filter(dt):
    if dt:
        wib_dt = dt + WIB_OFFSET
        return wib_dt.strftime('%Y-%m-%d')
    return None

# ========== CAPTCHA FUNCTIONS ==========
def generate_captcha():
    """Generate simple math CAPTCHA with + or - operators"""
    operator = random.choice(['+', '-'])
    
    if operator == '+':
        # Addition: result <= 100, both numbers minimum 20
        while True:
            a = random.randint(20, 79)  # Max 80 karena 79+20=99
            b = random.randint(20, 99 - a)  # Pastikan a+b <= 100
            result = a + b
            if result <= 99 and a >= 20 and b >= 20:
                break
        question = f"{a} + {b} = ?"
        answer = str(result)
        
    else:  # operator == '-'
        # Subtraction: result >= 20, both numbers minimum 20
        a = random.randint(40, 99)  # Minimal 40 karena 40-20=20
        max_b = a - 20  # Hasil minimal 20, jadi b maksimal a-20
        b = random.randint(20, max_b)  # Minimal 20, maksimal a-20
        result = a - b
        question = f"{a} - {b} = ?"
        answer = str(result)
    
    return question, answer

@app.route('/get_captcha', methods=['GET'])
def get_captcha():
    """Generate new CAPTCHA and return as JSON"""
    question, answer = generate_captcha()
    session['captcha_answer'] = answer  # Store answer in session
    return jsonify({
        'question': question,
        'answer': answer
    })

# ========== LIVE SESSION HELPER FUNCTIONS ==========
def add_active_session(session_id, user_id, connection_id):
    """Add a new active SSH session"""
    with session_lock:
        active_ssh_sessions[session_id] = {
            "user_id": user_id,
            "connection_id": connection_id,
            "start_time": datetime.utcnow(),
            "last_activity": datetime.utcnow()
        }
        
        if user_id not in user_active_sessions:
            user_active_sessions[user_id] = set()
        user_active_sessions[user_id].add(session_id)
    
    logger.info(f"✅ LIVE SESSION: Session {session_id} added for user {user_id}")
    return True

def update_session_activity(session_id):
    """Update last activity time for a session"""
    with session_lock:
        if session_id in active_ssh_sessions:
            active_ssh_sessions[session_id]["last_activity"] = datetime.utcnow()

def remove_active_session(session_id):
    """Remove an active SSH session"""
    with session_lock:
        if session_id in active_ssh_sessions:
            user_id = active_ssh_sessions[session_id]["user_id"]
            
            # Remove from active_ssh_sessions
            del active_ssh_sessions[session_id]
            
            # Remove from user_active_sessions
            if user_id in user_active_sessions:
                user_active_sessions[user_id].discard(session_id)
                if not user_active_sessions[user_id]:  # Clean up empty sets
                    del user_active_sessions[user_id]
            
            logger.info(f"✅ LIVE SESSION: Session {session_id} removed")
            return user_id
    return None

def get_user_active_session_count(user_id):
    """Get number of active sessions for a user"""
    with session_lock:
        return len(user_active_sessions.get(user_id, set()))

def get_all_active_sessions():
    """Get all active sessions (for debugging)"""
    with session_lock:
        return active_ssh_sessions.copy()

def cleanup_inactive_sessions_background():
    """Background task to cleanup inactive sessions"""
    while True:
        try:
            # Clean sessions inactive for more than 30 minutes
            cutoff_time = datetime.utcnow() - timedelta(minutes=30)
            sessions_to_remove = []
            
            with session_lock:
                for session_id, session_data in active_ssh_sessions.items():
                    if session_data["last_activity"] < cutoff_time:
                        sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                user_id = remove_active_session(session_id)
                if user_id:
                    # Notify user about session cleanup
                    socketio.emit('session_cleanup', 
                                {'session_id': session_id, 'reason': 'inactive'},
                                room=f'user_{user_id}')
            
            if sessions_to_remove:
                logger.info(f"Cleaned up {len(sessions_to_remove)} inactive sessions")
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        
        eventlet.sleep(60 * 5)  # Check every 5 minutes

def broadcast_session_count(user_id):
    """Broadcast session count update to user"""
    active_count = get_user_active_session_count(user_id)
    socketio.emit('session_count_update', 
                {'active_count': active_count}, 
                room=f'user_{user_id}')

# ========== HELPER FUNCTIONS ==========
def safe_decrypt_password(encrypted_password, connection_name):
    """Safely decrypt password with error handling"""
    if not encrypted_password:
        return ''

    try:
        decrypted = ssh_manager.decrypt_password(encrypted_password)
        if not decrypted:
            logger.warning(f"⚠ Empty decryption result for connection: {connection_name}")
            return ''
        return decrypted
    except Exception as e:
        logger.error(f"❌ Decryption failed for {connection_name}: {str(e)}")
        return ''

def check_password_validity(connection):
    """Check if password is valid (can be decrypted)"""
    if not connection.password:
        return True  # No password is valid

    try:
        decrypted = ssh_manager.decrypt_password(connection.password)
        return bool(decrypted)
    except:
        return False

def sort_connections_by_last_used(connections):
    """Sort connections by last_used, handling None values"""
    def get_sort_key(conn):
        if conn.last_used:
            return conn.last_used
        else:
            # Return a datetime far in the past for None values
            return datetime.min

    return sorted(connections, key=get_sort_key, reverse=True)

# ========== SOCKETIO CONNECTION HANDLERS ==========
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    if current_user.is_authenticated:
        join_room(f'user_{current_user.id}')
        logger.info(f"📡 SocketIO: User {current_user.id} connected to room user_{current_user.id}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if current_user.is_authenticated:
        logger.info(f"📡 SocketIO: User {current_user.id} disconnected")

# ========== PERSISTENT SSH HANDLERS ==========
@socketio.on('start_persistent_ssh')
def handle_start_persistent_ssh(data):
    """Start persistent SSH session"""
    try:
        connection_id = data.get('connection_id')
        connection = SSHConnection.query.get(connection_id)

        if not connection or connection.user_id != current_user.id:
            emit('ssh_error', {'message': 'Unauthorized'})
            return

        # Decrypt password
        decrypted_password = safe_decrypt_password(connection.password, connection.name)
        if not decrypted_password and not connection.private_key:
            emit('ssh_error', {'message': 'Password decryption failed. Please edit connection.'})
            return

        # Create persistent session
        result = persistent_manager.create_session(
            hostname=connection.hostname,
            port=connection.port,
            username=connection.username,
            password=decrypted_password,
            private_key=connection.private_key
        )

        if result['success']:
            session_id = result['session_id']

            # ADD TO LIVE SESSION TRACKING
            add_active_session(session_id, current_user.id, connection_id)
            
            # Update last_used for connection
            connection.last_used = datetime.utcnow()
            db.session.commit()

            # Send initial output (banner, motd, etc.)
            if result.get('initial_output'):
                emit('ssh_output', {
                    'session_id': session_id,
                    'data': result['initial_output']
                })

            # Broadcast session count update
            broadcast_session_count(current_user.id)

            emit('ssh_session_started', {
                'session_id': session_id,
                'message': 'Persistent SSH session started'
            })
            
            logger.info(f"✅ SSH Session Started: {session_id} by user {current_user.id}")
        else:
            emit('ssh_error', {'message': result['message']})

    except Exception as e:
        logger.error(f"Persistent SSH start error: {e}")
        emit('ssh_error', {'message': str(e)})

@socketio.on('persistent_ssh_input')
def handle_persistent_ssh_input(data):
    """Handle input for persistent SSH session"""
    try:
        session_id = data.get('session_id')
        input_data = data.get('data')

        if not session_id or not input_data:
            return

        # Update session activity
        update_session_activity(session_id)

        # Send input to persistent session
        result = persistent_manager.send_input(session_id, input_data)

        if not result['success']:
            emit('ssh_error', {'message': result['message']})

    except Exception as e:
        logger.error(f"Persistent SSH input error: {e}")
        emit('ssh_error', {'message': str(e)})

@socketio.on('get_persistent_output')
def handle_get_persistent_output(data):
    """Get output from persistent SSH session"""
    try:
        session_id = data.get('session_id')
        if not session_id:
            return

        # Update session activity
        update_session_activity(session_id)

        output = persistent_manager.get_output(session_id)
        if output:
            emit('ssh_output', {
                'session_id': session_id,
                'data': output
            })

    except Exception as e:
        logger.error(f"Get persistent output error: {e}")

@socketio.on('resize_persistent_terminal')
def handle_resize_persistent_terminal(data):
    """Resize persistent terminal"""
    try:
        session_id = data.get('session_id')
        cols = data.get('cols', 80)
        rows = data.get('rows', 24)

        persistent_manager.resize_terminal(session_id, rows, cols)
    except Exception as e:
        logger.error(f"Resize persistent terminal error: {e}")

@socketio.on('close_persistent_ssh')
def handle_close_persistent_ssh(data):
    """Close persistent SSH session"""
    try:
        session_id = data.get('session_id')
        if session_id:
            persistent_manager.close_session(session_id)
            
            # REMOVE FROM LIVE SESSION TRACKING
            user_id = remove_active_session(session_id)
            
            # Broadcast session count update
            if user_id:
                broadcast_session_count(user_id)
            
            emit('ssh_session_closed', {'session_id': session_id})
            logger.info(f"✅ SSH Session Closed: {session_id}")
    except Exception as e:
        logger.error(f"Close persistent SSH error: {e}")

# Background task to cleanup inactive sessions
def cleanup_inactive_persistent_sessions():
    """Periodically cleanup inactive SSH sessions in persistent manager"""
    while True:
        try:
            cleaned = persistent_manager.cleanup_inactive(timeout_minutes=30)
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} inactive SSH sessions from persistent manager")
        except Exception as e:
            logger.error(f"Persistent manager cleanup error: {e}")

        eventlet.sleep(60 * 5)  # Check every 5 minutes

# ========== ROUTES ==========
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'GET':
        # Generate initial CAPTCHA
        captcha_question, captcha_answer = generate_captcha()
        session['captcha_answer'] = captcha_answer
        return render_template('login.html', captcha_question=captcha_question)

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember')
        user_captcha_answer = request.form.get('captcha_answer', '').strip()
        stored_captcha_answer = session.get('captcha_answer', '')

        # Validate CAPTCHA
        if not user_captcha_answer or user_captcha_answer != stored_captcha_answer:
            # Generate new CAPTCHA for retry
            captcha_question, captcha_answer = generate_captcha()
            session['captcha_answer'] = captcha_answer
            flash('CAPTCHA incorrect. Please try again.', 'danger')
            return render_template('login.html', 
                                 captcha_question=captcha_question,
                                 username=username)

        user = User.query.filter_by(username=username).first()

        if user and user.verify_password(password):
            if user.is_active:
                login_user(user, remember=remember)
                user.update_last_login()
                
                # Clear CAPTCHA from session after successful login
                session.pop('captcha_answer', None)
                
                flash('✅ Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Account is disabled', 'danger')
        else:
            flash('Invalid username or password', 'danger')

        # If login fails, generate new CAPTCHA
        captcha_question, captcha_answer = generate_captcha()
        session['captcha_answer'] = captcha_answer
        return render_template('login.html', 
                             captcha_question=captcha_question,
                             username=username)

    return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's SSH connections
    connections = SSHConnection.query.filter_by(user_id=current_user.id).all()

    # Sort connections by last_used (handling None values)
    sorted_connections = sort_connections_by_last_used(connections)

    # Calculate active connections (LIVE SESSIONS)
    active_count = get_user_active_session_count(current_user.id)

    # Get recent activity (last 24 hours)
    recent_activity = []
    for conn in connections:
        if conn.last_used:
            time_diff = datetime.utcnow() - conn.last_used
            if time_diff.total_seconds() < 86400:  # 24 hours
                recent_activity.append(conn)

    # Sort recent activity by last_used (most recent first)
    recent_activity.sort(key=lambda x: x.last_used, reverse=True)
    # Get only the 3 most recent activities
    recent_activity = recent_activity[:3]

    # Add password validity check for each connection
    for conn in connections:
        conn.password_valid = check_password_validity(conn)

    # Debug logging
    logger.info(f"📊 Dashboard: User {current_user.id} has {active_count} active sessions")

    return render_template('dashboard.html',
                        connections=sorted_connections,
                        active_count=active_count,
                        recent_activity=recent_activity)

@app.route('/api/active_sessions')
@login_required
def api_active_sessions():
    """API endpoint to get active session count"""
    active_count = get_user_active_session_count(current_user.id)
    return jsonify({'active_count': active_count})

@app.route('/debug/sessions')
@login_required
def debug_sessions():
    """Debug endpoint to see active sessions"""
    if not current_user.is_admin:
        return "Access denied", 403
    
    user_active = get_user_active_session_count(current_user.id)
    all_active = get_all_active_sessions()
    
    return jsonify({
        'user_active_count': user_active,
        'all_active_sessions': all_active,
        'user_active_sessions': user_active_sessions.get(current_user.id, [])
    })

@app.route('/connections')
@login_required
def connections():
    # Get search query parameter
    search_query = request.args.get('search', '', type=str).strip()
    
    # Get page number for pagination
    page = request.args.get('page', 1, type=int)
    
    # Base query - filter by current user
    query = SSHConnection.query.filter_by(user_id=current_user.id)
    
    # Apply search filter if search query exists
    if search_query:
        query = query.filter(
            or_(
                SSHConnection.name.ilike(f'%{search_query}%'),
                SSHConnection.hostname.ilike(f'%{search_query}%')
            )
        )

    query = query.order_by(
        SSHConnection.last_used.is_(None).desc(),  
        SSHConnection.created_at.desc()            
    )

    # Paginate results - 6 items per page
    connections_paginated = query.paginate(
        page=page,
        per_page=9,
        error_out=False
    )
    
    # Add password validity check for each connection
    for conn in connections_paginated.items:
        conn.password_valid = check_password_validity(conn)

    return render_template('connections.html', 
                        connections=connections_paginated,
                        search_query=search_query)

@app.route('/add_connection', methods=['GET', 'POST'])
@login_required
def add_connection():
    if request.method == 'POST':
        name = request.form.get('name')
        hostname = request.form.get('hostname')
        port = request.form.get('port', 22)
        username = request.form.get('username')
        password = request.form.get('password')
        private_key = request.form.get('private_key')

        # Validate required fields
        if not all([name, hostname, username]):
            flash('Name, hostname, and username are required', 'danger')
            return redirect(url_for('add_connection'))

        # Encrypt password if provided
        encrypted_password = ssh_manager.encrypt_password(password) if password else ''

        # Create new connection
        connection = SSHConnection(
            name=name,
            hostname=hostname,
            port=int(port),
            username=username,
            password=encrypted_password,
            private_key=private_key if private_key else None,
            user_id=current_user.id
        )

        db.session.add(connection)
        db.session.commit()

        flash('SSH connection added successfully!', 'success')
        return redirect(url_for('connections'))

    return render_template('add_connection.html')

@app.route('/edit_connection/<int:connection_id>', methods=['GET', 'POST'])
@login_required
def edit_connection(connection_id):
    connection = SSHConnection.query.get_or_404(connection_id)

    # Check ownership
    if connection.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('connections'))

    if request.method == 'POST':
        connection.name = request.form.get('name')
        connection.hostname = request.form.get('hostname')
        connection.port = request.form.get('port', 22)
        connection.username = request.form.get('username')

        # Update password only if provided
        new_password = request.form.get('password')
        if new_password:
            connection.password = ssh_manager.encrypt_password(new_password)

        # Update private key only if provided
        new_key = request.form.get('private_key')
        if new_key:
            connection.private_key = new_key

        db.session.commit()
        flash('Connection updated successfully!', 'success')
        return redirect(url_for('connections'))

    return render_template('edit_connection.html', connection=connection)

@app.route('/delete_connection/<int:connection_id>')
@login_required
def delete_connection(connection_id):
    connection = SSHConnection.query.get_or_404(connection_id)

    # Check ownership
    if connection.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('connections'))

    db.session.delete(connection)
    db.session.commit()
    flash('Connection deleted successfully!', 'success')
    return redirect(url_for('connections'))

@app.route('/test_connection', methods=['POST'])
@login_required
def test_connection():
    """Test SSH connection without saving"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'})

        hostname = data.get('hostname', '').strip()
        port = int(data.get('port', 22))
        username = data.get('username', '').strip()
        password = data.get('password', '')
        private_key = data.get('private_key', '')

        if not hostname or not username:
            return jsonify({'success': False, 'message': 'Hostname and username are required'})

        # Test connection using paramiko directly
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            if private_key and private_key.strip():
                # Key-based authentication
                import io
                key_file = io.StringIO(private_key)
                private_key_obj = paramiko.RSAKey.from_private_key(key_file)
                ssh.connect(
                    hostname=hostname,
                    port=port,
                    username=username,
                    pkey=private_key_obj,
                    timeout=10,
                    banner_timeout=10
                )
            else:
                # Password authentication
                ssh.connect(
                    hostname=hostname,
                    port=port,
                    username=username,
                    password=password,
                    timeout=10,
                    banner_timeout=10
                )

            # Try to execute a simple command to verify
            stdin, stdout, stderr = ssh.exec_command('echo "Connection successful"', timeout=5)
            exit_status = stdout.channel.recv_exit_status()

            ssh.close()

            if exit_status == 0:
                return jsonify({'success': True, 'message': 'SSH connection successful'})
            else:
                return jsonify({'success': False, 'message': 'Connection test failed'})

        except paramiko.AuthenticationException:
            return jsonify({'success': False, 'message': 'Authentication failed. Check username/password or SSH key.'})
        except paramiko.SSHException as e:
            return jsonify({'success': False, 'message': f'SSH error: {str(e)}'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Connection error: {str(e)}'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'})

@app.route('/test_connection_direct/<int:connection_id>')
@login_required
def test_connection_direct(connection_id):
    """Test a specific connection directly"""
    connection = SSHConnection.query.get_or_404(connection_id)

    if connection.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))

    # Decrypt password dengan error handling yang lebih baik
    decrypted_password = ''
    if connection.password:
        decrypted_password = safe_decrypt_password(connection.password, connection.name)
        if not decrypted_password and not connection.private_key:
            flash('⚠ Password tidak valid. Silakan edit koneksi ini dan masukkan password kembali.', 'warning')
            return redirect(url_for('edit_connection', connection_id=connection.id))

    try:
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if connection.private_key:
            import io
            key_file = io.StringIO(connection.private_key)
            private_key = paramiko.RSAKey.from_private_key(key_file)
            ssh.connect(
                hostname=connection.hostname,
                port=connection.port,
                username=connection.username,
                pkey=private_key,
                timeout=10
            )
        else:
            if not decrypted_password:
                flash('Password tidak tersedia. Silakan edit koneksi dan masukkan password.', 'danger')
                return redirect(url_for('edit_connection', connection_id=connection.id))

            ssh.connect(
                hostname=connection.hostname,
                port=connection.port,
                username=connection.username,
                password=decrypted_password,
                timeout=10
            )

        # Test with simple command
        stdin, stdout, stderr = ssh.exec_command('echo "Good"')
        output = stdout.read().decode().strip()

        ssh.close()

        flash(f'✅ Connection test successful! {output}', 'success')

    except paramiko.AuthenticationException:
        flash('❌ Authentication failed. Please check username/password or SSH key.', 'danger')
    except Exception as e:
        flash(f'❌ Connection test failed: {str(e)}', 'danger')

    return redirect(url_for('dashboard'))

@app.route('/terminal/<int:connection_id>')
@login_required
def terminal(connection_id):
    """Powerful terminal with persistent SSH session"""
    connection = SSHConnection.query.get_or_404(connection_id)

    if connection.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))

    return render_template('terminal.html', connection=connection)

@app.route('/quick_connect', methods=['POST'])
@login_required
def quick_connect():
    """Quick connect without saving"""
    hostname = request.form.get('hostname', '').strip()
    port = request.form.get('port', 22)
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not hostname or not username:
        flash('Hostname and username are required', 'danger')
        return redirect(url_for('dashboard'))

    # Create a temporary connection for testing
    try:
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        ssh.connect(
            hostname=hostname,
            port=int(port),
            username=username,
            password=password,
            timeout=10
        )

        # Execute a simple command
        stdin, stdout, stderr = ssh.exec_command('whoami && pwd')
        output = stdout.read().decode().strip()

        ssh.close()

        flash(f'✅ Quick connect successful! Output: {output}', 'success')

        # Optionally save this connection
        save_option = request.form.get('save_connection')
        if save_option == 'yes':
            name = f"Quick: {hostname}"
            encrypted_password = ssh_manager.encrypt_password(password) if password else ''

            connection = SSHConnection(
                name=name,
                hostname=hostname,
                port=int(port),
                username=username,
                password=encrypted_password,
                user_id=current_user.id
            )

            db.session.add(connection)
            db.session.commit()
            flash('✅ Connection saved!', 'success')

    except Exception as e:
        flash(f'❌ Quick connect failed: {str(e)}', 'danger')

    return redirect(url_for('dashboard'))

# Add current_time to dashboard context
@app.context_processor
def inject_current_time():
    from datetime import datetime
    return {'current_time': datetime.now()}

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not current_user.verify_password(current_password):
                flash('Current password is incorrect', 'danger')
            elif new_password != confirm_password:
                flash('New passwords do not match', 'danger')
            elif len(new_password) < 6:
                flash('Password must be at least 6 characters', 'danger')
            else:
                current_user.change_password(new_password)
                flash('✅ Password changed successfully!', 'success')

        elif action == 'update_profile':
            new_username = request.form.get('username')
            if new_username and new_username != current_user.username:
                # Check if username is available
                existing_user = User.query.filter_by(username=new_username).first()
                if existing_user:
                    flash('Username already taken', 'danger')
                else:
                    current_user.username = new_username
                    db.session.commit()
                    flash('✅ Profile updated successfully!', 'success')

    return render_template('settings.html')

@app.route('/execute_ssh_command', methods=['POST'])
@login_required
def execute_ssh_command():
    """Execute SSH command via POST request"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})

        connection_id = data.get('connection_id')
        command = data.get('command', '').strip()

        if not connection_id or not command:
            return jsonify({'success': False, 'error': 'Connection ID and command are required'})

        connection = SSHConnection.query.get_or_404(connection_id)

        if connection.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'})

        # Decrypt password dengan error handling yang lebih baik
        decrypted_password = ''
        if connection.password:
            decrypted_password = safe_decrypt_password(connection.password, connection.name)
            if not decrypted_password and not connection.private_key:
                return jsonify({
                    'success': False,
                    'error': '⚠ Password tidak valid. Silakan edit koneksi ini dan masukkan password kembali.'
                })

        # Execute command using paramiko with better output handling
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            if connection.private_key:
                import io
                key_file = io.StringIO(connection.private_key)
                private_key = paramiko.RSAKey.from_private_key(key_file)
                ssh.connect(
                    hostname=connection.hostname,
                    port=connection.port,
                    username=connection.username,
                    pkey=private_key,
                    timeout=10
                )
            else:
                if not decrypted_password:
                    return jsonify({
                        'success': False,
                        'error': 'Password tidak tersedia. Silakan edit koneksi dan masukkan password.'
                    })

                ssh.connect(
                    hostname=connection.hostname,
                    port=connection.port,
                    username=connection.username,
                    password=decrypted_password,
                    timeout=10
                )

            # Get transport and open channel
            transport = ssh.get_transport()
            channel = transport.open_session()

            # Get PTY for better formatting
            channel.get_pty(term='xterm', width=80, height=24)

            # Execute command
            channel.exec_command(command)

            # Read output with timeout
            import select
            import time

            output = ""
            error = ""
            max_wait = 30  # Increased timeout for longer commands

            start_time = time.time()

            while True:
                # Check if channel is ready for reading
                read_ready, _, _ = select.select([channel], [], [], 0.1)

                if channel.recv_ready():
                    output += channel.recv(4096).decode('utf-8', errors='ignore')

                if channel.recv_stderr_ready():
                    error += channel.recv_stderr(4096).decode('utf-8', errors='ignore')

                # Check if channel is closed
                if channel.exit_status_ready():
                    # Get remaining output before exit
                    while channel.recv_ready():
                        output += channel.recv(4096).decode('utf-8', errors='ignore')
                    while channel.recv_stderr_ready():
                        error += channel.recv_stderr(4096).decode('utf-8', errors='ignore')
                    break

                # Timeout check
                if time.time() - start_time > max_wait:
                    break

            # Get exit status
            exit_status = channel.recv_exit_status()

            # Close channel and transport
            channel.close()
            transport.close()

            # Update last used
            connection.update_last_used()

            # Clean up output - ensure proper line endings
            output = output.replace('\r\n', '\n').replace('\r', '\n')
            error = error.replace('\r\n', '\n').replace('\r', '\n')

            # Remove trailing whitespace
            output = output.rstrip()
            error = error.rstrip()

            return jsonify({
                'success': True,
                'output': output,
                'error': error,
                'exit_status': exit_status
            })

        except paramiko.AuthenticationException:
            return jsonify({
                'success': False,
                'error': 'Authentication failed. Please check username/password or SSH key.'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Route Delete all connection
@app.route('/delete_all_connections')
@login_required
def delete_all_connections():
    """Delete all SSH connections for current user"""
    try:
        # Delete all connections for current user
        deleted_count = SSHConnection.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()

        flash(f'✅ Deleted {deleted_count} SSH connection(s)', 'success')
    except Exception as e:
        flash(f'❌ Error deleting connections: {str(e)}', 'danger')

    return redirect(url_for('settings'))


# ========== APPLICATION STARTUP ==========
if __name__ == '__main__':
    # ========== INISIALISASI DATABASE YANG AMAN ==========
    print("🚀 Starting Web SSH Client...")

    with app.app_context():
        try:
            # Cek apakah database sudah ada
            from sqlalchemy import inspect
            inspector = inspect(db.engine)

            if 'users' not in inspector.get_table_names():
                print("📦 Database does not exist yet, create database and table...")
                # Buat semua tabel
                db.create_all()

                # Buat user admin default
                from auth import User
                admin = User(
                    username='admin',
                    password_hash=User.hash_password('admin'),
                    is_admin=True,
                    is_active=True
                )
                db.session.add(admin)
                db.session.commit()
                print("✅ Database created successfully")
                print("✅ Admin user created (username: admin, password: admin)")
            else:
                print("✅ The database is ready to use.")

        except Exception as e:
            print(f"❌ Database initialization error: {e}")
            print("🔄 The database is ready to use.")
            # Force create database
            db.drop_all()
            db.create_all()

            from auth import User
            admin = User(
                username='admin',
                password_hash=User.hash_password('admin'),
                is_admin=True,
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Database successfully recreated")

    # Start background cleanup tasks
    eventlet.spawn(cleanup_inactive_sessions_background)
    eventlet.spawn(cleanup_inactive_persistent_sessions)
    
    print("✅ Live session tracking system started")

    # ========== START SERVER ==========
    try:
        print(f"""
    ╔══════════════════════════════════════════╗
    ║           • Web SSH Client •             ║
    ╠══════════════════════════════════════════╣
    ║  Local: http://localhost:5000            ║
    ║  Network: http://[YOUR-IP]:5000          ║
    ║                                          ║
    ║  Default Credentials                     ║
    ║  • Username: admin                       ║
    ║  • Password: admin                       ║
    ║                                          ║
    ║  Press Ctrl+C to Stop Server             ║
    ╚══════════════════════════════════════════╝
        """)

        # Run with SocketIO
        socketio.run(app,
                    host='0.0.0.0',
                    port=5000,
                    debug=False,
                    allow_unsafe_werkzeug=True)

    except KeyboardInterrupt:
        print("\n🛑 Server dihentikan oleh user")
    except Exception as e:
        print(f"\n❌ Error menjalankan server: {e}")
        
