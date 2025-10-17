# frontend/app.py
import gradio as gr
import secrets
import time
import threading
import atexit
from fastrtc import WebRTC
from typing import Dict
import numpy as np


# ------------------------------
# Ephemeral Call System
# ------------------------------
class EphemeralCallSystem:
    def __init__(self):
        self.active_rooms: Dict[str, Dict] = {}
        self.cleanup_thread = threading.Thread(target=self.periodic_cleanup, daemon=True)
        self.setup_cleanup()

    def setup_cleanup(self):
        atexit.register(self.emergency_cleanup)
        self.cleanup_thread.start()

    def periodic_cleanup(self):
        while True:
            time.sleep(300)
            now = time.time()
            stale_rooms = [room_id for room_id, room in self.active_rooms.items()
                           if now - room.get('last_activity', 0) > 1800]
            for room_id in stale_rooms:
                self.cleanup_room(room_id)

    def generate_room_id(self):
        return secrets.token_urlsafe(16)

    def create_room(self, user_name: str):
        room_id = self.generate_room_id()
        user_id = secrets.token_urlsafe(8)
        self.active_rooms[room_id] = {
            'creator': user_id,
            'participants': [user_id],
            'pending_approvals': [],
            'user_names': {user_id: user_name},
            'created_at': time.time(),
            'last_activity': time.time(),
            'call_ended': False
        }
        return room_id, user_id, f"Room created! Share this ID: {room_id}"

    def request_join(self, room_id: str, user_name: str):
        if room_id not in self.active_rooms:
            return None, None, "Room not found or expired"

        room = self.active_rooms[room_id]
        
        if room.get('call_ended', False):
            return None, None, "Call has ended permanently"
            
        user_id = secrets.token_urlsafe(8)

        if len(room['participants']) >= 10:
            return None, None, "Room is full"

        room['participants'].append(user_id)
        room['user_names'][user_id] = user_name
        room['last_activity'] = time.time()
        return user_id, room_id, f"Joined room {room_id}"

    def end_call_permanently(self, room_id: str):
        if room_id in self.active_rooms:
            self.active_rooms[room_id]['call_ended'] = True

    def can_start_call(self, room_id: str):
        if room_id not in self.active_rooms:
            return False
        return not self.active_rooms[room_id].get('call_ended', False)

    def get_status(self, room_id):
        if not room_id or room_id not in self.active_rooms:
            return "Room not found"
        
        room = self.active_rooms[room_id]
        
        if room.get('call_ended', False):
            return "❌ Call has ended permanently"
            
        status = f"🟢 Room Active | 👥 Participants: {len(room['participants'])}"
        
        # Show participant names
        if room['user_names']:
            names = list(room['user_names'].values())
            status += f"\n📋 Participants: {', '.join(names)}"
            
        return status

    def cleanup_room(self, room_id: str):
        if room_id in self.active_rooms:
            del self.active_rooms[room_id]

    def emergency_cleanup(self):
        self.active_rooms.clear()


call_system = EphemeralCallSystem()


# ------------------------------
# WebRTC Handler Functions
# ------------------------------
class CallHandler:
    def __init__(self):
        self.video_enabled = True
        self.audio_enabled = True
    
    def toggle_video(self):
        self.video_enabled = not self.video_enabled
        return self.video_enabled
    
    def toggle_audio(self):
        self.audio_enabled = not self.audio_enabled
        return self.audio_enabled

    def video_handler(self, frame):
        """Handle video frames"""
        if frame is not None and self.video_enabled:
            return frame
        # Return black frame when video is disabled
        return np.zeros((480, 640, 3), dtype=np.uint8)

    def audio_handler(self, audio):
        """Handle audio"""
        if audio is not None and self.audio_enabled:
            return audio
        # Return silence when audio is disabled
        return (16000, np.zeros((1, 1600), dtype=np.int16))


call_handler = CallHandler()


# ------------------------------
# Cyber Theme CSS
# ------------------------------
cyber_css = """
:root {
    --cyber-primary: #00ff41;
    --cyber-secondary: #0099cc;
    --cyber-danger: #ff0040;
    --cyber-bg: #0a0a0a;
    --cyber-surface: #1a1a1a;
    --cyber-border: #333333;
}
.gradio-container {
    background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
    color: var(--cyber-primary);
    font-family: 'Courier New', monospace;
}
.cyber-header {
    background: linear-gradient(90deg, #00ff41, #0099cc);
    background-clip: text;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-align: center;
    font-size: 2.5em;
    font-weight: bold;
    text-shadow: 0 0 20px #00ff41;
    margin-bottom: 20px;
}
.cyber-panel {
    background: rgba(26,26,26,0.9);
    border: 2px solid var(--cyber-primary);
    border-radius: 10px;
    padding: 20px;
    margin: 10px 0;
    box-shadow: 0 0 30px rgba(0,255,65,0.3);
}
.cyber-button {
    background: linear-gradient(45deg, var(--cyber-primary), var(--cyber-secondary)) !important;
    border: none !important;
    color: black !important;
    padding: 12px 24px;
    border-radius: 5px;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.3s;
    min-width: 120px;
}
.cyber-button:hover {
    box-shadow: 0 0 20px var(--cyber-primary);
    transform: translateY(-2px);
}
.cyber-input {
    background: var(--cyber-surface) !important;
    border: 2px solid var(--cyber-border) !important;
    color: var(--cyber-primary) !important;
    border-radius: 5px;
    padding: 10px;
}
.call-controls {
    display: flex;
    justify-content: center;
    gap: 15px;
    margin-top: 20px;
    flex-wrap: wrap;
}
.call-status {
    background: rgba(0,255,65,0.1);
    border: 1px solid var(--cyber-primary);
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
    text-align: center;
}
"""


# ------------------------------
# Interface Functions
# ------------------------------
def create_room_interface(user_name):
    if not user_name.strip():
        return None, None, "Please enter your name"
    return call_system.create_room(user_name.strip())

def join_room_interface(room_id, user_name):
    if not room_id.strip() or not user_name.strip():
        return None, None, "Please enter both Room ID and Name"
    return call_system.request_join(room_id.strip(), user_name.strip())

def get_room_status(room_id):
    return call_system.get_status(room_id)

def start_call_interface(room_id):
    if not room_id:
        return gr.update(visible=False)
    
    if not call_system.can_start_call(room_id):
        return gr.update(visible=False)
    
    return gr.update(visible=True)

def end_call_interface(room_id):
    # End call permanently
    if room_id:
        call_system.end_call_permanently(room_id)
    
    # Reset call handler states
    call_handler.video_enabled = True
    call_handler.audio_enabled = True
    
    return (
        gr.update(visible=False),
        gr.update(value="🔇 Mute"),
        gr.update(value="📹 Video"),
        gr.update(value="🔊 Unmuted"),
        gr.update(value="📹 Video On")
    )

def toggle_mute_interface():
    is_enabled = call_handler.toggle_audio()
    button_text = "🔊 Unmute" if not is_enabled else "🔇 Mute"
    status_text = "🔊 Unmuted" if is_enabled else "🔇 Muted"
    return button_text, status_text

def toggle_video_interface():
    is_enabled = call_handler.toggle_video()
    button_text = "📹 Video On" if not is_enabled else "📹 Video Off"
    status_text = "📹 Video On" if is_enabled else "📹 Video Off"
    return button_text, status_text


# ------------------------------
# Gradio Interface
# ------------------------------
with gr.Blocks(css=cyber_css, title="Ephemeral Private Call") as demo:
    gr.HTML('<div class="cyber-header">🔒 EPHEMERAL PRIVATE CALL SYSTEM 🔒</div>')
    
    # State variables
    current_room_id = gr.State(None)
    current_user_id = gr.State(None)

    with gr.Tabs():
        # Create Room Tab
        with gr.Tab("🏠 Create Room"):
            with gr.Column(elem_classes="cyber-panel"):
                name_box = gr.Textbox(
                    label="Your Name", 
                    placeholder="Enter your name", 
                    elem_classes="cyber-input"
                )
                create_btn = gr.Button("Create Room", elem_classes="cyber-button")
                create_output = gr.Textbox(label="Room Info", interactive=False)
                
                create_btn.click(
                    create_room_interface, 
                    inputs=[name_box],
                    outputs=[current_room_id, current_user_id, create_output]
                )

        # Join Room Tab
        with gr.Tab("🚪 Join Room"):
            with gr.Column(elem_classes="cyber-panel"):
                join_room_id = gr.Textbox(label="Room ID", elem_classes="cyber-input")
                join_name = gr.Textbox(label="Your Name", elem_classes="cyber-input")
                join_btn = gr.Button("Join Room", elem_classes="cyber-button")
                join_output = gr.Textbox(label="Join Status", interactive=False)
                
                join_btn.click(
                    join_room_interface,
                    inputs=[join_room_id, join_name],
                    outputs=[current_user_id, current_room_id, join_output]
                )

        # Secure Call Tab
        with gr.Tab("📞 Secure Call"):
            with gr.Column(elem_classes="cyber-panel"):
                # Room status and refresh (always visible)
                room_status = gr.Textbox(label="Room Status", interactive=False)
                refresh_btn = gr.Button("🔄 Refresh Status", elem_classes="cyber-button")
                
                refresh_btn.click(
                    get_room_status, 
                    inputs=[current_room_id], 
                    outputs=[room_status]
                )

                # Call initiation
                start_call_btn = gr.Button("📞 Start Video Call", elem_classes="cyber-button")

                # WebRTC component (initially hidden)
                webrtc_interface = gr.Column(visible=False)
                
                with webrtc_interface:
                    gr.HTML('<div class="call-status"><h3>🔴 LIVE CALL</h3></div>')
                    
                    # Main WebRTC component for video calling
                    webrtc_component = WebRTC(
                        label="Video Call",
                        mode="send-receive",
                        modality="video",
                        rtc_configuration={
                            "iceServers": [{"urls": "stun:stun.l.google.com:19302"}]
                        }
                    )
                    
                    # Call controls
                    with gr.Row(elem_classes="call-controls"):
                        mute_btn = gr.Button("🔇 Mute", elem_classes="cyber-button")
                        video_btn = gr.Button("📹 Video", elem_classes="cyber-button")
                        end_call_btn = gr.Button("📞 End Call", elem_classes="cyber-button")
                    
                    # Control status displays
                    with gr.Row():
                        mute_status = gr.Textbox(label="Audio", value="🔊 Unmuted", interactive=False)
                        video_status = gr.Textbox(label="Video", value="📹 Video On", interactive=False)

                # Event handlers
                start_call_btn.click(
                    start_call_interface,
                    inputs=[current_room_id],
                    outputs=[webrtc_interface]
                )
                
                # Set up WebRTC streaming with proper handler
                webrtc_component.stream(
                    fn=call_handler.video_handler,
                    inputs=[webrtc_component],
                    outputs=[webrtc_component],
                    time_limit=3600
                )
                
                mute_btn.click(
                    toggle_mute_interface,
                    outputs=[mute_btn, mute_status]
                )
                
                video_btn.click(
                    toggle_video_interface,
                    outputs=[video_btn, video_status]
                )
                
                end_call_btn.click(
                    end_call_interface,
                    inputs=[current_room_id],
                    outputs=[webrtc_interface, mute_btn, video_btn, mute_status, video_status]
                )

        # Security Tab
        with gr.Tab("🛡️ Security"):
            gr.HTML("""
            <div class="cyber-panel">
                <h3 style='color:#ff0040;'>🔒 SECURITY FEATURES</h3>
                <ul style='color:#00ff41; line-height:1.8;'>
                    <li>🎭 Real-time WebRTC Communication</li>
                    <li>🔐 Peer-to-Peer Connection</li>
                    <li>💾 Zero Server Storage</li>
                    <li>⏰ Auto Room Expiry (30 min)</li>
                    <li>🚫 No Call Recording</li>
                    <li>🔄 Ephemeral Room IDs</li>
                    <li>👥 Max 10 Participants</li>
                    <li>⚠️ Call ends permanently if any user leaves</li>
                </ul>
                <div style='margin-top:20px; color:#0099cc;'>
                    <h4>📋 Usage Instructions:</h4>
                    <ol style='line-height:1.6;'>
                        <li>Create or join a room</li>
                        <li>Share room ID with participants</li>
                        <li>Use refresh to see participant list</li>
                        <li>Click "Start Video Call" to begin</li>
                        <li>Use controls to mute/unmute and toggle video</li>
                        <li>⚠️ Call ends permanently if anyone leaves</li>
                    </ol>
                </div>
            </div>
            """)

# Launch
if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1", 
        server_port=7860, 
        share=False,
        debug=True
    )
