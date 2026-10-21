/* MUSE live voice — hands-free conversation with the lab.
   Listen (energy VAD) → /api/voice/hear (whisper) → /api/voice/talk (MUSE's own brain + lab tools; renders → /api/generate)
   → reply spoken by VOICE (Kokoro). Talking over MUSE stops her (barge-in). Docked card, top-right. */
window.MUSE=(function(){
  const S={on:false,state:'off',stream:null,ctx:null,an:null,rec:null,chunks:[],talking:false,quietAt:0,startAt:0,
           floor:0.008,job:null,prevOn:true,raf:0,lastHeard:''};
  const START=2.6,STOP_MS=900,MIN_MS=350,MAX_MS=30000;          // speech = RMS > floor*START; end after STOP_MS quiet
  let card=null,BIG=null,MINI=null,FLOAT=null,RING=null,RINGC=null;
  const LOOKS=['pearl','halo','particles','crystal'];
  let STYLE=(()=>{try{return localStorage.getItem('mml.musestyle')||'pearl'}catch(e){return 'pearl'}})();
  function orbs(fn){if(window.MuseOrb)fn();else addEventListener('museorb-ready',fn,{once:true})}
  function setStyle(s,push){if(LOOKS.indexOf(s)<0)return;STYLE=s;try{localStorage.setItem('mml.musestyle',s)}catch(e){}
    if(BIG)BIG.style(s);if(MINI)MINI.style(s);if(FLOAT)FLOAT.style(s);if(RING)RING.style(s);
    if(push)fetch('/api/prefs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:'musestyle',value:s})}).catch(()=>{})}
  fetch('/api/prefs',{cache:'no-store'}).then(r=>r.json()).then(d=>{if(d&&d.musestyle)setStyle(d.musestyle)}).catch(()=>{});
  function mini(){const b=document.getElementById('b-muse'),c=b&&b.querySelector('canvas');if(!c||MINI)return;
    orbs(()=>{MINI=MuseOrb.mount(c,{style:STYLE,small:true,state:'idle'})})}
  /* floating MUSE: always on top of every screen (chat, editor, series, downloader…), drag anywhere, tap to talk */
  let FLOATON=(()=>{try{return localStorage.getItem('mml.musefloat')!=='0'}catch(e){return true}})();
  function float(){let f=document.getElementById('muse-float');
    if(!FLOATON){if(f){if(FLOAT)FLOAT.destroy();FLOAT=null;f.remove()}return}
    if(f)return;
    f=document.createElement('div');f.id='muse-float';f.title='MUSE — tap to talk, drag to move';
    f.style.cssText='position:fixed;z-index:10001;width:68px;height:68px;border-radius:50%;cursor:grab;touch-action:none;'+
      'background:radial-gradient(circle,rgba(0,0,0,.35),transparent 70%);filter:drop-shadow(0 6px 16px rgba(0,0,0,.5))';
    let p={x:innerWidth-84,y:innerHeight-250};try{Object.assign(p,JSON.parse(localStorage.getItem('mml.musefloatpos')||'{}'))}catch(e){}
    const place=()=>{p.x=Math.max(4,Math.min(innerWidth-72,p.x));p.y=Math.max(4,Math.min(innerHeight-72,p.y));f.style.left=p.x+'px';f.style.top=p.y+'px'};
    place();addEventListener('resize',place);
    const c=document.createElement('canvas');c.style.cssText='width:100%;height:100%;display:block';f.appendChild(c);document.body.appendChild(f);
    let d=null,mv=0;
    f.addEventListener('pointerdown',e=>{d=[e.clientX-p.x,e.clientY-p.y];mv=0;f.setPointerCapture(e.pointerId)});
    f.addEventListener('pointermove',e=>{if(!d)return;const nx=e.clientX-d[0],ny=e.clientY-d[1];mv+=Math.abs(nx-p.x)+Math.abs(ny-p.y);
      if(mv>8){p.x=nx;p.y=ny;place()}});
    f.addEventListener('pointerup',()=>{if(!d)return;d=null;if(mv>8){try{localStorage.setItem('mml.musefloatpos',JSON.stringify(p))}catch(e){}}else S.on?stop():start()});
    orbs(()=>{FLOAT=MuseOrb.mount(c,{style:STYLE,small:true,still:true,state:S.on?S.state:'idle'})})}
  function setFloat(on){FLOATON=on;try{localStorage.setItem('mml.musefloat',on?'1':'0')}catch(e){}float()}
  /* MUSE inside the live-status ring of the working job's bubble (one shared 3D view, moved to the newest live ring) */
  setInterval(()=>{const sl=[...document.querySelectorAll('.mb-orb-slot')].pop();
    if(!sl){if(RINGC&&RINGC.parentNode)RINGC.remove();return}
    if(!RINGC){RINGC=document.createElement('canvas');orbs(()=>{RING=MuseOrb.mount(RINGC,{style:STYLE,small:true,still:true,state:'thinking'})})}
    if(RINGC.parentNode!==sl)sl.appendChild(RINGC);
    if(RING)RING.state(VOICE.busy()?'speaking':'thinking')},500);
  function boot(){mini();float()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
  /* settings → MUSE look: the 4 live styles side by side */
  let PREV=[];
  function openLook(){head('sparkle','var(--panel2)','MUSE LOOK');
    $('#s-body').innerHTML='<div style="width:100%;flex:1 1 100%;grid-column:1/-1"><p style="color:var(--dim);margin:0 0 10px">How MUSE looks in the header and while you talk with her. Drag to spin.</p>'+
      '<label style="display:flex;gap:8px;align-items:center;margin:0 0 12px">What should MUSE call you? <input id="mu-nm" maxlength="40" placeholder="your name" style="flex:1;max-width:240px"></label>'+
      '<label style="display:flex;gap:8px;align-items:center;margin:0 0 12px"><input type="checkbox" id="mu-fl" '+(FLOATON?'checked':'')+'> Floating MUSE on every screen (drag her anywhere, tap to talk)</label>'+
      '<div style="display:grid;width:100%;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px">'+
      MuseOrbStyles().map(x=>`<button class="vc ${x.id===STYLE?'on':''}" data-look="${x.id}" style="display:block;width:auto;min-width:0;text-align:left;padding:8px">
        <canvas style="width:100%;height:130px;display:block"></canvas><b>${x.name}</b><small style="display:block;opacity:.7">${x.desc}</small></button>`).join('')+'</div></div>';
    $('#s-ft').innerHTML='';
    $('#mu-fl').onchange=e=>setFloat(e.target.checked);
    fetch('/api/voice/name').then(r=>r.json()).then(d=>{const i=$('#mu-nm');if(i&&!i.value)i.value=d.name||''}).catch(()=>{});
    $('#mu-nm').onchange=e=>fetch('/api/voice/name',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:e.target.value})})
      .then(()=>toast(e.target.value?'MUSE will call you '+e.target.value:'MUSE will ask your name')).catch(()=>{});
    PREV.forEach(o=>o.destroy());PREV=[];
    orbs(()=>{$$('#s-body [data-look]').forEach(b=>{const cv=b.querySelector('canvas');
      PREV.push(MuseOrb.mount(cv,{style:b.dataset.look,state:b.dataset.look===STYLE?'speaking':'listening'}));
      b.onclick=()=>{if(cv.museMoved&&cv.museMoved())return;setStyle(b.dataset.look,true);toast('MUSE look: '+b.querySelector('b').textContent);
        $$('#s-body [data-look]').forEach(x=>x.classList.toggle('on',x===b))}})});
    openSheet()}
  function MuseOrbStyles(){return (window.MuseOrb&&MuseOrb.STYLES)||LOOKS.map(id=>({id,name:id,desc:''}))}

  function el(){
    if(card)return card;
    card=document.createElement('div');card.id='muse-card';
    card.innerHTML='<canvas class="mu-big"></canvas><div class="mu-top"><b>MUSE</b><span class="mu-st">off</span>'+
      '<button class="mu-m mu-off" title="Offload all AI models from the GPU">'+(window.MI?MI.html('power'):'off')+'</button>'+'<button class="mu-m" title="Mute my mic">'+(window.MI?MI.html('mic'):'mic')+'</button>'+'<button class="mu-x" title="End conversation">'+(window.MI?MI.html('close'):'×')+'</button></div>'+
      '<div class="mu-you"></div><div class="mu-hint">Just talk — I\'ll answer out loud. Talk over me to interrupt.</div>';
    const css=document.createElement('style');css.textContent=
      '#muse-card{position:fixed;top:64px;right:16px;z-index:10000;width:300px;max-width:calc(100vw - 32px);padding:12px 14px;'+
      'border-radius:16px;background:var(--panel2,#14141c);color:var(--text,#eee);border:1px solid rgba(255,255,255,.12);'+
      'box-shadow:0 10px 40px rgba(0,0,0,.5);font-size:13px;backdrop-filter:blur(14px)}'+
      '#muse-card .mu-top{display:flex;align-items:center;gap:8px}#muse-card .mu-st{opacity:.7;flex:1;font-size:12px}'+
      '#muse-card .mu-m{background:none;border:1px solid rgba(255,255,255,.18);border-radius:10px;color:inherit;cursor:pointer;padding:3px 7px;margin-right:6px}'+
      '#muse-card .mu-m.on{background:#ff4d4d;border-color:#ff4d4d;color:#fff}'+
      '#muse-card .mu-x{background:none;border:0;color:inherit;cursor:pointer;font-size:16px;opacity:.7}'+
      '#muse-card .mu-orb{width:14px;height:14px;border-radius:50%;background:#666;transition:transform .08s,background .3s}'+
      '#muse-card[data-s=listening] .mu-orb{background:#3ddc97}#muse-card[data-s=hearing] .mu-orb{background:#ffd23f}'+
      '#muse-card[data-s=thinking] .mu-orb{background:#7aa2ff;animation:muP 1s infinite}#muse-card[data-s=speaking] .mu-orb{background:#ff5fd2;animation:muP .6s infinite}'+
      '#muse-card[data-s=error] .mu-orb{background:#ff4d4d}@keyframes muP{50%{transform:scale(1.35)}}'+
      '#muse-card .mu-big{width:100%;height:150px;display:block;cursor:grab}'+
      '#b-muse{padding:2px}#b-muse canvas{pointer-events:auto}'+
      '#muse-card .mu-you{margin-top:8px;min-height:1em;font-style:italic;opacity:.85}#muse-card .mu-hint{margin-top:6px;font-size:11px;opacity:.55}'+
      '#b-muse.on{color:#3ddc97}';
    document.head.appendChild(css);document.body.appendChild(card);
    card.querySelector('.mu-x').onclick=stop;
    card.querySelector('.mu-m:not(.mu-off)').onclick=()=>mute(!S.muted);
    card.querySelector('.mu-off').onclick=()=>offload();
    orbs(()=>{BIG=MuseOrb.mount(card.querySelector('.mu-big'),{style:STYLE,state:S.state})});
    return card}
  const LABEL={off:'off',starting:'starting…',listening:'listening',hearing:'hearing you…',thinking:'thinking…',speaking:'speaking',error:'problem'};
  function set(st,msg){S.state=st;const os=st==='starting'?'thinking':st;if(BIG)BIG.state(os);if(MINI)MINI.state(os);if(FLOAT)FLOAT.state(os);const c=el();c.dataset.s=st;c.querySelector('.mu-st').textContent=msg||LABEL[st]||st}
  function you(t){el().querySelector('.mu-you').textContent=t?'“'+t+'”':''}
  function btn(){const b=document.getElementById('b-muse');if(b){b.classList.toggle('on',S.on);b.title=S.on?'MUSE is listening — tap to end':'MUSE — talk to the lab hands-free'}}

  async function startBasic(){
    if(S.on)return;
    if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){el();set('error','the mic needs https or this PC');return}
    S.on=true;btn();set('starting');you('');
    let err=null;
    for(const c of [{audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}},{audio:true}]){   // plain retry: some headsets reject the extras
      try{S.stream=await navigator.mediaDevices.getUserMedia(c);err=null;break}catch(e){err=e}}
    if(err){S.on=false;btn();const n=err.name||'';console.warn('MUSE mic',err);
      set('error',n==='NotAllowedError'||n==='SecurityError'?(window.top!==window||!/^(127\.0\.0\.1|localhost)$/.test(location.hostname)&&location.protocol!=='https:'
          ?'this window cannot use the mic — open MML in Chrome on this PC (or over https)':'mic blocked — click the lock/mic icon left of the address bar, allow Microphone, then tap MUSE again')
        :n==='NotFoundError'?'no microphone found — plug one in or pick one in Windows Sound settings'
        :n==='NotReadableError'||n==='AbortError'?'the mic is busy in another app (Discord, a call, Steam…) or the headset is in music-only mode — free it, then tap MUSE again'
        :'mic error: '+(n||String(err)));return}
    S.noEars=null;                                             // ears that can't start: say so and stop listening (no endless "listening")
    fetch('/api/voice/warm',{method:'POST'}).then(r=>r.json()).then(d=>{if(d&&d.error&&S.on){S.noEars=d.error;set('error',d.error)}}).catch(()=>{});
    S.prevOn=VOICE.st.on;VOICE.st.on=true;                     // MUSE always answers out loud while live
    S.ctx=new (window.AudioContext||window.webkitAudioContext)();
    const src=S.ctx.createMediaStreamSource(S.stream);S.an=S.ctx.createAnalyser();S.an.fftSize=1024;src.connect(S.an);
    S.floor=0.008;set('listening');loop()}

  const TAB={create:'create',library:'library',projects:'production',editor:'editor',series:'series',motion:'motion',flow:'flow',downloader:'grab',social:'social'};
  async function start(){
    if(S.on)return;
    return startBasic()}
  function say(t){const c=el();let p=c.querySelector('.mu-say');if(!p){p=document.createElement('div');p.className='mu-say';p.style.cssText='margin-top:6px;max-height:90px;overflow:auto;font-size:12.5px;line-height:1.35';c.querySelector('.mu-you').after(p)}p.textContent=t}
  function mute(on){S.muted=!!on;const b=card&&card.querySelector('.mu-m:not(.mu-off)');
    if(b){b.classList.toggle('on',S.muted);b.innerHTML=window.MI?MI.html(S.muted?'mute':'mic'):(S.muted?'muted':'mic');b.title=S.muted?'Mic muted — tap to unmute':'Mute my mic'}
    if(S.stream)S.stream.getAudioTracks().forEach(t=>t.enabled=!S.muted);
    if(S.on&&S.state!=='speaking'&&S.state!=='thinking')set(S.muted?'idle':'listening',S.muted?'mic muted':undefined)}
  async function offload(){if(S.on)stop();toast('Offloading all AI models…');
    try{const d=await api('/api/offload',{method:'POST'});toast(d.offloaded&&d.offloaded.length?'Offloaded: '+d.offloaded.join(', ')+(d.render_kept?' (render kept running)':''):'Nothing was loaded')}
    catch(e){toast(e.message)}}
  function stop(){
    S.on=false;btn();cancelAnimationFrame(S.raf);
    try{if(S.rec&&S.rec.state!=='inactive')S.rec.stop()}catch(e){}
    S.rec=null;S.talking=false;
    if(S.stream)S.stream.getTracks().forEach(t=>t.stop());S.stream=null;
    if(S.ctx)S.ctx.close().catch(()=>{});S.ctx=null;
    VOICE.st.on=S.prevOn;
    if(BIG){BIG.destroy();BIG=null}if(MINI)MINI.state('idle');if(FLOAT)FLOAT.state('idle');
    if(card){card.remove();card=null}}

  function rms(){const a=new Float32Array(S.an.fftSize);S.an.getFloatTimeDomainData(a);let s=0;for(const v of a)s+=v*v;return Math.sqrt(s/a.length)}

  function loop(){
    if(!S.on)return;
    if(S.noEars){if(S.state!=='error')set('error',S.noEars);S.raf=requestAnimationFrame(loop);return}
    const r=rms(),now=performance.now(),speaking=VOICE.busy();
    const lv=S.talking?Math.min(1,r*14):0;if(BIG)BIG.level(lv);if(MINI)MINI.level(lv);if(FLOAT)FLOAT.level(lv);
    // her own voice leaks back even with echo-cancel: be stricter while she talks
    const th=Math.max(0.012,S.floor*START)*(speaking?2.2:1);
    if(!S.talking){
      if(r<th)S.floor=S.floor*0.995+r*0.005;                       // adapt to the room
      if(r>th){S.talking=true;S.startAt=now;S.quietAt=0;if(speaking)VOICE.stop();begin();set('hearing')}
      else if(S.state!=='thinking')set(speaking?'speaking':'listening');
    }else{
      if(r>th*0.7)S.quietAt=0;else if(!S.quietAt)S.quietAt=now;
      if((S.quietAt&&now-S.quietAt>STOP_MS)||now-S.startAt>MAX_MS){S.talking=false;finish(now-S.startAt-(S.quietAt?now-S.quietAt:0))}}
    if(S.state==='speaking'&&!speaking&&!S.talking)set('listening');
    if(S.watch&&now-(S.wAt||0)>1500){S.wAt=now;           // renders she started: tell them when each one lands
      Object.keys(S.watch).forEach(id=>{const j=(window._lastJobs||[]).find(x=>x.id===id);if(!j)return;
        if(j.status==='done'){delete S.watch[id];VOICE.say('Your '+({qimg:'picture',h3:'video',music3:'track',ace:'song',llama:'answer'}[j.model]||'render')+' is ready.',true)}
        else if(j.status==='error'){delete S.watch[id];VOICE.say('That render didn\'t finish.',true)}
        else if(j.status==='cancelled')delete S.watch[id]})}
    S.raf=requestAnimationFrame(loop)}

  function begin(){S.chunks=[];
    try{S.rec=new MediaRecorder(S.stream);S.rec.ondataavailable=e=>{if(e.data.size)S.chunks.push(e.data)};S.rec.start(200)}catch(e){S.rec=null}}

  function finish(ms){const rec=S.rec;S.rec=null;if(!rec)return;
    rec.onstop=()=>{if(!S.on)return;if(ms<MIN_MS){set('listening');return}
      const blob=new Blob(S.chunks,{type:rec.mimeType||'audio/webm'});send(blob)};
    try{rec.stop()}catch(e){}}

  async function send(blob){
    set('thinking','listening back…');
    const fd=new FormData();fd.append('audio',blob,'muse.webm');
    let d;try{d=await (await fetch('/api/voice/hear',{method:'POST',body:fd})).json()}catch(e){d={error:'the lab is offline'}}
    if(!S.on)return;
    if(d.error){set('error',d.error);setTimeout(()=>S.on&&set('listening'),3000);return}
    const t=(d.text||'').trim();if(!t){set('listening');return}
    you(t);
    if(/^(stop|goodbye|bye muse|end (the )?conversation|that'?s all)[.!]*$/i.test(t)){VOICE.say('Okay, talk soon.',true);setTimeout(stop,400);return}
    if(/^(stop|quiet|shush|be quiet)[.!]*$/i.test(t)){VOICE.stop();set('listening');return}
    set('thinking');
    // a real conversation turn (MUSE's own brain + lab tools) — only actual work (a render, a long MirAI task) becomes a chat job
    let d2;try{d2=await api('/api/voice/talk',{method:'POST',body:JSON.stringify({text:t,session:(window.SESS||{}).id||''})})}
    catch(e){if(!S.on)return;VOICE.say('Sorry, I couldn\'t think just now. Say that again?',true);set('listening');return}
    if(!S.on)return;
    const sess=(window.SESS||{}).id||'';
    try{
      if(d2.do==='make'||d2.do==='mirai'){
        const r=await api('/api/generate',{method:'POST',body:JSON.stringify({model:d2.do==='mirai'?'llama':'auto',prompt:d2.prompt||t,session:sess})});
        if(d2.do==='make'&&r&&r.id){S.watch=S.watch||{};S.watch[r.id]=1}
        try{stick=true;pollJobs(true);pollStatus()}catch(e){}}
      else if(d2.do==='cancel'&&d2.job){await api('/api/jobs/'+d2.job+'/cancel',{method:'POST'});try{pollJobs(true)}catch(e){}}
      else if(d2.do==='tab'&&TAB[d2.tab])setTab(TAB[d2.tab]);
    }catch(e){const m=String(e&&e.message||e);d2.say=/still working/i.test(m)?'I\'m still on your last request. Give me a moment.':'That didn\'t go through: '+m}
    say(d2.say||'');
    if(d2.say)VOICE.say(d2.say,true);
    set(d2.say?'speaking':'listening')}

  return {start,stop,toggle:()=>S.on?stop():start(),click:b=>{const c=b.querySelector('canvas');if(c&&c.museMoved&&c.museMoved())return;S.on?stop():start()},openLook,setStyle,setFloat,offload,get state(){return S.state}}})();
/* ?muse=1 opens MUSE on load (needs one tap for the mic on most browsers) */
if(/[?&]muse=1/.test(location.search))document.addEventListener('click',function f(){document.removeEventListener('click',f,true);MUSE.start()},true);
