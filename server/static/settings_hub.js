/* SETTINGS hub — every setting grouped by category with its own menu (left rail on desktop / the .exe window,
   a scrolling tab strip on phones). Each category reuses the panel that already owns those settings. */
(function(){
  let NAV=false,CUR='general';
  const owner=()=>typeof ME!=='undefined'&&ME.role==='owner',host=()=>typeof ME!=='undefined'&&ME.host;
  const CATS=[
    {id:'general',ic:'gear',name:'General',sub:'prompt engine · live render viewer',fn:()=>settingsPart('general')},
    {id:'ai',ic:'sparkle',name:'AI models',sub:'MirAI director model · cloud keys · cap · Civitai',fn:()=>{settingsPart('ai');
      if(typeof ME!=='undefined'&&ME.host){const old=document.getElementById('mpk');if(old)old.remove();   // the picker lives inside Settings
        const b=document.createElement('div');b.id='mpk';b.className='inl';$('#s-body').prepend(b);const cb=$('#cb-slot');if(cb)cb.remove();mpOpen()}}},
    {id:'look',ic:'palette',name:'Appearance',sub:'theme · fonts',fn:()=>{openThemes();
      $('#s-body').insertAdjacentHTML('afterbegin','<div style="width:100%;grid-column:1/-1;margin-bottom:12px"><button class="btn" id="hub-font">'+MI.html('type')+' MIR FONTS — pick a typeface…</button></div>');
      const f=$('#hub-font');if(f)f.onclick=()=>{closeSheet();window.MirFont&&MirFont.openPicker()}}},
    {id:'muse',ic:'sparkle',name:'MUSE',sub:'her 3D look · floating MUSE',fn:()=>MUSE.openLook()},
    {id:'voice',ic:'volume',name:'Voice',sub:'MirAI voice · speed',fn:()=>openVoice()},
    {id:'access',ic:'qr',name:'Access & people',sub:'my key · who has access',fn:()=>access()},
    {id:'system',ic:'server',name:'System',sub:'GPU engine · LAN address · app · library',fn:()=>settingsPart('system')},
    {id:'help',ic:'note',name:'Help & about',sub:'guide · version · report a bug',fn:()=>{const b=$('#b-about');b&&b.onclick&&b.onclick()}},
  ];
  function access(){head('qr','var(--panel2)','ACCESS & PEOPLE');
    $('#s-body').innerHTML='<div style="width:100%;grid-column:1/-1;display:grid;gap:10px">'+
      (owner()?'':'<button class="btn" data-a="key">'+MI.html('qr')+' My key — your key as a QR code (one device per key)</button>')+
      (owner()&&host()?'<button class="btn" data-a="key">'+MI.html('key')+' Master key — sees every chat (this PC only)</button>':'')+
      (host()?'<button class="btn" data-a="users">'+MI.html('shield')+' Host control — invite people, limits, who is online</button>':'')+
      '<p style="color:var(--dim);margin:4px 0 0">Each person gets their own key and sees only their own creations.</p></div>';
    $('#s-ft').innerHTML='';
    $$('#s-body [data-a]').forEach(b=>b.onclick=()=>go(b.dataset.a==='users'?openUsers:openMyKey));
    openSheet()}
  function go(fn){NAV=true;try{fn()}finally{NAV=false}rail()}
  /* keep the rail while a category's own panel draws itself; anything opened from elsewhere drops it */
  const _head=window.head;window.head=function(){if(!NAV)hub(false);return _head.apply(this,arguments)};
  const _close=window.closeSheet;window.closeSheet=function(){hub(false);return _close.apply(this,arguments)};
  function hub(on){const sh=$('#sheet');if(!sh)return;sh.classList.toggle('hub',on);const n=$('#s-nav');if(n)n.style.display=on?'':'none'}
  function rail(){const sh=$('#sheet');let n=$('#s-nav');
    if(!n){n=document.createElement('nav');n.id='s-nav';sh.insertBefore(n,$('#s-body'))}
    n.innerHTML='<div class="sn-t">SETTINGS</div>'+CATS.map(c=>`<button data-cat="${c.id}" class="${c.id===CUR?'on':''}">${MI.html(c.ic)}<span><b>${c.name}</b><small>${c.sub}</small></span></button>`).join('');
    n.querySelectorAll('[data-cat]').forEach(b=>b.onclick=()=>openSettings(b.dataset.cat));
    hub(true)}
  window.openSettings=function(cat){CUR=CATS.some(c=>c.id===cat)?cat:(CUR||'general');
    const c=CATS.find(x=>x.id===CUR);go(c.fn);
    setTimeout(()=>{if($('#sheet').classList.contains('on')&&!$('#sheet').classList.contains('hub'))rail()},0);   // panels that open async
    try{localStorage.setItem('mml.setcat',CUR)}catch(e){}};
  try{CUR=localStorage.getItem('mml.setcat')||'general'}catch(e){}
  const css=document.createElement('style');css.textContent=
    '#sheet.hub{width:min(1040px,calc(100vw - 24px));height:min(720px,calc(100dvh - 40px));display:grid!important;grid-template-columns:250px 1fr;grid-template-rows:auto 1fr auto}'+
    '#sheet.hub:not(.on){display:none!important}'+
    '#sheet.hub>.hd{grid-column:2}#sheet.hub>#s-nav{grid-column:1;grid-row:1/4;overflow:auto;border-right:1px solid var(--line2);padding:14px 10px;background:rgba(0,0,0,.18)}'+
    '#sheet.hub>#s-body{grid-column:2;overflow:auto;align-content:start;align-items:start;justify-content:start}#sheet.hub>#s-ft{grid-column:2}'+
    '#s-nav .sn-t{font:800 11px var(--mono,monospace);letter-spacing:.18em;color:var(--faint,#888);padding:4px 10px 10px}'+
    '#s-nav button{display:flex;gap:10px;align-items:flex-start;width:100%;text-align:left;background:none;border:0;color:var(--ink,#eee);padding:10px;border-radius:12px;cursor:pointer;margin-bottom:2px}'+
    '#s-nav button:hover{background:rgba(255,255,255,.05)}#s-nav button.on{background:var(--panel2,rgba(255,255,255,.08));box-shadow:inset 3px 0 0 var(--acc,#f60)}'+
    '#s-nav button b{display:block;font-size:13.5px}#s-nav button small{display:block;font-size:11px;color:var(--dim,#999);margin-top:2px;line-height:1.3}'+
    '@media (max-width:760px){#sheet.hub{grid-template-columns:1fr;grid-template-rows:auto auto 1fr auto;height:calc(100dvh - 24px)}'+
    '#sheet.hub>.hd{grid-column:1;grid-row:1}#sheet.hub>#s-nav{grid-column:1;grid-row:2;display:flex;gap:6px;overflow-x:auto;border-right:0;border-bottom:1px solid var(--line2);padding:8px}'+
    '#sheet.hub>#s-body{grid-column:1;grid-row:3}#sheet.hub>#s-ft{grid-column:1;grid-row:4}#s-nav .sn-t,#s-nav small{display:none!important}#s-nav button{width:auto;flex:none;white-space:nowrap;margin:0}}';
  css.textContent+='#s-body #mpk.inl{position:static;inset:auto;display:block;background:none;backdrop-filter:none;grid-column:1/-1;z-index:auto}'+
    '#s-body #mpk.inl .mp{width:100%;max-height:none;box-shadow:none;animation:none}#s-body #mpk.inl #mp-x{display:none}';
  document.head.appendChild(css);
})();
