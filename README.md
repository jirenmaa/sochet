![preview](assets/example.gif)

## 🌲 Server Execution Tree (Call Hierarchy)

#### Main Execution Sequence:
```javascript
start_connection()  → accept_connection()
                    → accept_and_handle_connection()
                    → handle_client()
```

```javascript
┌─> main.py (Server)
│   ├─> makefile()  # Ensures DB files exist
│   ├─> Server()
│   │   └─> __init__()
│   ├─> signal_handler()  # Graceful shutdown on Ctrl+C
│   └─> server.start_connection()
│       ├─> socket.bind/listen/settimeout
│       └─> while is_running:
│           └─> accept_and_handle_connection()
│               ├─> verify_user()
│               │   └─> parse_credentials()
│               │   └─> verify_password()
│               ├─> client_manager.register()
│               │   └─> ThreadPoolExecutor.submit(handler)
│               └─> broadcaster.send_msg_to() + broadcast_active_users()
│
│               Thread: handle_client()
│               └─> while running:
│                   └─> handle_message()
│                       ├─> client.recv()
│                       ├─> parse_response()
│                       ├─> check_mute()
│                       ├─> check_rate_limit()
│                       ├─> handle_admin_command() if /command
│                       │   ├─> admin_action_kick/ban/unban/mute/help()
│                       └─> broadcast_message()
│
├─> client/gui.py
│   └─> ChatGUI(root)
│       ├─> build_login_ui()
│       └─> build_chat_ui()
│       └─> attempt_login()
│           └─> Client.connect_to_server()
│               ├─> socket.connect + send credentials
│               ├─> recv auth response
│               └─> thread: read_message()
│                   └─> client.recv()
│                       └─> parse_response()
│                       └─> _dispatch_server_message()
│                           └─> handle_flag / shutdown / update GUI
│
├─> Shared modules
│   ├─> shared.flags (constants for socket signaling)
│   ├─> shared.protocol
│   │   ├─> build_response()
│   │   ├─> parse_response()
│   │   └─> payload_wrapper()
│   └─> utils.helpers
│       ├─> hash/verify_password()
│       ├─> load_json() / save_json()
│       └─> is_authorized() / reject_connection()
│
└─> Admin commands
    └─> Commands.handle_admin_command()
        ├─> /kick      → admin_action_kick()
        ├─> /ban       → admin_action_ban()
        ├─> /unban     → admin_action_unban()
        ├─> /mute      → admin_action_mute()
        └─> /help      → admin_action_help()
```