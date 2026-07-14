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

# confirmation double-tap guard
replace_once("  confirmYes = () => { const c = this.state.confirmBox; this.setState({ confirmBox: null }); if (c && c.onYes) c.onYes(); };",
'''  confirmYes = () => {
    if (this._confirmLock) return;
    const c = this.state.confirmBox; if (!c) return;
    this._confirmLock = true; this.setState({ confirmBox: null }, () => { this._confirmLock = false; if (c.onYes) c.onYes(); });
  };''', 'confirm yes')
_confirm_no_variants = [
  "  confirmNo = () => { const c = this.state.confirmBox; this.setState({ confirmBox: null }); if (c && c.onNo) c.onNo(); };",
  "  confirmNo = () => this.setState({ confirmBox: null });"
]
_found = [v for v in _confirm_no_variants if v in text]
if len(_found) != 1: raise RuntimeError(f'confirm no: expected one supported variant, found {len(_found)}')
text = text.replace(_found[0], "  confirmNo = () => { const c = this.state.confirmBox; this._confirmLock = false; this.setState({ confirmBox: null }); if (c && c.onNo) c.onNo(); };", 1)

# Replace forward + selected actions block
fstart = text.index('  openForward =')
fend = text.index('  closePostMenu =', fstart)
new_forward = r'''  openForward = (ids, fromName, sourceChatId) => {
    const src = sourceChatId || this.state.activeId;
    const clean = [...new Set((ids || []).map(this._normMsgId).filter(Boolean))];
    if (!clean.length) return;
    this.setState({ fwdIds: clean, fwdFrom: fromName || '', fwdSourceChatId: src, postFor: null });
  };
  closeForward = () => { if (!this.state.selActionPending) this.setState({ fwdIds: null, fwdSourceChatId: null }); };
  forwardTo = async (targetId) => {
    if (this._forwardLock || this.state.selActionPending) return;
    const s = this.state, srcId = s.fwdSourceChatId || s.activeId;
    const ids = [...new Set((s.fwdIds || []).map(this._normMsgId))];
    const wanted = new Set(ids), src = (s.threads || {})[srcId] || [];
    const picked = src.filter(m => wanted.has(this._normMsgId(m.id)));
    if (!picked.length) { this.setState({ fwdIds: null, fwdSourceChatId: null }); this._toast('Выбранные сообщения больше недоступны'); return; }
    const token = 'forward:' + Date.now() + ':' + Math.random(); this._forwardLock = token;
    const selectionOwned = s.selChatId === srcId && ids.every(id => (s.selPosts || []).map(this._normMsgId).includes(id));
    this.setState({ selActionPending: selectionOwned, selActionToken: selectionOwned ? token : s.selActionToken });
    const from = s.fwdFrom || (s.contacts.find(c => c.id === srcId) || {}).name || 'ЧАТ';
    const now = this.now(); let success = true;
    try {
      if (this._isServerChat(targetId)) {
        const results = await Promise.all(picked.map(m => this._sendMediaBackend(targetId, { ...m, fwdFrom: m.fwdFrom || from })));
        success = results.every(Boolean);
      } else {
        const copies = picked.map((m, k) => ({ ...m, id: Date.now() + Math.random() + k, from: 'me', time: now, status: 'sent', reactions: [], mine: [], views: undefined, comments: undefined, fwdFrom: m.fwdFrom || from }));
        await new Promise(resolve => this.setState(st => ({ threads: { ...st.threads, [targetId]: [...((st.threads || {})[targetId] || []), ...copies] }, contacts: st.contacts.map(c => c.id === targetId ? { ...c, last: 'переслано: ' + this._messageCopyText(picked[0]).slice(0, 24), time: now } : c) }), resolve));
      }
    } catch (e) { success = false; }
    if (this._forwardLock !== token) return;
    this._forwardLock = null;
    if (!success) {
      this.setState(st => ({ selActionPending: st.selActionToken === token ? false : st.selActionPending, selActionToken: st.selActionToken === token ? null : st.selActionToken }));
      this._toast('Пересылка не завершена. Проверь соединение.'); return;
    }
    this.setState(st => ({
      fwdIds: null, fwdSourceChatId: null,
      selPosts: selectionOwned && st.selChatId === srcId ? [] : st.selPosts,
      selChatId: selectionOwned && st.selChatId === srcId ? null : st.selChatId,
      selActionPending: st.selActionToken === token ? false : st.selActionPending,
      selActionToken: st.selActionToken === token ? null : st.selActionToken
    }), () => this.openChat(targetId));
  };
  fwdSinglePost = () => { const mid = this.state.postFor; const g = this.state.contacts.find(c => c.id === this.state.activeId); this.openForward([mid], g ? g.name : '', this.state.activeId); };
  fwdSelectedPosts = () => { const snap = this._selectionSnapshot(); if (!snap || this.state.selActionPending) return; const g = this.state.contacts.find(c => c.id === snap.chatId); this.openForward(snap.ids, g ? g.name : '', snap.chatId); };
  _messageCopyText = (m) => {
    if (!m) return '';
    const t = String(m.text || '').trim();
    if (t && t !== '🔒' && t !== '🔒 …') return t;
    if (m.caption) return String(m.caption);
    if (m.type === 'image' || m.imgSrc) return '[Фото]';
    if (m.type === 'video' || m.vidSrc) return '[Видео]';
    if (m.type === 'voice' || m.audioSrc) return '[Голосовое' + (m.duration ? ' · ' + m.duration : '') + ']';
    if (m.type === 'file' || m.fileData) return '[Файл' + (m.fileName ? ': ' + m.fileName : '') + ']';
    if (m.type === 'sticker') return '[Стикер' + (m.emojiId ? ': ' + m.emojiId : '') + ']';
    if (m.type === 'call') return '[Звонок]';
    if (m._e2e) return '[Зашифрованное сообщение]';
    return '[Сообщение]';
  };
  _copyTextToClipboard = async (value) => {
    if (navigator.clipboard && navigator.clipboard.writeText) { await navigator.clipboard.writeText(value); return true; }
    const ta = document.createElement('textarea'); ta.value = value; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta); ta.select();
    const ok = !!document.execCommand && document.execCommand('copy'); ta.remove(); if (!ok) throw new Error('COPY_FAILED'); return true;
  };
  copySelPosts = async () => {
    const snap = this._selectionSnapshot(); const token = this._beginSelectionAction(snap, 'copy'); if (!token) return;
    const txt = snap.messages.map(this._messageCopyText).filter(Boolean).join('\n\n');
    if (!txt) { this._finishSelectionAction(token, false); this._toast('Нет доступного содержимого для копирования'); return; }
    try { await this._copyTextToClipboard(txt); this._finishSelectionAction(token, true); this._toast('Скопировано: ' + snap.ids.length); }
    catch (e) { this._finishSelectionAction(token, false); this._toast('Не удалось скопировать'); }
  };
  pinSelPosts = async () => {
    const snap = this._selectionSnapshot();
    if (!snap || snap.ids.length !== 1 || this.state.selActionPending) { this._toast('Для закрепления выбери одно сообщение'); return; }
    const token = this._beginSelectionAction(snap, 'pin'); if (!token) return;
    const id = snap.ids[0], c = this.state.contacts.find(x => x.id === snap.chatId) || {};
    const nextPinned = this._normMsgId(c.pinnedId) === id ? null : id;
    let ok = true;
    if (this._isServerChat(snap.chatId)) {
      try { const sc = this._serverChatOf(snap.chatId); if (!sc) ok = false; else await NC.updateChatMeta(sc.chatId, { pinnedId: nextPinned || '' }); }
      catch (e) { ok = false; }
    }
    if (!ok) { this._finishSelectionAction(token, false); this._toast('Не удалось изменить закрепление'); return; }
    this.setState(st => ({ contacts: st.contacts.map(x => x.id === snap.chatId ? { ...x, pinnedId: nextPinned } : x) }), () => { this._finishSelectionAction(token, true); this._toast(nextPinned ? 'Сообщение закреплено' : 'Сообщение откреплено'); });
  };
'''
text = text[:fstart] + new_forward + text[fend:]


out.write_text(text, encoding="utf-8")
print(f"selection patch stage complete: {out} ({len(text)} chars)")
