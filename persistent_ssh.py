import paramiko
import select
import threading
import queue
import time
import logging
from io import StringIO

logger = logging.getLogger(__name__)

class PersistentSSHManager:
    """Manage persistent SSH shell sessions"""
    
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()
    
    def create_session(self, hostname, port, username, password, private_key=None):
        """Create a persistent SSH shell session"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if private_key:
                # Key-based authentication
                key_file = StringIO(private_key)
                pkey = paramiko.RSAKey.from_private_key(key_file)
                ssh.connect(
                    hostname=hostname,
                    port=port,
                    username=username,
                    pkey=pkey,
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
            
            # Create interactive shell with PTY
            transport = ssh.get_transport()
            channel = transport.open_session()
            
            # Request PTY for interactive programs
            channel.get_pty(
                term='xterm-256color',
                width=80,
                height=24,
                width_pixels=0,
                height_pixels=0
            )
            
            # Invoke shell
            channel.invoke_shell()
            
            # Set non-blocking
            channel.setblocking(0)
            
            # Create output queue
            output_queue = queue.Queue()
            
            session_id = f"{hostname}:{port}:{username}:{int(time.time())}"
            
            with self.lock:
                self.sessions[session_id] = {
                    'ssh': ssh,
                    'channel': channel,
                    'transport': transport,
                    'output_queue': output_queue,
                    'last_activity': time.time(),
                    'is_alive': True
                }
            
            # Start background thread to read output
            thread = threading.Thread(
                target=self._read_output_thread,
                args=(session_id,),
                daemon=True
            )
            thread.start()
            
            logger.info(f"Created persistent SSH session: {session_id}")
            
            # Wait for initial output (banner, motd, etc.)
            time.sleep(0.5)
            initial_output = self._get_output(session_id)
            
            return {
                'success': True,
                'session_id': session_id,
                'initial_output': initial_output
            }
            
        except paramiko.AuthenticationException as e:
            return {'success': False, 'message': f'Authentication failed: {str(e)}'}
        except Exception as e:
            return {'success': False, 'message': f'Connection failed: {str(e)}'}
    
    def _read_output_thread(self, session_id):
        """Background thread to read output from SSH channel"""
        while True:
            with self.lock:
                if session_id not in self.sessions:
                    break
                
                session = self.sessions.get(session_id)
                if not session or not session['is_alive']:
                    break
                
                channel = session['channel']
                output_queue = session['output_queue']
            
            try:
                # Check if data is available
                ready = select.select([channel], [], [], 0.1)[0]
                if ready:
                    if channel.recv_ready():
                        data = channel.recv(4096)
                        if data:
                            output_queue.put(data.decode('utf-8', errors='ignore'))
                            with self.lock:
                                if session_id in self.sessions:
                                    self.sessions[session_id]['last_activity'] = time.time()
                    
                    # Check if channel is closed
                    if channel.exit_status_ready():
                        logger.info(f"SSH channel closed for session: {session_id}")
                        with self.lock:
                            if session_id in self.sessions:
                                self.sessions[session_id]['is_alive'] = False
                        break
                
                # Small sleep to prevent CPU hogging
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error reading from SSH channel {session_id}: {e}")
                with self.lock:
                    if session_id in self.sessions:
                        self.sessions[session_id]['is_alive'] = False
                break
    
    def send_input(self, session_id, data):
        """Send input to SSH session"""
        with self.lock:
            if session_id not in self.sessions:
                return {'success': False, 'message': 'Session not found'}
            
            session = self.sessions[session_id]
            if not session['is_alive']:
                return {'success': False, 'message': 'Session is closed'}
            
            channel = session['channel']
        
        try:
            # Handle special keys
            if data == '\r' or data == '\n':
                channel.send('\r')
            elif data == '\x03':  # Ctrl+C
                channel.send('\x03')
            elif data == '\x04':  # Ctrl+D
                channel.send('\x04')
            elif data == '\x1b[A':  # Up arrow
                channel.send('\x1b[A')
            elif data == '\x1b[B':  # Down arrow
                channel.send('\x1b[B')
            elif data == '\x1b[C':  # Right arrow
                channel.send('\x1b[C')
            elif data == '\x1b[D':  # Left arrow
                channel.send('\x1b[D')
            elif data == '\x7f':  # Backspace
                channel.send('\x7f')
            elif data == '\x1b':  # Escape
                channel.send('\x1b')
            else:
                channel.send(data)
            
            session['last_activity'] = time.time()
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error sending input to session {session_id}: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_output(self, session_id):
        """Get accumulated output from session"""
        with self.lock:
            if session_id not in self.sessions:
                return None
            
            session = self.sessions[session_id]
            output_queue = session['output_queue']
        
        # Get all available output
        output = []
        while True:
            try:
                output.append(output_queue.get_nowait())
            except queue.Empty:
                break
        
        return ''.join(output) if output else None
    
    def resize_terminal(self, session_id, rows, cols):
        """Resize terminal window"""
        with self.lock:
            if session_id not in self.sessions:
                return False
            
            channel = self.sessions[session_id]['channel']
        
        try:
            channel.resize_pty(width=cols, height=rows)
            return True
        except:
            return False
    
    def close_session(self, session_id):
        """Close SSH session"""
        with self.lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session['is_alive'] = False
                
                try:
                    # Send exit command and close
                    session['channel'].send('exit\n')
                    time.sleep(0.1)
                    session['channel'].close()
                    session['ssh'].close()
                except:
                    pass
                
                del self.sessions[session_id]
                logger.info(f"Closed SSH session: {session_id}")
                return True
        
        return False
    
    def cleanup_inactive(self, timeout_minutes=30):
        """Clean up inactive sessions"""
        current_time = time.time()
        to_remove = []
        
        with self.lock:
            for session_id, session in self.sessions.items():
                inactive_time = current_time - session['last_activity']
                if inactive_time > (timeout_minutes * 60):
                    to_remove.append(session_id)
        
        for session_id in to_remove:
            self.close_session(session_id)
        
        return len(to_remove)
    
    def _get_output(self, session_id):
        """Helper method to get output (non-blocking)"""
        with self.lock:
            if session_id not in self.sessions:
                return ''
            
            session = self.sessions[session_id]
            output_queue = session['output_queue']
        
        output = []
        while True:
            try:
                output.append(output_queue.get_nowait())
            except queue.Empty:
                break
        
        return ''.join(output)

# Global instance
persistent_manager = PersistentSSHManager()
