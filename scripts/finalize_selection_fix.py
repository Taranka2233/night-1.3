from pathlib import Path
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('src')
parser.add_argument('out')
args = parser.parse_args()
src = Path(args.src)
out = Path(args.out)
text = src.read_text(encoding='utf-8')

def replace_once(old, new, label):
    global text
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f'{label}: expected 1 occurrence, found {n}')
    text = text.replace(old, new, 1)

# Capability-aware disabled state for every selection action.
replace_once(
'''            <button class="nc-selection-btn" disabled="{{ selActionPending }}" onclick="{{ fwdSelectedPosts }}" style="border:1px solid #3aff8f;color:#3aff8f">ПЕРЕСЛАТЬ</button>
            <button class="nc-selection-btn" disabled="{{ selActionPending }}" onclick="{{ copySelPosts }}" style="border:1px solid #00f0ff;color:#00f0ff">КОПИРОВАТЬ</button>
            <button class="nc-selection-btn" disabled="{{ pinSelDisabled }}" onclick="{{ pinSelPosts }}" style="border:1px solid #f6ff00;color:#f6ff00">{{ pinSelLabel }}</button>
            <button class="nc-selection-btn" disabled="{{ selActionPending }}" onclick="{{ deleteSelPosts }}" style="border:1px solid #ff003c;color:#ff003c">УДАЛИТЬ</button>''',
'''            <button class="nc-selection-btn" disabled="{{ forwardSelDisabled }}" onclick="{{ fwdSelectedPosts }}" style="border:1px solid #3aff8f;color:#3aff8f">ПЕРЕСЛАТЬ</button>
            <button class="nc-selection-btn" disabled="{{ copySelDisabled }}" onclick="{{ copySelPosts }}" style="border:1px solid #00f0ff;color:#00f0ff">КОПИРОВАТЬ</button>
            <button class="nc-selection-btn" disabled="{{ pinSelDisabled }}" onclick="{{ pinSelPosts }}" style="border:1px solid #f6ff00;color:#f6ff00">{{ pinSelLabel }}</button>
            <button class="nc-selection-btn" disabled="{{ deleteSelDisabled }}" onclick="{{ deleteSelPosts }}" style="border:1px solid #ff003c;color:#ff003c">УДАЛИТЬ</button>''',
'panel capabilities')

# New messages must not yank the scroll position while the user is selecting older messages.
replace_once(
"    if (this.state.screen === 'chat' && (id !== this._lastActiveId || count > (this._lastMsgCount || 0))) { this.scrollBottom(); }",
"    if (this.state.screen === 'chat' && !this._selectionActive() && (id !== this._lastActiveId || count > (this._lastMsgCount || 0))) { this.scrollBottom(); }",
'no autoscroll during selection')

# Use only currently existing IDs to decide if selection mode is active.
replace_once(
"  _selectionActive = (st = this.state, chatId = st.activeId) => !!(chatId && st.selChatId === chatId && (st.selPosts || []).length > 0);",
"  _selectionActive = (st = this.state, chatId = st.activeId) => !!(chatId && st.selChatId === chatId && this._validSelectionIds(st, chatId).length > 0);",
'valid selection active')

# Nested message actions must always stop bubbling to the bubble/row. In selection mode they also prevent default navigation/media behavior.
replace_once(
'''  _messageInteraction = (mid, e, normalAction) => {
    if (Date.now() < (this._selectionSuppressClickUntil || 0)) { this._stopMessageEvent(e, true); return true; }
    if (this._selectionActive()) { this._stopMessageEvent(e, true); this.togglePostSel(mid); return true; }
    if (normalAction) normalAction();
    return false;
  };''',
'''  _messageInteraction = (mid, e, normalAction) => {
    if (Date.now() < (this._selectionSuppressClickUntil || 0)) { this._stopMessageEvent(e, true); return true; }
    if (this._selectionActive()) { this._stopMessageEvent(e, true); this.togglePostSel(mid); return true; }
    this._stopMessageEvent(e, false);
    if (normalAction) normalAction();
    return false;
  };''',
'nested event propagation')

# Add capability model for system and still-locked E2E messages.
insert_after = '''  _selectionSnapshot = () => {
    const st = this.state, chatId = st.activeId;
    const ids = this._validSelectionIds(st, chatId);
    if (!ids.length) return null;
    const wanted = new Set(ids);
    const messages = ((st.threads || {})[chatId] || []).filter(m => wanted.has(this._normMsgId(m.id)));
    return { chatId, ids, messages };
  };
'''
cap_block = '''  _isSystemMessage = (m) => {
    if (!m) return false;
    const id = this._normMsgId(m.id).toLowerCase();
    const t = String(m.text || '').trim();
    return id.startsWith('sys') || /^\/\/\s*(система|банда)/i.test(t);
  };
  _isLockedE2EMessage = (m) => !!(m && m._e2e && (!String(m.text || '').trim() || /^🔒/.test(String(m.text || '').trim())));
  _messageCapabilities = (m) => {
    const system = this._isSystemMessage(m), locked = this._isLockedE2EMessage(m);
    return { copy: true, forward: !system && !locked, pin: !system, delete: !system };
  };
  _selectionCapabilities = (snap) => {
    if (!snap || !snap.messages.length) return { copy: false, forward: false, pin: false, delete: false };
    const caps = snap.messages.map(this._messageCapabilities);
    return {
      copy: caps.every(c => c.copy),
      forward: caps.every(c => c.forward),
      pin: snap.messages.length === 1 && caps[0].pin,
      delete: caps.every(c => c.delete)
    };
  };
'''
if text.count(insert_after) != 1:
    raise RuntimeError('capability insertion point missing')
text = text.replace(insert_after, insert_after + cap_block, 1)

# Close all mutually exclusive chat interaction modes when selection starts, including active search and voice recording.
replace_once(
'''  togglePostSel = (mid) => {
    const k = this._normMsgId(mid); if (!k || this.state.selActionPending) return;
    this.setState(s => {
      const chatId = s.activeId; if (!chatId) return null;
      const cur = (s.selChatId === chatId ? (s.selPosts || []).map(this._normMsgId) : []);
      const next = cur.includes(k) ? cur.filter(x => x !== k) : [...cur, k];
      return { selPosts: next, selChatId: next.length ? chatId : null, msgMenu: null, postFor: null, reactFor: null, replyTo: null, editing: null, emojiPanel: false, attachOpen: false };
    }, () => { try { if (this._selectionActive()) { this._cancelMessageGestures(); this._vibrate && this._vibrate(12); } } catch (e) {} });
  };''',
'''  togglePostSel = (mid) => {
    const k = this._normMsgId(mid); if (!k || this.state.selActionPending) return;
    const starting = !this._selectionActive();
    if (starting && this.state.recording) { try { this.cancelRec(); } catch (e) {} }
    this.setState(s => {
      const chatId = s.activeId; if (!chatId) return null;
      const cur = (s.selChatId === chatId ? (s.selPosts || []).map(this._normMsgId) : []);
      const next = cur.includes(k) ? cur.filter(x => x !== k) : [...cur, k];
      return { selPosts: next, selChatId: next.length ? chatId : null, msgMenu: null, postFor: null, reactFor: null, replyTo: null, editing: null, emojiPanel: false, attachOpen: false, inChatSearch: false, inChatQuery: '', chatMenu: false, profileOpen: false, commentsFor: null, iceUnlockFor: null };
    }, () => { try { if (this._selectionActive()) { this._cancelMessageGestures(); this._vibrate && this._vibrate(12); } } catch (e) {} });
  };''',
'toggle closes conflicting UI')

# Avoid Android WebView double-toggle when both our timer and contextmenu fire for one long press.
replace_once(
'''  postLong = (mid, e) => {
    this._stopMessageEvent(e, true);
    if (this.state.selActionPending) return;
    this._selectionSuppressClickUntil = Date.now() + 700;
    this.togglePostSel(mid);
  };''',
'''  postLong = (mid, e) => {
    this._stopMessageEvent(e, true);
    if (this.state.selActionPending) return;
    if (Date.now() < (this._selectionSuppressClickUntil || 0)) return;
    this._selectionSuppressClickUntil = Date.now() + 700;
    this.togglePostSel(mid);
  };''',
'long press duplicate guard')

# Clear every operation lock when selection is explicitly cancelled/lifecycle-cleared.
replace_once(
"    this._selActionLock = null; this._selectionSuppressClickUntil = 0;",
"    this._selActionLock = null; this._forwardLock = null; this._selectionSuppressClickUntil = 0;",
'clear locks')

# Re-check delete capability at execution time.
replace_once(
'''  deleteSelPosts = () => {
    const snap = this._selectionSnapshot(); if (!snap || this.state.selActionPending) return;
    this.askConfirm('Удалить выбранные (' + snap.ids.length + ')?', () => this._deleteSelection(snap));
  };''',
'''  deleteSelPosts = () => {
    const snap = this._selectionSnapshot(); if (!snap || this.state.selActionPending) return;
    if (!this._selectionCapabilities(snap).delete) { this._toast('Системные сообщения удалить нельзя'); return; }
    this.askConfirm('Удалить выбранные (' + snap.ids.length + ')?', () => this._deleteSelection(snap));
  };''',
'delete capability guard')

# Replace forwarding with partial-success-safe behavior. Successful messages are removed from selection; failures remain selected and are not duplicated on retry.
fstart = text.index('  forwardTo = async (targetId) => {')
fend = text.index('  fwdSinglePost =', fstart)
new_forward = '''  forwardTo = async (targetId) => {
    if (this._forwardLock || this.state.selActionPending) return;
    const s = this.state, srcId = s.fwdSourceChatId || s.activeId;
    const ids = [...new Set((s.fwdIds || []).map(this._normMsgId))];
    const wanted = new Set(ids), src = (s.threads || {})[srcId] || [];
    const picked = src.filter(m => wanted.has(this._normMsgId(m.id)));
    if (!picked.length) { this.setState({ fwdIds: null, fwdSourceChatId: null }); this._toast('Выбранные сообщения больше недоступны'); return; }
    const blocked = picked.filter(m => !this._messageCapabilities(m).forward);
    if (blocked.length) { this._toast('Системные или нерасшифрованные сообщения нельзя переслать'); return; }
    const token = 'forward:' + Date.now() + ':' + Math.random(); this._forwardLock = token;
    const selectedNow = this._validSelectionIds(s, srcId);
    const selectionOwned = s.selChatId === srcId && selectedNow.length === ids.length && ids.every(id => selectedNow.includes(id));
    this.setState({ selActionPending: selectionOwned, selActionToken: selectionOwned ? token : s.selActionToken });
    const from = s.fwdFrom || (s.contacts.find(c => c.id === srcId) || {}).name || 'ЧАТ';
    const now = this.now(); let okIds = [], failedIds = [];
    try {
      if (this._isServerChat(targetId)) {
        const results = await Promise.all(picked.map(m => this._sendMediaBackend(targetId, { ...m, fwdFrom: m.fwdFrom || from })));
        picked.forEach((m, i) => (results[i] ? okIds : failedIds).push(this._normMsgId(m.id)));
      } else {
        const copies = picked.map((m, k) => ({ ...m, id: Date.now() + Math.random() + k, from: 'me', time: now, status: 'sent', reactions: [], mine: [], views: undefined, comments: undefined, fwdFrom: m.fwdFrom || from }));
        await new Promise(resolve => this.setState(st => ({ threads: { ...st.threads, [targetId]: [...((st.threads || {})[targetId] || []), ...copies] }, contacts: st.contacts.map(c => c.id === targetId ? { ...c, last: 'переслано: ' + this._messageCopyText(picked[0]).slice(0, 24), time: now } : c) }), resolve));
        okIds = picked.map(m => this._normMsgId(m.id));
      }
    } catch (e) { failedIds = picked.map(m => this._normMsgId(m.id)); okIds = []; }
    if (this._forwardLock !== token) return;
    this._forwardLock = null;
    const okSet = new Set(okIds), failedSet = new Set(failedIds);
    if (failedIds.length) {
      this.setState(st => {
        const currentAction = st.selActionToken === token;
        const remainingSelected = selectionOwned && st.selChatId === srcId ? (st.selPosts || []).map(this._normMsgId).filter(id => !okSet.has(id)) : st.selPosts;
        return {
          fwdIds: failedIds, fwdSourceChatId: srcId,
          selPosts: remainingSelected,
          selChatId: selectionOwned ? (remainingSelected.length ? srcId : null) : st.selChatId,
          selActionPending: currentAction ? false : st.selActionPending,
          selActionToken: currentAction ? null : st.selActionToken
        };
      });
      this._toast((okIds.length ? ('Переслано: ' + okIds.length + '. ') : '') + 'Не отправлено: ' + failedSet.size);
      return;
    }
    this.setState(st => ({
      fwdIds: null, fwdSourceChatId: null,
      selPosts: selectionOwned && st.selChatId === srcId ? [] : st.selPosts,
      selChatId: selectionOwned && st.selChatId === srcId ? null : st.selChatId,
      selActionPending: st.selActionToken === token ? false : st.selActionPending,
      selActionToken: st.selActionToken === token ? null : st.selActionToken
    }), () => this.openChat(targetId));
  };
'''
text = text[:fstart] + new_forward + text[fend:]

# Forward and copy actions also re-check capabilities.
replace_once(
"  fwdSelectedPosts = () => { const snap = this._selectionSnapshot(); if (!snap || this.state.selActionPending) return; const g = this.state.contacts.find(c => c.id === snap.chatId); this.openForward(snap.ids, g ? g.name : '', snap.chatId); };",
"  fwdSelectedPosts = () => { const snap = this._selectionSnapshot(); if (!snap || this.state.selActionPending) return; if (!this._selectionCapabilities(snap).forward) { this._toast('Системные или нерасшифрованные сообщения нельзя переслать'); return; } const g = this.state.contacts.find(c => c.id === snap.chatId); this.openForward(snap.ids, g ? g.name : '', snap.chatId); };",
'forward capability guard')
replace_once(
'''  copySelPosts = async () => {
    const snap = this._selectionSnapshot(); const token = this._beginSelectionAction(snap, 'copy'); if (!token) return;''',
'''  copySelPosts = async () => {
    const snap = this._selectionSnapshot(); if (!snap || !this._selectionCapabilities(snap).copy) return;
    const token = this._beginSelectionAction(snap, 'copy'); if (!token) return;''',
'copy capability guard')
replace_once(
'''    if (!snap || snap.ids.length !== 1 || this.state.selActionPending) { this._toast('Для закрепления выбери одно сообщение'); return; }
    const token = this._beginSelectionAction(snap, 'pin'); if (!token) return;''',
'''    if (!snap || snap.ids.length !== 1 || this.state.selActionPending) { this._toast('Для закрепления выбери одно сообщение'); return; }
    if (!this._selectionCapabilities(snap).pin) { this._toast('Системное сообщение закрепить нельзя'); return; }
    const token = this._beginSelectionAction(snap, 'pin'); if (!token) return;''',
'pin capability guard')

# Search/settings/group-call direct handlers must also be inert in selection mode, not only visually hidden.
replace_once(
"  toggleChatSearch = () => this.setState(s => ({ inChatSearch: !s.inChatSearch, inChatQuery: '' }));",
"  toggleChatSearch = () => { if (this._selectionActive()) return; this.setState(s => ({ inChatSearch: !s.inChatSearch, inChatQuery: '' })); };",
'search guard')
replace_once(
"  openGroupSettings = () => {\n    const g = this.state.contacts.find(c => c.id === this.state.activeId);",
"  openGroupSettings = () => {\n    if (this._selectionActive()) return;\n    const g = this.state.contacts.find(c => c.id === this.state.activeId);",
'group settings guard')
replace_once(
"  openChannelSettings = () => {\n    const ch = this.state.contacts.find(c => c.id === this.state.activeId);",
"  openChannelSettings = () => {\n    if (this._selectionActive()) return;\n    const ch = this.state.contacts.find(c => c.id === this.state.activeId);",
'channel settings guard')
replace_once(
"  openChatMenu = () => this.setState({ chatMenu: true });",
"  openChatMenu = () => { if (!this._selectionActive()) this.setState({ chatMenu: true }); };",
'chat menu guard')
replace_once(
"  startGroupCall = async (kind) => {",
"  startGroupCall = async (kind) => { if (this._selectionActive()) return;",
'group call guard')

# Native video controls swallow the outer click. In selection mode they must toggle the message instead.
replace_once(
"        vidStop: (e) => { try { if (e && e.stopPropagation) e.stopPropagation(); } catch (x) {} },",
"        vidStop: (e) => { if (this._selectionActive()) this._messageInteraction(m.id, e); else this._stopMessageEvent(e, false); },",
'video control selection')

# Expose aggregate capabilities to the template.
replace_once(
'''      selActionPending: !!s.selActionPending,
      pinSelDisabled: !!s.selActionPending || selectedMessageIds.length !== 1,
      pinSelLabel: selectedMessageIds.length === 1 && this._normMsgId(active && active.pinnedId) === selectedMessageIds[0] ? 'ОТКРЕПИТЬ' : 'ЗАКРЕПИТЬ',''',
'''      selActionPending: !!s.selActionPending,
      forwardSelDisabled: !!s.selActionPending || !this._selectionCapabilities(this._selectionSnapshot()).forward,
      copySelDisabled: !!s.selActionPending || !this._selectionCapabilities(this._selectionSnapshot()).copy,
      pinSelDisabled: !!s.selActionPending || !this._selectionCapabilities(this._selectionSnapshot()).pin,
      deleteSelDisabled: !!s.selActionPending || !this._selectionCapabilities(this._selectionSnapshot()).delete,
      pinSelLabel: selectedMessageIds.length === 1 && this._normMsgId(active && active.pinnedId) === selectedMessageIds[0] ? 'ОТКРЕПИТЬ' : 'ЗАКРЕПИТЬ',''',
'template capability state')

# Mark final build source clearly.
text = text.replace('<!-- NC_SELECTION_AUDIT_FIX_2026_07_14 -->', '<!-- NC_SELECTION_AUDIT_FIX_FINAL_2026_07_14 -->', 1)
out.write_text(text, encoding='utf-8')
print(out, len(text))
