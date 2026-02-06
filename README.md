# Web SSH Client

A web-based SSH client that runs locally on your machine.

## Features

- 🔐 User authentication with password change capability
- 🖥️ Add and manage multiple SSH connections
- 🌐 Web-based terminal interface
- 📱 Responsive design
- 🔄 Real-time terminal using WebSockets
- 🔒 Encrypted password storage
- 📊 Connection history and management

## Requirements

- Only Python 3.8 to 3.11
- Modern web browser

## How To RUN

- Create virtual environment
  <code>
python3 -m venv venv
for Linux: source venv/bin/activate
for Windows: venv\Scripts\activate
  </code>
- Install Dependencies
  <code>
pip install -r requirements.txt
  </code>
- Run application
  <code>
  for Linux: python3 app.py
  for Windows: py app.py
  </code>
- Access application with port: 5000
- Default credentials: username: </code>admin</code> password: </code>admin</code>
  <code>
✓ Loaded encryption key from encryption_key.key
🚀 Starting Web SSH Client...
✅ The database is ready to use.
✅ Live session tracking system started
    ╔══════════════════════════════════════════╗
    ║           🛟 Web SSH Client 🛟          ║
    ╠══════════════════════════════════════════╣
    ║  🚧 Local: http://localhost:5000         ║
    ║  🚧 Network: http://[YOUR-IP]:5000       ║
    ║                                          ║
    ║  🔐 Default Credentials 🔐              ║
    ║  ✅ Username: admin     ☀️              ║
    ║  ✅ Password: admin     ☀️              ║
    ║                                          ║
    ║  Live Session Tracking: ✅ ENABLED       ║
    ║  Press Ctrl+C ❌ to Stop Server          ║
    ╚══════════════════════════════════════════╝
  </code>
- To reset configuration and data
  <code>
  for Linux: bash clean_start.sh
  for Windows: .\clean_start.bat
  </code>
- Thank you
