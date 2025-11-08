from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, send, emit, join_room
import threading, webbrowser, time
from pyngrok import ngrok

app = Flask(__name__)
app.config['SECRET_KEY'] = 'turkcord_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

users = {}
channels = {
    "TRcord Official": [],
    "Agalar": [],
    "Eriyen Tekerlek": []
}

html = """<!DOCTYPE html>
<html>
<head>
<title>TurkCord 💬 + Voice + DM</title>
<style>
body { font-family: Arial; background:#121212; color:#eee; margin:0; display:flex; height:100vh; flex-direction:column; }
.banner {
  background:#1e90ff;
  color:white;
  text-align:center;
  padding:10px;
  font-weight:bold;
  cursor:pointer;
  transition:0.2s;
}
.banner:hover { background:#3aa0ff; }
.main { display:flex; flex:1; }
.server-sidebar { width:70px; background:#202225; display:flex; flex-direction:column; align-items:center; padding-top:10px; }
.server { width:50px; height:50px; border-radius:50%; background:#7289da; margin:8px; display:flex; align-items:center; justify-content:center; cursor:pointer; font-size:24px; }
.server.active { border:2px solid #fff; }
.channel-sidebar { width:180px; background:#2f3136; padding:10px; }
.channel { padding:5px 8px; margin:4px 0; border-radius:5px; cursor:pointer; }
.channel.active { background:#7289da; }
.user-sidebar { width:150px; background:#2c2f33; padding:10px; overflow-y:auto; }
.user { cursor:pointer; margin:4px 0; }
.user:hover { text-decoration:underline; }
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

<div class="banner" onclick="window.open('https://efeoyunkeyfi10.netlify.app/', '_blank')">
  🎮 Efe'nin Oyun Keyfi — Eğlenceyi Maksimuma Çıkar! 🔵
</div>

<div class="main">
  <div class="server-sidebar">
    <div class="server" id="server1">🦆</div>
    <div class="server" id="server2">🐰</div>
    <div class="server" id="server3">🖱️</div>
  </div>

  <div class="channel-sidebar" id="channelSidebar"></div>
  <div class="user-sidebar" id="userSidebar"><h4>👥 Kullanıcılar</h4></div>

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

let activeServer = "server1";
let activeChannel = "TRcord Official";
let dmRoom = null;
const servers = { "server1":["TRcord Official"], "server2":["Agalar"], "server3":["Eriyen Tekerlek"] };

const channelSidebar = document.getElementById("channelSidebar");
const messages = document.getElementById("messages");
const input = document.getElementById("msg");
const typingBox = document.getElementById("typing");
const userSidebar = document.getElementById("userSidebar");
const voiceBtn = document.getElementById("voiceBtn");

let typing=false, typingTimeout;
let localStream=null, peers={}, voiceActive=false;
const config = { iceServers:[{urls:"stun:stun.l.google.com:19302"}] };

for(let s in servers){
  document.getElementById(s).onclick = ()=>{
    activeServer = s;
    updateServerUI();
    activeChannel = servers[s][0];
    dmRoom = null;
    updateChannels();
    updateMessages();
  }
}
function updateServerUI(){
  for(let s in servers){ document.getElementById(s).classList.remove("active"); }
  document.getElementById(activeServer).classList.add("active");
}

function updateChannels(){
  channelSidebar.innerHTML = "";
  servers[activeServer].forEach(ch=>{
    const div = document.createElement("div");
    div.textContent = ch;
    div.classList.add("channel");
    if(ch===activeChannel && !dmRoom) div.classList.add("active");
    div.onclick = ()=>{
      activeChannel = ch;
      dmRoom = null;
      updateChannels();
      updateMessages();
    }
    channelSidebar.appendChild(div);
  });
}

socket.on("user_list", list=>{
  userSidebar.innerHTML="<h4>👥 Kullanıcılar</h4>";
  list.forEach(u=>{
    if(u===nickname) return;
    const div = document.createElement("div");
    div.textContent = u;
    div.classList.add("user");
    div.onclick = ()=>{
      dmRoom = `DM_${[nickname,u].sort().join("_")}`;
      messages.innerHTML="";
      input.placeholder = `DM: ${u} mesaj yaz...`;
      socket.emit("join_dm", dmRoom);
    }
    userSidebar.appendChild(div);
  });
});

function updateMessages(){
  messages.innerHTML="";
  if(dmRoom){ socket.emit("get_dm_messages", dmRoom); }
  else { socket.emit("get_messages", activeChannel); }
}
socket.on("message_list", msgs=>{
  messages.innerHTML="";
  msgs.forEach(m=>{
    const li=document.createElement("li");
    li.textContent=m;
    messages.appendChild(li);
  });
});
socket.on("dm_message_list", msgs=>{
  if(dmRoom){
    messages.innerHTML="";
    msgs.forEach(m=>{
      const li=document.createElement("li");
      li.textContent=m;
      messages.appendChild(li);
    });
  }
});

function sendMessage(){
  const msg=input.value.trim();
  if(msg==="") return;
  if(dmRoom){ socket.emit("dm_message",{room:dmRoom,msg}); }
  else { socket.emit("message",{channel:activeChannel,msg}); }
  input.value="";
}

input.addEventListener("input", ()=>{
  if(!typing){ typing=true; socket.emit("typing",{channel:activeChannel,dm:dmRoom}); }
  clearTimeout(typingTimeout);
  typingTimeout=setTimeout(stopTyping,1000);
});
function stopTyping(){ if(typing){ typing=false; socket.emit("stop_typing",{channel:activeChannel,dm:dmRoom}); } }
socket.on("show_typing", d=> typingBox.textContent=`🟡 ${d.nickname} yazıyor...`);
socket.on("hide_typing", d=> typingBox.textContent="");

async function toggleVoice(){ if(!voiceActive){ await startVoice(); voiceBtn.textContent="🔴 Durdur"; voiceActive=true; } else{ stopVoice(); voiceBtn.textContent="🎤 Voice Chat Başlat"; voiceActive=false; } }
async function startVoice(){ localStream=await navigator.mediaDevices.getUserMedia({audio:true}); const audioEl=document.createElement("audio"); audioEl.srcObject=localStream; audioEl.autoplay=true; audioEl.muted=true; document.body.appendChild(audioEl); socket.emit("join_room","global"); }
function stopVoice(){ if(localStream){ localStream.getTracks().forEach(t=>t.stop()); localStream=null;} for(const id in peers){ peers[id].close();} peers={}; }
</script>
</body></html>
"""

@app.route('/')
def index():
    return render_template_string(html)

@socketio.on("join")
def handle_join(nickname):
    users[request.sid] = nickname
    emit("user_list", list(users.values()), broadcast=True)

@socketio.on("get_messages")
def handle_get_messages(channel):
    emit("message_list", channels.get(channel, []))

@socketio.on("message")
def handle_message(data):
    ch = data["channel"]
    nick = users.get(request.sid,"Anon")
    text = f"{nick}: {data['msg']}"
    channels.setdefault(ch, []).append(text)
    emit("message_list", channels[ch], broadcast=True)

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
