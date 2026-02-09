"""
Terminal WebSocket Handler - Simplified Version
"""

import paramiko
import select
import threading
import time
import json
import logging
from flask_socketio import emit

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SSHTerminalManager:
    """Simplified SSH terminal manager"""
    
    def __init__(self):
        self.sessions = {}
    
    def create_session(self, hostname, port, username, password, private_key=None):
        """Create SSH session"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            if private_key:
                import io
                key_file = io.StringIO(private_key)
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
                ssh.connect(
                    hostname=hostname,
                    port=port,
                    username=username,
                    password=password,
                    timeout=10,
                    banner_timeout=10
                )
            
            # Get transport and open session
            transport = ssh.get_transport()
            channel = transport.open_session()
            
            # Get PTY
            channel.get_pty(term='xterm-256color', width=80, height=24)
            
            # Invoke shell
            channel.invoke_shell()
            
            # Set non-blocking
            channel.setblocking(0)
            
            session_id = f"{hostname}:{port}:{username}:{int(time.time())}"
            self.sessions[session_id] = {
                'ssh': ssh,
                'channel': channel,
                'transport': transport,
                'hostname': hostname,
                'username': username
            }
            
            logger.info(f"SSH session created: {session_id}")
            return {'success': True, 'session_id': session_id}
            
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            return {'success': False, 'message': str(e)}
    
    def read_output(self, session_id):
        """Read from SSH channel"""
        if session_id not in self.sessions:
            return None
        
        channel = self.sessions[session_id]['channel']
        output = ""
        
        try:
            # Check if data is available
            while True:
                if channel.recv_ready():
                    data = channel.recv(1024)
                    if data:
                        output += data.decode('utf-8', errors='ignore')
                    else:
                        break
                else:
                    break
        except Exception as e:
            logger.error(f"Error reading from channel: {e}")
        
        return output if output else None
    
    def write_input(self, session_id, data):
        """Write to SSH channel"""
        if session_id not in self.sessions:
            return False
        
        channel = self.sessions[session_id]['channel']
        
        try:
            # For Enter key, send \r (carriage return)
            if data == '\r' or data == '\n':
                channel.send('\r')
            elif data == '\x03':  # Ctrl+C
                channel.send('\x03')
            elif data == '\x04':  # Ctrl+D
                channel.send('\x04')
            else:
                channel.send(data)
            return True
        except Exception as e:
            logger.error(f"Error writing to channel: {e}")
            return False
    
    def resize(self, session_id, rows, cols):
        """Resize terminal"""
        if session_id not in self.sessions:
            return False
        
        channel = self.sessions[session_id]['channel']
        
        try:
            channel.resize_pty(width=cols, height=rows)
            return True
        except:
            return False
    
    def close(self, session_id):
        """Close SSH session"""
        if session_id in self.sessions:
            try:
                self.sessions[session_id]['channel'].close()
                self.sessions[session_id]['ssh'].close()
            except:
                pass
            finally:
                del self.sessions[session_id]
                logger.info(f"SSH session closed: {session_id}")
        
        return True

# Global instance
terminal_manager = SSHTerminalManager()
