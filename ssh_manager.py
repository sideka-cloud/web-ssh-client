import paramiko
import threading
import time
import select
from io import StringIO
from cryptography.fernet import Fernet
import os
import base64

class SSHManager:
    """Manage SSH connections and operations"""
    
    def __init__(self):
        self.connections = {}
        
        # Gunakan FIXED encryption key yang sama setiap kali
        # JANGAN generate key baru setiap kali aplikasi dijalankan!
        self.key = self.get_or_create_encryption_key()
        self.cipher = Fernet(self.key)
    
    def get_or_create_encryption_key(self):
        """Get existing encryption key or create one and save it"""
        key_file = 'encryption_key.key'
        
        # Jika file key sudah ada, baca dari file
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                key = f.read()
            print(f"✓ Loaded encryption key from {key_file}")
            return key
        
        # Jika tidak ada, generate key baru dan simpan ke file
        print(f"⚠ No encryption key found. Creating new one at {key_file}")
        key = Fernet.generate_key()
        
        with open(key_file, 'wb') as f:
            f.write(key)
        
        # Set permissions agar hanya owner yang bisa baca
        try:
            os.chmod(key_file, 0o600)
        except:
            pass
        
        print("✓ New encryption key created and saved")
        return key
    
    def encrypt_password(self, password):
        """Encrypt password for storage"""
        if not password:
            return ''
        try:
            return self.cipher.encrypt(password.encode()).decode()
        except Exception as e:
            print(f"Error encrypting password: {e}")
            return ''
    
    def decrypt_password(self, encrypted_password):
        """Decrypt password for use"""
        if not encrypted_password:
            return ''
        
        try:
            return self.cipher.decrypt(encrypted_password.encode()).decode()
        except Exception as e:
            print(f"⚠ WARNING: Failed to decrypt password. It may have been encrypted with a different key.")
            print(f"Error: {e}")
            
            # Fallback: return empty string
            return ''
    
    def connect(self, hostname, port, username, password, private_key=None):
        """Establish SSH connection"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            if private_key:
                # Key-based authentication
                key_file = StringIO(private_key)
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
            
            # Untuk testing, buka session bukan shell
            transport = ssh.get_transport()
            channel = transport.open_session()
            channel.get_pty(term='xterm')
            channel.invoke_shell()
            channel.setblocking(0)
            
            connection_id = f"{hostname}_{port}_{username}_{int(time.time())}"
            self.connections[connection_id] = {
                'ssh': ssh,
                'channel': channel,
                'hostname': hostname,
                'username': username
            }
            
            # Tunggu sebentar untuk initial output
            import eventlet
            eventlet.sleep(0.5)
            
            return {'success': True, 'connection_id': connection_id}
            
        except paramiko.AuthenticationException:
            return {'success': False, 'message': 'Authentication failed'}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def execute_command(self, connection_id, command):
        """Execute command on SSH connection"""
        if connection_id not in self.connections:
            return {'success': False, 'message': 'Connection not found'}
        
        try:
            ssh = self.connections[connection_id]['ssh']
            stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)
            
            # Baca output dengan timeout
            import select
            import time
            
            output = ''
            error = ''
            max_wait = 10
            
            start_time = time.time()
            while True:
                if stdout.channel.recv_ready():
                    output += stdout.channel.recv(4096).decode('utf-8', errors='ignore')
                
                if stderr.channel.recv_stderr_ready():
                    error += stderr.channel.recv_stderr(4096).decode('utf-8', errors='ignore')
                
                if stdout.channel.exit_status_ready():
                    break
                
                if time.time() - start_time > max_wait:
                    break
                
                time.sleep(0.1)
            
            return {
                'success': True,
                'output': output,
                'error': error
            }
            
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def read_output(self, connection_id):
        """Read output from shell channel"""
        if connection_id not in self.connections:
            return None
        
        channel = self.connections[connection_id]['channel']
        
        output = ''
        try:
            if channel.recv_ready():
                while True:
                    try:
                        ready = select.select([channel], [], [], 0.1)[0]
                        if ready:
                            data = channel.recv(4096)
                            if data:
                                output += data.decode('utf-8', errors='ignore')
                            else:
                                break
                        else:
                            break
                    except:
                        break
        except:
            pass
        
        return output if output else None
    
    def send_input(self, connection_id, data):
        """Send input to shell channel"""
        if connection_id not in self.connections:
            return False
        
        try:
            channel = self.connections[connection_id]['channel']
            channel.send(data)
            return True
        except:
            return False
    
    def resize_terminal(self, connection_id, rows, cols):
        """Resize terminal window"""
        if connection_id not in self.connections:
            return False
        
        try:
            channel = self.connections[connection_id]['channel']
            channel.resize_pty(width=cols, height=rows)
            return True
        except:
            return False
    
    def disconnect(self, connection_id):
        """Close SSH connection"""
        if connection_id in self.connections:
            try:
                self.connections[connection_id]['channel'].close()
                self.connections[connection_id]['ssh'].close()
            except:
                pass
            finally:
                del self.connections[connection_id]
        
        return True

# Global SSH manager instance
ssh_manager = SSHManager()
