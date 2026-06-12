# Chat Module

A real-time chat system built with Flask, Socket.IO, and Alpine.js.

## Features

- Real-time messaging with WebSocket support
- Channel-based communication
- Unread message tracking
- Message pinning
- Message search
- Admin-only channel management
- Persistent message history
- Responsive design

## Setup

1. Ensure dependencies are installed:
   ```bash
   pip install flask-socketio eventlet
   ```

2. Database migrations:
   ```bash
   flask db upgrade
   ```

3. Configure WebSocket server:
   ```python
   socketio = SocketIO(app, async_mode='eventlet')
   ```

## API Endpoints

### Channels

- `GET /chat` - Main chat interface
- `POST /chat/channels` - Create new channel (admin only)
- `DELETE /chat/channels/<name>` - Delete channel (admin only)
- `GET /chat/channels/<name>/messages` - Get channel messages

### Messages

- `POST /chat/create` - Create new message
- `DELETE /chat/<id>` - Delete message
- `POST /chat/<id>/pin` - Toggle message pin

### WebSocket Events

- `message_created` - New message notification
- `chat_changed` - Message updated/deleted
- `channel_created` - New channel created
- `channel_deleted` - Channel deleted

## Architecture

The chat system uses:
- Flask for the backend API
- Socket.IO for real-time communication
- Alpine.js for reactive UI
- SQLAlchemy for data models

## Unimplemented Features

Future improvements planned:
- Message replies
- Reactions/likes
- File attachments
- Emoji picker
- @mentions
- Rich text formatting

## Security

- Channel creation/deletion restricted to admins
- Message deletion restricted to admins and message authors
- XSS prevention through proper escaping
- CSRF protection enabled 