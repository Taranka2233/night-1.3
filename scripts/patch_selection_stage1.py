from pathlib import Path
import argparse
import re

parser = argparse.ArgumentParser()
parser.add_argument("src")
parser.add_argument("out")
args = parser.parse_args()
src = Path(args.src)
out = Path(args.out)
text = src.read_text(encoding="utf-8")

def replace_once(old, new, label):
    global text
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, found {n}")
    text = text.replace(old, new, 1)

# viewport + CSS
replace_once('<meta name="viewport" content="width=device-width, initial-scale=1">',
             '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
             'viewport')
replace_once('.cp-scroll{scrollbar-width:none;-ms-overflow-style:none}',
'''.cp-scroll{scrollbar-width:none;-ms-overflow-style:none}
.nc-selection-bar{flex:none;display:grid;grid-template-columns:minmax(44px,.55fr) repeat(2,minmax(0,1fr));gap:6px;align-items:stretch;padding:8px max(8px,env(safe-area-inset-right,0px)) 8px max(8px,env(safe-area-inset-left,0px));background:#12121a;border-bottom:1px solid #00f0ff;position:relative;z-index:4}
.nc-selection-count{min-width:0;min-height:44px;display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono',monospace;font-size:11px;color:#00f0ff;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.nc-selection-btn{min-width:0;min-height:44px;padding:7px 4px;background:transparent;font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;line-height:1.1;white-space:normal;overflow:hidden;text-overflow:ellipsis;cursor:pointer;touch-action:manipulation}
.nc-selection-btn:disabled{opacity:.42;cursor:default;filter:saturate(.45)}
.nc-msg-row{touch-action:pan-y;-webkit-user-select:none;user-select:none;-webkit-tap-highlight-color:transparent}
@media(max-width:350px){.nc-selection-bar{gap:4px;padding-left:6px;padding-right:6px}.nc-selection-btn{font-size:8px;padding-left:2px;padding-right:2px}.nc-selection-count{font-size:10px}}''',
             'selection css')

# panel markup (supports both repository and APK variants)
new_panel = '''          <sc-if value="{{ postSelMode }}">
          <div class="nc-selection-bar">
            <span class="nc-selection-count" title="Выбрано сообщений">{{ selPostCount }} ✓</span>
            <button class="nc-selection-btn" disabled="{{ selActionPending }}" onclick="{{ fwdSelectedPosts }}" style="border:1px solid #3aff8f;color:#3aff8f">ПЕРЕСЛАТЬ</button>
            <button class="nc-selection-btn" disabled="{{ selActionPending }}" onclick="{{ copySelPosts }}" style="border:1px solid #00f0ff;color:#00f0ff">КОПИРОВАТЬ</button>
            <button class="nc-selection-btn" disabled="{{ pinSelDisabled }}" onclick="{{ pinSelPosts }}" style="border:1px solid #f6ff00;color:#f6ff00">{{ pinSelLabel }}</button>
            <button class="nc-selection-btn" disabled="{{ selActionPending }}" onclick="{{ deleteSelPosts }}" style="border:1px solid #ff003c;color:#ff003c">УДАЛИТЬ</button>
            <button class="nc-selection-btn" onclick="{{ clearPostSel }}" style="border:1px solid #8a8a96;color:#c8c8d2">✕ СНЯТЬ</button>
          </div>
          </sc-if>'''
panel_re = re.compile(r'          <sc-if value="\{\{ postSelMode \}\}">\n.*?          </sc-if>', re.S)
text, n = panel_re.subn(new_panel, text, count=1)
if n != 1:
    raise RuntimeError(f'panel: expected 1 occurrence, found {n}')

# row key/class and file click
replace_once('<div ref="{{ m.swipeRef }}" data-mid="{{ m.mid }}" onclick="{{ m.onRow }}" ondoubleclick="{{ m.onDbl }}" oncontextmenu="{{ m.onRowLong }}" style="{{ m.rowStyle }}">',
             '<div key="{{ m.mid }}" ref="{{ m.swipeRef }}" class="nc-msg-row" data-mid="{{ m.mid }}" onclick="{{ m.onRow }}" ondoubleclick="{{ m.onDbl }}" oncontextmenu="{{ m.onRowLong }}" style="{{ m.rowStyle }}">',
             'message key')
replace_once('<div style="display:flex;gap:11px;align-items:center;min-width:180px">\n                        <div style="width:38px;height:44px;',
             '<div onclick="{{ m.openFile }}" style="display:flex;gap:11px;align-items:center;min-width:180px;cursor:pointer">\n                        <div style="width:38px;height:44px;',
             'file click')

# composer bottom safe area
replace_once('<div style="flex:none;border-top:1px solid #1c1c26;background:#0c0c12;padding:10px 12px 14px">',
             '<div style="flex:none;border-top:1px solid #1c1c26;background:#0c0c12;padding:10px max(12px,env(safe-area-inset-right,0px)) calc(14px + env(safe-area-inset-bottom,0px)) max(12px,env(safe-area-inset-left,0px))">',
             'composer safe area')

# state fields
replace_once('    selPosts: [],\n    e2ePeers:',
             "    selPosts: [], selChatId: null, selActionPending: false, selActionToken: null,\n    e2ePeers:",
             'selection state')
replace_once("    fwdIds: null, fwdFrom: '',", "    fwdIds: null, fwdFrom: '', fwdSourceChatId: null,", 'forward source state')

# return boolean from backend send
text = text.replace('const sc = this._serverChatOf(uid); if (!sc) return;', 'const sc = this._serverChatOf(uid); if (!sc) return false;', 1)
text = text.replace("if ((msg.fileData || '').length > 720000) { this._toast('Файл больше 700 КБ — не отправлен'); return; }", "if ((msg.fileData || '').length > 720000) { this._toast('Файл больше 700 КБ — не отправлен'); return false; }", 1)
text = text.replace("if (total > 980000) { this._toast('Слишком большой файл (лимит ~1 МБ)'); return; }", "if (total > 980000) { this._toast('Слишком большой файл (лимит ~1 МБ)'); return false; }", 1)
replace_once("      if (msg.ghost && msg.ghostAt && msgId) {\n        const delay = Math.max(0, msg.ghostAt - Date.now()) + 400;\n        setTimeout(() => { try { NC.deleteMessage(chatId, msgId).catch(() => {}); } catch (e) {} }, delay);\n      }\n    } catch (e) {",
             "      if (msg.ghost && msg.ghostAt && msgId) {\n        const delay = Math.max(0, msg.ghostAt - Date.now()) + 400;\n        setTimeout(() => { try { NC.deleteMessage(chatId, msgId).catch(() => {}); } catch (e) {} }, delay);\n      }\n      return true;\n    } catch (e) {",
             'send success return')
replace_once("      this._toast(code.startsWith('E2E_') ? 'Отправка отменена: ключ шифрования недоступен' : 'Не удалось отправить');\n    }\n  };",
             "      this._toast(code.startsWith('E2E_') ? 'Отправка отменена: ключ шифрования недоступен' : 'Не удалось отправить');\n      return false;\n    }\n  };",
             'send failure return')

# quick reaction guard
replace_once("  quickReact = (mid) => { try { this.toggleReaction(mid, 'love'); this._vibrate && this._vibrate(15); } catch (e) {} };",
'''  quickReact = (mid, e) => {
    if (this._selectionActive()) { this._stopMessageEvent(e, true); return; }
    try { this.toggleReaction(mid, 'love'); this._vibrate && this._vibrate(15); } catch (x) {}
  };''', 'quick react')

# openChat clears selection atomically
old_return = "return { screen: 'chat', activeId: id, threads, contacts: s.contacts.map(c => c.id === id ? { ...c, unread: 0 } : c), replyTo: null, editing: null, emojiPanel: false, msgMenu: null, composerEmpty: !(this._pendingComposer), typing: null, typingName: '', inChatSearch: false, inChatQuery: '', drafts };"
new_return = "return { screen: 'chat', activeId: id, threads, contacts: s.contacts.map(c => c.id === id ? { ...c, unread: 0 } : c), replyTo: null, editing: null, emojiPanel: false, msgMenu: null, postFor: null, composerEmpty: !(this._pendingComposer), typing: null, typingName: '', inChatSearch: false, inChatQuery: '', drafts, selPosts: [], selChatId: null, selActionPending: false, selActionToken: null, fwdIds: null, fwdSourceChatId: null };"
replace_once(old_return, new_return, 'openChat return')
replace_once("    try { if (this._pendingComposer) this.setComposer(this._pendingComposer); else this.clearComposer(); } catch (e) {}\n    if (FIREBASE_ENABLED) this.openChatBackend(id);",
             "    this._selActionLock = null; this._forwardLock = null; this._cancelMessageGestures();\n    try { if (this._pendingComposer) this.setComposer(this._pendingComposer); else this.clearComposer(); } catch (e) {}\n    if (FIREBASE_ENABLED) this.openChatBackend(id);",
             'openChat cleanup')

# Replace post selection methods block
start = text.index('  // ---- действия над постом канала ----')
end = text.index('  askConfirm =', start)
new_methods = r'''  // ---- единая модель выделения сообщений ----
  _normMsgId = (mid) => String(mid == null ? '' : mid);
  _selectionActive = (st = this.state, chatId = st.activeId) => !!(chatId && st.selChatId === chatId && (st.selPosts || []).length > 0);
  _validSelectionIds = (st = this.state, chatId = st.activeId) => {
    if (!chatId || st.selChatId !== chatId) return [];
    const existing = new Set(((st.threads || {})[chatId] || []).map(m => this._normMsgId(m.id)));
    const out = [];
    for (const raw of (st.selPosts || [])) { const id = this._normMsgId(raw); if (id && existing.has(id) && !out.includes(id)) out.push(id); }
    return out;
  };
  _selectionSnapshot = () => {
    const st = this.state, chatId = st.activeId;
    const ids = this._validSelectionIds(st, chatId);
    if (!ids.length) return null;
    const wanted = new Set(ids);
    const messages = ((st.threads || {})[chatId] || []).filter(m => wanted.has(this._normMsgId(m.id)));
    return { chatId, ids, messages };
  };
  _stopMessageEvent = (e, prevent = false) => {
    try { if (prevent && e && e.preventDefault) e.preventDefault(); if (e && e.stopPropagation) e.stopPropagation(); } catch (x) {}
  };
  _messageInteraction = (mid, e, normalAction) => {
    if (Date.now() < (this._selectionSuppressClickUntil || 0)) { this._stopMessageEvent(e, true); return true; }
    if (this._selectionActive()) { this._stopMessageEvent(e, true); this.togglePostSel(mid); return true; }
    if (normalAction) normalAction();
    return false;
  };
  _cancelMessageGestures = () => {
    try {
      document.querySelectorAll('[data-mid]').forEach(el => {
        if (el.__cancelLongPress) el.__cancelLongPress();
        el.style.transition = ''; el.style.transform = '';
      });
      if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
    } catch (e) {}
  };
  _beginSelectionAction = (snap, kind) => {
    if (!snap || this._selActionLock || !this._selectionActive(this.state, snap.chatId)) return null;
    const current = this._validSelectionIds(this.state, snap.chatId);
    if (!snap.ids.length || snap.ids.some(id => !current.includes(id))) return null;
    const token = kind + ':' + Date.now() + ':' + Math.random();
    this._selActionLock = token;
    this.setState({ selActionPending: true, selActionToken: token });
    return token;
  };
  _finishSelectionAction = (token, clear = false) => {
    if (this._selActionLock === token) this._selActionLock = null;
    this.setState(st => {
      if (st.selActionToken !== token) return null;
      return clear
        ? { selPosts: [], selChatId: null, selActionPending: false, selActionToken: null, msgMenu: null, postFor: null }
        : { selActionPending: false, selActionToken: null };
    }, () => { if (clear) this._cancelMessageGestures(); });
  };
  openPostMenu = (mid) => { if (!this._selectionActive()) this.setState({ postFor: mid }); };
  togglePostSel = (mid) => {
    const k = this._normMsgId(mid); if (!k || this.state.selActionPending) return;
    this.setState(s => {
      const chatId = s.activeId; if (!chatId) return null;
      const cur = (s.selChatId === chatId ? (s.selPosts || []).map(this._normMsgId) : []);
      const next = cur.includes(k) ? cur.filter(x => x !== k) : [...cur, k];
      return { selPosts: next, selChatId: next.length ? chatId : null, msgMenu: null, postFor: null, reactFor: null, replyTo: null, editing: null, emojiPanel: false, attachOpen: false };
    }, () => { try { if (this._selectionActive()) { this._cancelMessageGestures(); this._vibrate && this._vibrate(12); } } catch (e) {} });
  };
  postTap = (mid, e) => {
    if (Date.now() < (this._selectionSuppressClickUntil || 0)) { this._stopMessageEvent(e, true); return; }
    if (this._selectionActive()) { this._stopMessageEvent(e, true); this.togglePostSel(mid); }
    else this.openPostMenu(mid);
  };
  postLong = (mid, e) => {
    this._stopMessageEvent(e, true);
    if (this.state.selActionPending) return;
    this._selectionSuppressClickUntil = Date.now() + 700;
    this.togglePostSel(mid);
  };
  clearPostSel = () => {
    this._selActionLock = null; this._selectionSuppressClickUntil = 0;
    this.setState({ selPosts: [], selChatId: null, selActionPending: false, selActionToken: null, fwdIds: null, fwdSourceChatId: null, msgMenu: null, postFor: null, reactFor: null }, this._cancelMessageGestures);
  };
  _deleteSelection = async (snap) => {
    const token = this._beginSelectionAction(snap, 'delete'); if (!token) return;
    let okIds = snap.ids.slice(), failedIds = [];
    if (this._isServerChat(snap.chatId)) {
      const sc = this._serverChatOf(snap.chatId);
      if (!sc) { failedIds = okIds; okIds = []; }
      else {
        const results = await Promise.allSettled(okIds.map(mid => NC.deleteMessage(sc.chatId, mid)));
        failedIds = okIds.filter((_, i) => results[i].status !== 'fulfilled');
        okIds = okIds.filter((_, i) => results[i].status === 'fulfilled');
      }
    }
    const okSet = new Set(okIds);
    this.setState(st => {
      const currentAction = st.selActionToken === token && st.selChatId === snap.chatId;
      const remaining = currentAction ? (st.selPosts || []).map(this._normMsgId).filter(id => !okSet.has(id)) : (st.selPosts || []);
      return {
        threads: { ...st.threads, [snap.chatId]: ((st.threads || {})[snap.chatId] || []).filter(m => !okSet.has(this._normMsgId(m.id))) },
        contacts: st.contacts.map(c => (c.id === snap.chatId && okSet.has(this._normMsgId(c.pinnedId))) ? { ...c, pinnedId: null } : c),
        selPosts: remaining, selChatId: currentAction && remaining.length ? snap.chatId : (currentAction ? null : st.selChatId),
        selActionPending: currentAction ? false : st.selActionPending, selActionToken: currentAction ? null : st.selActionToken
      };
    }, () => {
      if (this._selActionLock === token) this._selActionLock = null;
      if (failedIds.length) this._toast('Не удалено: ' + failedIds.length + '. Проверь соединение.');
      else this._toast('Удалено: ' + okIds.length);
      if (!failedIds.length) this._cancelMessageGestures();
    });
  };
  deleteSelPosts = () => {
    const snap = this._selectionSnapshot(); if (!snap || this.state.selActionPending) return;
    this.askConfirm('Удалить выбранные (' + snap.ids.length + ')?', () => this._deleteSelection(snap));
  };
'''
text = text[:start] + new_methods + text[end:]


out.write_text(text, encoding="utf-8")
print(f"selection patch stage complete: {out} ({len(text)} chars)")
