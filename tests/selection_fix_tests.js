const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

let queriedRows = [];
global.window = {
  FIREBASE_CONFIG: {}, addEventListener(){}, removeEventListener(){}, requestAnimationFrame:null,
  NC_EMOJI: { svg:{} }, confirm(){ return true; }
};
Object.defineProperty(global, 'navigator', { value: { clipboard: { writeText: async () => true }, onLine: true }, configurable: true, writable: true });
global.document = {
  activeElement: { blur(){} },
  querySelectorAll(){ return queriedRows; },
  createElement(){ return { value:'', style:{}, setAttribute(){}, select(){}, remove(){}, click(){} }; },
  body: { appendChild(){} },
  execCommand(){ return true; }
};
global.localStorage = { getItem(){return null;}, setItem(){}, removeItem(){} };
global.React = { createRef(){ return { current:null }; } };
global.crypto = require('crypto').webcrypto;
global.NC = {
  deleteMessage: async () => true,
  updateChatMeta: async () => true
};
class DCLogic {
  setState(update, cb) {
    const patch = typeof update === 'function' ? update(this.state) : update;
    if (patch && typeof patch === 'object') this.state = { ...this.state, ...patch };
    if (cb) cb();
  }
  forceUpdate(cb){ if(cb) cb(); }
}
global.DCLogic = DCLogic;
const finalHtmlPath = process.argv[2] || 'www/index.html';
const runtimePath = process.argv[3] || 'build/selection-runtime.js';
const finalHtml = fs.readFileSync(finalHtmlPath, 'utf8');
const backendMarker = '/* ==================== НАЙТ-СИТИ НЕТ · БЭКЕНД';
const markerAt = finalHtml.indexOf(backendMarker);
if (markerAt < 0) throw new Error('Application script marker was not found');
const scriptStart = finalHtml.lastIndexOf('<script', markerAt);
const scriptOpenEnd = finalHtml.indexOf('>', scriptStart);
const scriptEnd = finalHtml.indexOf('</script>', markerAt);
if (scriptStart < 0 || scriptOpenEnd < 0 || scriptEnd < 0) throw new Error('Application script boundaries were not found');
let src = finalHtml.slice(scriptOpenEnd + 1, scriptEnd);
src += '\n;globalThis.__NCComponent = Component; globalThis.__NCBackend = NC;';
vm.runInThisContext(src, { filename: finalHtmlPath + '#app' });
const Component = global.__NCComponent;

function app() {
  const c = new Component();
  c._matrixEnsure = () => {};
  c._sizeCustomWall = () => {};
  c.persist = () => {};
  c._toastMessages = [];
  c._toast = (x) => c._toastMessages.push(x);
  c._vibrate = () => {};
  c._isServerChat = () => false;
  c._serverChatOf = () => null;
  c.askConfirm = (_text, yes) => yes();
  c.openChat = (id) => c.setState({ activeId:id, screen:'chat' });
  c.state = {
    ...c.state,
    screen:'chat', activeId:'a', recording:false,
    threads:{
      a:[
        {id:1,type:'text',text:'one',from:'me'},
        {id:'2',type:'image',imgSrc:'x',from:'them'},
        {id:3,type:'file',fileName:'a.pdf',fileData:'data:x',from:'them'},
        {id:'sys-4',type:'text',text:'// СИСТЕМА: joined',from:'them'},
        {id:'e2e-5',type:'text',text:'🔒 …',_e2e:true,from:'them'},
        {id:'6',type:'sticker',emojiId:'skull',from:'them'},
        {id:'7',type:'voice',audioSrc:'voice',duration:'0:12',from:'them'}
      ],
      b:[{id:1,type:'text',text:'other',from:'them'}],
      target:[], server:[]
    },
    contacts:[
      {id:'a',name:'A',pinnedId:null}, {id:'b',name:'B',pinnedId:null},
      {id:'target',name:'Target',pinnedId:null}, {id:'server',name:'Server',pinnedId:null}
    ],
    selPosts:[], selChatId:null, selActionPending:false, selActionToken:null,
    fwdIds:null, fwdSourceChatId:null,
    msgMenu:'old', postFor:'old', reactFor:'old', replyTo:'old', editing:'old',
    emojiPanel:true, attachOpen:true, inChatSearch:true, inChatQuery:'query', chatMenu:true,
    profileOpen:true, commentsFor:'x', iceUnlockFor:'x'
  };
  return c;
}

function eventProbe() {
  return {
    prevented:false, stopped:false,
    preventDefault(){ this.prevented=true; },
    stopPropagation(){ this.stopped=true; }
  };
}

async function run() {
  let n = 0;
  const test = async (name, fn) => { await fn(); n++; console.log('PASS', name); };

  await test('stable string IDs and independent toggle', async () => {
    const c=app(); c.togglePostSel(1); c.togglePostSel('2');
    assert.deepStrictEqual(c.state.selPosts,['1','2']);
    c.togglePostSel(1); assert.deepStrictEqual(c.state.selPosts,['2']);
    c.togglePostSel('2'); assert.deepStrictEqual(c.state.selPosts,[]); assert.equal(c.state.selChatId,null);
  });

  await test('selection start closes conflicting modes and cancels recording', async () => {
    const c=app(); let cancelled=0; c.state.recording=true; c.cancelRec=()=>{cancelled++; c.state.recording=false;};
    c.togglePostSel(1);
    assert.equal(cancelled,1);
    for (const k of ['msgMenu','postFor','reactFor','replyTo','editing','commentsFor','iceUnlockFor']) assert.equal(c.state[k],null,k);
    assert.equal(c.state.emojiPanel,false); assert.equal(c.state.attachOpen,false); assert.equal(c.state.inChatSearch,false); assert.equal(c.state.inChatQuery,'');
    assert.equal(c.state.chatMenu,false); assert.equal(c.state.profileOpen,false);
  });

  await test('selection cannot leak into another chat', async () => {
    const c=app(); c.togglePostSel(1); c.state.activeId='b'; c.componentDidUpdate();
    assert.deepStrictEqual(c.state.selPosts,[]); assert.equal(c.state.selChatId,null);
  });

  await test('snapshot reconciliation removes deleted IDs and exits hidden mode', async () => {
    const c=app(); c.togglePostSel(1); c.togglePostSel('2');
    c.state.threads.a = [{id:'2',type:'image'}]; c.componentDidUpdate(); assert.deepStrictEqual(c.state.selPosts,['2']);
    c.state.threads.a=[]; c.componentDidUpdate(); assert.deepStrictEqual(c.state.selPosts,[]); assert.equal(c.state.selChatId,null); assert.equal(c._selectionActive(),false);
  });

  await test('sorting/rebuild keeps selection by ID rather than index', async () => {
    const c=app(); c.togglePostSel('2'); c.state.threads.a=[...c.state.threads.a].reverse(); c.componentDidUpdate();
    assert.deepStrictEqual(c.state.selPosts,['2']); assert.equal(c._selectionSnapshot().messages[0].id,'2');
  });

  await test('nested message actions are blocked during selection', async () => {
    const c=app(); c.togglePostSel(1); let normal=0; const e=eventProbe();
    c._messageInteraction('2',e,()=>normal++);
    assert.equal(normal,0); assert.equal(e.prevented,true); assert.equal(e.stopped,true); assert.deepStrictEqual(c.state.selPosts,['1','2']);
  });

  await test('nested normal action stops bubbling but remains usable outside selection', async () => {
    const c=app(); c.clearPostSel(); let normal=0; const e=eventProbe();
    c._messageInteraction('2',e,()=>normal++);
    assert.equal(normal,1); assert.equal(e.prevented,false); assert.equal(e.stopped,true);
  });

  await test('duplicate contextmenu after pointer long-press cannot toggle twice', async () => {
    const c=app(); const e1=eventProbe(); c.postLong(1,e1); assert.deepStrictEqual(c.state.selPosts,['1']);
    const e2=eventProbe(); c.postLong(1,e2); assert.deepStrictEqual(c.state.selPosts,['1']);
    assert.equal(e1.prevented,true); assert.equal(e2.prevented,true);
  });

  await test('copy is locked, succeeds atomically and serializes special messages', async () => {
    const c=app(); c.togglePostSel(1); c.togglePostSel('2'); c.togglePostSel('3'); c.togglePostSel('6'); c.togglePostSel('7');
    let captured='', resolveCopy; navigator.clipboard.writeText=(v)=>{captured=v; return new Promise(r=>resolveCopy=r);};
    const p=c.copySelPosts(); assert.equal(c.state.selActionPending,true); c.copySelPosts();
    assert.match(captured,/one/); assert.match(captured,/\[Фото\]/); assert.match(captured,/\[Файл: a\.pdf\]/); assert.match(captured,/\[Стикер: skull\]/); assert.match(captured,/\[Голосовое · 0:12\]/);
    resolveCopy(); await p; assert.deepStrictEqual(c.state.selPosts,[]); assert.equal(c.state.selActionPending,false);
  });

  await test('copy failure preserves selection', async () => {
    const c=app(); c.togglePostSel(1); navigator.clipboard.writeText=async()=>{throw new Error('denied');};
    await c.copySelPosts(); assert.deepStrictEqual(c.state.selPosts,['1']); assert.equal(c.state.selActionPending,false);
  });

  await test('old async action cannot clear a new chat selection', async () => {
    const c=app(); c.togglePostSel(1); let resolveCopy; navigator.clipboard.writeText=()=>new Promise(r=>resolveCopy=r);
    const pending=c.copySelPosts(); c.state.activeId='b'; c.componentDidUpdate(); c.togglePostSel(1); assert.equal(c.state.selChatId,'b');
    resolveCopy(); await pending; assert.equal(c.state.selChatId,'b'); assert.deepStrictEqual(c.state.selPosts,['1']);
  });

  await test('cancel stays usable during pending action and old completion cannot clear a new selection', async () => {
    const c=app(); c.togglePostSel(1); let resolveCopy; navigator.clipboard.writeText=()=>new Promise(r=>resolveCopy=r);
    const pending=c.copySelPosts(); assert.equal(c.state.selActionPending,true); c.clearPostSel(); c.togglePostSel('2');
    resolveCopy(); await pending; assert.deepStrictEqual(c.state.selPosts,['2']); assert.equal(c.state.selChatId,'a');
    assert.match(finalHtml,/<button class="nc-selection-btn" onclick="\{\{ clearPostSel \}\}"/);
  });

  await test('local forward accepts numeric and string IDs and clears source selection', async () => {
    const c=app(); c.togglePostSel(1); c.togglePostSel('2'); c.fwdSelectedPosts();
    assert.deepStrictEqual(c.state.fwdIds,['1','2']); await c.forwardTo('target');
    assert.equal(c.state.threads.target.length,2); assert.deepStrictEqual(c.state.selPosts,[]); assert.equal(c.state.activeId,'target');
  });

  await test('partial server forward removes successes and preserves failures', async () => {
    const c=app(); c._isServerChat=(id)=>id==='server'; c._sendMediaBackend=async(_id,m)=>String(m.id)==='1';
    c.togglePostSel(1); c.togglePostSel('2'); c.fwdSelectedPosts(); await c.forwardTo('server');
    assert.deepStrictEqual(c.state.selPosts,['2']); assert.equal(c.state.selChatId,'a'); assert.deepStrictEqual(c.state.fwdIds,['2']); assert.equal(c.state.selActionPending,false);
  });

  await test('system and locked E2E capabilities block unsafe actions', async () => {
    const c=app(); c.togglePostSel('sys-4'); let snap=c._selectionSnapshot(); let caps=c._selectionCapabilities(snap);
    assert.deepStrictEqual(caps,{copy:true,forward:false,pin:false,delete:false});
    c.clearPostSel(); c.togglePostSel('e2e-5'); caps=c._selectionCapabilities(c._selectionSnapshot());
    assert.equal(caps.copy,true); assert.equal(caps.forward,false); assert.equal(caps.pin,true); assert.equal(caps.delete,true);
  });

  await test('system selection cannot invoke delete/forward/pin', async () => {
    const c=app(); c.togglePostSel('sys-4'); const before=JSON.stringify(c.state.threads.a);
    c.deleteSelPosts(); c.fwdSelectedPosts(); await c.pinSelPosts();
    assert.equal(JSON.stringify(c.state.threads.a),before); assert.deepStrictEqual(c.state.selPosts,['sys-4']);
    assert.ok(c._toastMessages.length>=3);
  });

  await test('pin action requires one supported message and clears only after success', async () => {
    const c=app(); c.togglePostSel(1); await c.pinSelPosts();
    assert.equal(c.state.contacts.find(x=>x.id==='a').pinnedId,'1'); assert.deepStrictEqual(c.state.selPosts,[]);
  });

  await test('local delete removes selected and unpins by normalized ID', async () => {
    const c=app(); c.state.contacts.find(x=>x.id==='a').pinnedId=1; c.togglePostSel('1'); c.togglePostSel('2');
    await c._deleteSelection(c._selectionSnapshot());
    assert.deepStrictEqual(c.state.threads.a.map(x=>String(x.id)),['3','sys-4','e2e-5','6','7']);
    assert.equal(c.state.contacts.find(x=>x.id==='a').pinnedId,null); assert.deepStrictEqual(c.state.selPosts,[]);
  });

  await test('partial server delete leaves failed IDs selected', async () => {
    const c=app(); c._isServerChat=(id)=>id==='a'; c._serverChatOf=()=>({chatId:'srv-a'});
    global.__NCBackend.deleteMessage=async(_chat,id)=>{ if(String(id)==='2') throw new Error('offline'); return true; };
    c.togglePostSel(1); c.togglePostSel('2'); await c._deleteSelection(c._selectionSnapshot());
    assert.equal(c.state.threads.a.some(m=>String(m.id)==='1'),false); assert.equal(c.state.threads.a.some(m=>String(m.id)==='2'),true);
    assert.deepStrictEqual(c.state.selPosts,['2']); assert.equal(c.state.selActionPending,false);
    global.__NCBackend.deleteMessage=async()=>true;
  });

  await test('action double tap is rejected by operation token', async () => {
    const c=app(); c.togglePostSel(1); const snap=c._selectionSnapshot();
    const t1=c._beginSelectionAction(snap,'copy'); const t2=c._beginSelectionAction(snap,'copy');
    assert.ok(t1); assert.equal(t2,null); c._finishSelectionAction(t1,false); assert.equal(c.state.selActionPending,false);
  });

  await test('explicit cancel clears state, locks, gestures and stale UI', async () => {
    const c=app(); let cancelled=0; queriedRows=[{style:{transition:'x',transform:'translateX(1px)'},__cancelLongPress(){cancelled++;}}];
    c.togglePostSel(1); cancelled=0; c._selActionLock='x'; c._forwardLock='y'; c.state.fwdIds=['1']; c.state.fwdSourceChatId='a';
    c.clearPostSel(); assert.deepStrictEqual(c.state.selPosts,[]); assert.equal(c.state.selChatId,null); assert.equal(c.state.fwdIds,null);
    assert.equal(c._selActionLock,null); assert.equal(c._forwardLock,null); assert.equal(cancelled,1); assert.equal(queriedRows[0].style.transform,''); queriedRows=[];
  });

  await test('incoming message does not force scroll while selecting', async () => {
    const c=app(); let scroll=0; c.scrollBottom=()=>scroll++; c._lastActiveId='a'; c._lastMsgCount=c.state.threads.a.length-1;
    c.togglePostSel(1); c.componentDidUpdate(); assert.equal(scroll,0);
    c.clearPostSel(); c._lastMsgCount=c.state.threads.a.length-1; c.componentDidUpdate(); assert.equal(scroll,1);
  });

  await test('final HTML has stable keyed loop and adaptive safe-area UI', async () => {
    const runtime=fs.readFileSync(runtimePath,'utf8');
    assert.match(finalHtml,/<sc-for list="\{\{ messages \}\}" as="m" key="\{\{ m\.mid \}\}"/);
    assert.match(runtime,/const keyRaw = el\.getAttribute\("key"\)/);
    assert.match(runtime,/\{ key: String\(itemKey\) \}/);
    assert.match(finalHtml,/viewport-fit=cover/); assert.match(finalHtml,/safe-area-inset-bottom/); assert.match(finalHtml,/\.nc-msg-row\{touch-action:pan-y/);
  });

  console.log(`PASS selection final tests: ${n} scenarios`);
}

run().catch(e=>{ console.error('FAIL',e); process.exit(1); });
