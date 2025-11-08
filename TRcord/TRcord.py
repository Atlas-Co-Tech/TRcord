from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, send, emit
import threading, webbrowser, time
from pyngrok import ngrok

app = Flask(__name__)
app.config['SECRET_KEY'] = 'turkcord_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# --- HTML (chat + voice) ---
html = """<!DOCTYPE html>
<html>
<head>
  <title>TurkCord 💬 + Voice</title>
  <style>
    body { font-family: Arial; background:#121212; color:#eee; text-align:center; }
    ul { list-style:none; padding:0; max-width:400px; margin:auto; text-align:left; }
    li { background:#1f1f1f; margin:5px; padding:8px; border-radius:10px; }
    input { padding:8px; width:250px; border-radius:5px; border:none; outline:none; }
    button { padding:8px 12px; background:#7289da; color:white; border:none; border-radius:5px; cursor:pointer; margin:4px; }
    #typing { color:#aaa; font-size:13px; height:20px; margin-top:5px; }
  </style>
  <script src="https://cdn.socket.io/4.0.0/socket.io.min.js"></script>
</head>
<body>
  <h1>💬 TurkCord</h1>
  <ul id="messages"></ul>
  <input id="msg" autocomplete="off" placeholder="Mesaj yaz..." />
  <button onclick="sendMessage()">Gönder</button>
  <div id="typing"></div>
  <hr>
  <button id="voiceBtn" onclick="toggleVoice()">🎤 Voice Chat Başlat</button>

  <script>
    const socket = io();
    const messages = document.getElementById("messages");
    const input = document.getElementById("msg");
    const typingBox = document.getElementById("typing");
    const voiceBtn = document.getElementById("voiceBtn");
    let typing=false, typingTimeout;
    let localStream=null;
    let peers = {};
    let voiceActive=false;
    const config = { iceServers: [{ urls: "stun:stun.l.google.com:19302" }] };

    socket.on("message", msg => {
      const li = document.createElement("li");
      li.textContent = msg;
      messages.appendChild(li);
      window.scrollTo(0, document.body.scrollHeight);
    });

    function sendMessage() {
      const msg = input.value.trim();
      if (msg !== "") {
        socket.send(msg);
        input.value = "";
        stopTyping();
      }
    }

    input.addEventListener("input", ()=>{
      if(!typing){ typing=true; socket.emit("typing"); }
      clearTimeout(typingTimeout);
      typingTimeout = setTimeout(stopTyping, 1000);
    });

    function stopTyping(){
      if(typing){ typing=false; socket.emit("stop_typing"); }
    }

    socket.on("show_typing", ()=> typingBox.textContent = "🟡 Biri yazıyor...");
    socket.on("hide_typing", ()=> typingBox.textContent = "");

    async function toggleVoice(){
      if(!voiceActive){
        await startVoice();
        voiceBtn.textContent = "🔴 Durdur";
        voiceActive=true;
      } else {
        stopVoice();
        voiceBtn.textContent = "🎤 Voice Chat Başlat";
        voiceActive=false;
      }
    }

    async function startVoice(){
      localStream = await navigator.mediaDevices.getUserMedia({ audio:true });
      const audioEl = document.createElement("audio");
      audioEl.srcObject = localStream;
      audioEl.autoplay=true;
      audioEl.muted=true;
      document.body.appendChild(audioEl);
      socket.emit("join_room", "global");
    }

    function stopVoice(){
      if(localStream){
        localStream.getTracks().forEach(track => track.stop());
        localStream = null;
      }
      for(const id in peers){
        peers[id].close();
      }
      peers = {};
    }

    socket.on("new_peer", async data=>{
      const peerId=data.id;
      if(peers[peerId] || !localStream) return;

      const pc = new RTCPeerConnection(config);
      peers[peerId]=pc;
      localStream.getTracks().forEach(track => pc.addTrack(track, localStream));

      pc.ontrack = e=>{
        const audio=document.createElement("audio");
        audio.srcObject=e.streams[0];
        audio.autoplay=true;
        document.body.appendChild(audio);
      };

      pc.onicecandidate = e=>{
        if(e.candidate) socket.emit("ice_candidate", {to:peerId, candidate:e.candidate});
      };

      const offer=await pc.createOffer();
      await pc.setLocalDescription(offer);
      socket.emit("offer", {to:peerId, offer});
    });

    socket.on("offer", async data=>{
      const peerId=data.from;
      const pc=new RTCPeerConnection(config);
      peers[peerId]=pc;
      localStream.getTracks().forEach(track => pc.addTrack(track, localStream));
      pc.ontrack=e=>{
        const audio=document.createElement("audio");
        audio.srcObject=e.streams[0];
        audio.autoplay=true;
        document.body.appendChild(audio);
      };
      pc.onicecandidate=e=>{
        if(e.candidate) socket.emit("ice_candidate", {to:peerId, candidate:e.candidate});
      };
      await pc.setRemoteDescription(data.offer);
      const answer=await pc.createAnswer();
      await pc.setLocalDescription(answer);
      socket.emit("answer", {to:peerId, answer});
    });

    socket.on("answer", async data=>{
      const peerId=data.from;
      await peers[peerId].setRemoteDescription(data.answer);
    });

    socket.on("ice_candidate", async data=>{
      const peerId=data.from;
      if(peers[peerId]) await peers[peerId].addIceCandidate(data.candidate);
    });
  </script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(html)

@socketio.on('message')
def handle_message(msg):
    print(f"[TurkCord] Yeni mesaj: {msg}")
    send(msg, broadcast=True)

@socketio.on("typing")
def handle_typing():
    emit("show_typing", broadcast=True, include_self=False)

@socketio.on("stop_typing")
def handle_stop_typing():
    emit("hide_typing", broadcast=True, include_self=False)

@socketio.on("join_room")
def handle_join(room):
    emit("new_peer", {"id": request.sid}, broadcast=True, include_self=False)

@socketio.on("offer")
def handle_offer(data):
    emit("offer", {"from": request.sid, "offer": data["offer"]}, room=data["to"])

@socketio.on("answer")
def handle_answer(data):
    emit("answer", {"from": request.sid, "answer": data["answer"]}, room=data["to"])

@socketio.on("ice_candidate")
def handle_ice(data):
    emit("ice_candidate", {"from": request.sid, "candidate": data["candidate"]}, room=data["to"])

def start_server():
    socketio.run(app, host="0.0.0.0", port=5000)

if __name__ == "__main__":
    # --- ngrok bağlantısını başlat ---
    print("🔌 Ngrok başlatılıyor...")
    public_url = ngrok.connect(5000)
    print(f"🌍 Ngrok aktif: {public_url.public_url}")
    threading.Thread(target=start_server, daemon=True).start()

    # Tarayıcıda aç
    time.sleep(2)
    webbrowser.open(public_url.public_url)
    print("✅ TurkCord hazır! Tarayıcıda açıldı.")
    input("Sunucuyu kapatmak için ENTER'a bas...")

