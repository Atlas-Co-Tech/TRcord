from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, send, emit
import threading, webbrowser, time
from pyngrok import ngrok

app = Flask(__name__)
app.config['SECRET_KEY'] = 'turkcord_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Kullanıcılar ve mesajlar ---
users = {}  # sid -> nickname
channels = {
    "TRcord Official": [],
    "Agalar": [],
    "Eriyen Tekerlek": []
}
dms = {}  # (sid1,sid2) -> list of messages

html = """<!DOCTYPE html>
<html>
<head>
<title>TurkCord 💬 + Voice</title>
<style>
body { font-family: Arial; background:#121212; color:#eee; margin:0; display:flex; flex-direction:column; height:100vh; }

.banner {
  background:#1e90ff;
  color:white;
  text-align:center;
  font-weight:bold;
  padding:10px;
  cursor:pointer;
  transition:0.3s;
}
.banner:hover { background:#3aa0ff; }

.main { display:flex; flex:1; }

.sidebar { width:200px; background:#2f3136; padding:10px; }
#users, #channels { list-style:none; padding:0; margin:0; }
#users li, #channels li { padding:5px; margin:3px 0; border-radius:5px; cursor:pointer; background:#3a3c43; }
#users li.active, #channels li.active { background:#7289da; }

.chat-panel { flex:1; display:flex; flex-direction:column; padding:10px; }
#messages { flex:1; list-style:none; padding:0; overflow-y:auto; }
#messages li { margin:5px; padding:8px; border-radius:10px; background:#3a3c43; }
input { padding:8px; border-radius:5px; border:none; width:80%; margin-top:5px; }
button { padding:8px 12px; border-radius:5px; border:none; background:#7289da; color:white; cursor:pointer; margin-top:5px; }
#typing { font-size:12px; color:#aaa; height:18px; margin-top:2px; }
</style>
<script src="https://cdn.socket.io/4.0.0/socket.io.min.js"></script>
</head>
<body>

<div class="banner" onclick="window.open('https://efeoyunkeyfi19.netlify.app/', '_blank')">
🎮 Efe'nin Oyun Keyfi — Eğlenceyi Maksimuma Çıkar! 🔵
</div>

<div class="main">
  <div class="sidebar">
    <h3>Kullanıcılar</h3>
    <ul id="users"></ul>
    <h3>Kanallar</h3>
    <ul id="channels"></ul>
  </div>

  <div class="chat-panel">
    <ul id="messages"></ul>
    <div id="typing"></div>
    <input id="msg" placeholder="Mesaj yaz..." autocomplete="off"/>
    <button onclick="sendMessage()">Gönder</button>
    <hr>
    <button id="voiceBtn" onclick="toggleVoice()">🎤 Voice Chat Başlat</button>
  </div>
</div>

<script>
const socket = io();
let nickname = prompt("Nickname gir:"); 
socket.emit("join", nickname);

let activeChannel = "TRcord Official";
let activeDM = null;
const messages = document.getElementById("messages");
const usersList = document.getElementById("users");
const channelsList = document.getElementById("channels");
const input = document.getElementById("msg");
const typingBox = document.getElementById("typing");
const voiceBtn = document.getElementById("voiceBtn");

let typing=false, typingTimeout;
let localStream=null, peers={}, voiceActive=false;
const config = { iceServers:[{urls:"stun:stun.l.google.com:19302"}] };

// --- Channel list ---
function updateChannels(){
    channelsList.innerHTML="";
    ["TRcord Official","Agalar","Eriyen Tekerlek"].forEach(ch=>{
        const li=document.createElement("li");
        li.textContent=ch;
        if(ch===activeChannel) li.classList.add("active");
        li.onclick=()=>{ activeChannel=ch; activeDM=null; updateChannels(); loadMessages(); };
        channelsList.appendChild(li);
    });
}

// --- Users list for DM ---
socket.on("user_list", ulist=>{
    usersList.innerHTML="";
    ulist.forEach(u=>{
        if(u===nickname) return;
        const li=document.createElement("li");
        li.textContent=u;
        li.onclick=()=>{ activeDM=u; activeChannel=null; loadMessages(); };
        usersList.appendChild(li);
    });
});

// --- Messages ---
function loadMessages(){
    messages.innerHTML="";
    if(activeChannel){
        socket.emit("get_messages", activeChannel);
    } else if(activeDM){
        socket.emit("get_dm", activeDM);
    }
}

socket.on("message_list", msgs=>{
    messages.innerHTML="";
    msgs.forEach(m=>{
        const li=document.createElement("li");
        li.textContent=m;
        messages.appendChild(li);
    });
});

function sendMessage(){
    const msg=input.value.trim();
    if(msg==="") return;
    if(activeChannel) socket.emit("message",{channel:activeChannel,msg});
    else if(activeDM) socket.emit("dm",{to:activeDM,msg});
    input.value="";
}

// --- Typing ---
input.addEventListener("input", ()=>{
    if(!typing){ typing=true; socket.emit("typing",{channel:activeChannel,dm:activeDM}); }
    clearTimeout(typingTimeout);
    typingTimeout=setTimeout(stopTyping,1000);
});
function stopTyping(){ if(typing){ typing=false; socket.emit("stop_typing",{channel:activeChannel,dm:activeDM}); } }
socket.on("show_typing", data=>typingBox.textContent=`🟡 ${data.nickname} yazıyor...`);
socket.on("hide_typing", data=>typingBox.textContent="");

// --- Voice chat ---
async function toggleVoice(){
    if(!voiceActive){ await startVoice(); voiceBtn.textContent="🔴 Durdur"; voiceActive=true; }
    else{ stopVoice(); voiceBtn.textContent="🎤 Voice Chat Başlat"; voiceActive=false; }
}
async function startVoice(){
    localStream=await navigator.mediaDevices.getUserMedia({audio:true});
    const audioEl=document.createElement("audio");
    audioEl.srcObject=localStream; audioEl.autoplay=true; audioEl.muted=true;
    document.body.appendChild(audioEl);
    socket.emit("join_room","global");
}
function stopVoice(){
    if(localStream){ localStream.getTracks().forEach(t=>t.stop()); localStream=null; }
    for(let id in peers){ peers[id].close(); }
    peers={};
}
socket.on("new_peer", async data=>{
    const peerId=data.id;
    if(peers[peerId] || !localStream) return;
    const pc=new RTCPeerConnection(config);
    peers[peerId]=pc;
    localStream.getTracks().forEach(track=>pc.addTrack(track,localStream));
    pc.ontrack=e=>{ const audio=document.createElement("audio"); audio.srcObject=e.streams[0]; audio.autoplay=true; document.body.appendChild(audio); };
    pc.onicecandidate=e=>{ if(e.candidate) socket.emit("ice_candidate",{to:peerId,candidate:e.candidate}); };
    const offer=await pc.createOffer();
    await pc.setLocalDescription(offer);
    socket.emit("offer",{to:peerId,offer});
});
socket.on("offer", async data=>{
    const pc=new RTCPeerConnection(config);
    peers[data.from]=pc;
    localStream.getTracks().forEach(track=>pc.addTrack(track,localStream));
    pc.ontrack=e=>{ const audio=document.createElement("audio"); audio.srcObject=e.streams[0]; audio.autoplay=true; document.body.appendChild(audio); };
    pc.onicecandidate=e=>{ if(e.candidate) socket.emit("ice_candidate",{to:data.from,candidate:e.candidate}); };
    await pc.setRemoteDescription(data.offer);
    const answer=await pc.createAnswer();
    await pc.setLocalDescription(answer);
    socket.emit("answer",{to:data.from,answer});
});
socket.on("answer", async data=> await peers[data.from].setRemoteDescription(data.answer));
socket.on("ice_candidate", async data=>{ if(peers[data.from]) await peers[data.from].addIceCandidate(data.candidate); });

updateChannels();
</script>
</body></html>"""

@app.route('/')
def index():
    return render_template_string(html)

# --- Socket handlers ---
@socketio.on("join")
def handle_join(nickname):
    users[request.sid]=nickname
    emit("user_list", list(users.values()), broadcast=True)
    send(f"💬 {nickname} katıldı!", broadcast=True)

@socketio.on("get_messages")
def handle_get_messages(channel):
    msgs = channels.get(channel,[])
    emit("message_list", msgs)

@socketio.on("message")
def handle_message(data):
    channel = data["channel"]
    text = f"{users.get(request.sid,'Anon')}: {data['msg']}"
    channels[channel].append(text)
    emit("message_list", channels[channel], broadcast=True)

# --- DM handlers ---
@socketio.on("get_dm")
def handle_get_dm(target):
    for sid,nick in users.items():
        if nick==target:
            key = tuple(sorted([request.sid,sid]))
            msgs = dms.get(key,[])
            emit("message_list", msgs)
            break

@socketio.on("dm")
def handle_dm(data):
    target = data["to"]
    text = f"{users.get(request.sid,'Anon')}: {data['msg']}"
    for sid,nick in users.items():
        if nick==target:
            key = tuple(sorted([request.sid,sid]))
            if key not in dms: dms[key]=[]
            dms[key].append(text)
            emit("message_list", dms[key], room=[request.sid,sid])
            break

@socketio.on("typing")
def handle_typing(data):
    emit("show_typing", {"nickname": users.get(request.sid,"Anon")}, broadcast=True, include_self=False)

@socketio.on("stop_typing")
def handle_stop_typing(data):
    emit("hide_typing", {"nickname": users.get(request.sid,"Anon")}, broadcast=True, include_self=False)

@socketio.on("join_room")
def handle_join_room(room):
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

if __name__=="__main__":
    print("🔌 Ngrok başlatılıyor...")
    public_url = ngrok.connect(5000)
    print(f"🌍 Ngrok aktif: {public_url.public_url}")
    threading.Thread(target=start_server, daemon=True).start()
    time.sleep(2)
    webbrowser.open(public_url.public_url)
    input("Sunucuyu kapatmak için ENTER'a bas...")



