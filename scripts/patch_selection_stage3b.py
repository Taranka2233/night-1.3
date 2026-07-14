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

# render selection locals
replace_once("    const rawMsgsAll = s.threads[s.activeId] || [];\n    const rawMsgs = _icq ? rawMsgsAll.filter(m => (m.text || '').toLowerCase().includes(_icq)) : rawMsgsAll;",
'''    const rawMsgsAll = s.threads[s.activeId] || [];
    const selectedMessageIds = this._validSelectionIds(s, s.activeId);
    const selectedMessageSet = new Set(selectedMessageIds);
    const selectionActive = selectedMessageIds.length > 0;
    const rawMsgs = _icq ? rawMsgsAll.filter(m => (m.text || '').toLowerCase().includes(_icq)) : rawMsgsAll;''', 'render selection locals')
replace_once("      const _selP = s.selPosts.map(String).includes(String(m.id));", "      const _selP = selectedMessageSet.has(this._normMsgId(m.id));", 'selected row local')

# row style + handlers/actions in message mapping
old_rowstyle = "        rowStyle: (active && active.isChannel && isMe) ? `display:flex;gap:8px;margin-bottom:14px;align-items:flex-start;cursor:pointer;padding:2px 0` : `display:flex;gap:8px;margin-bottom:14px;align-items:flex-end;flex-direction:${isMe ? 'row-reverse' : 'row'};animation:cpIn .2s ease`,"
new_rowstyle = "        rowStyle: ((active && active.isChannel && isMe) ? `display:flex;gap:8px;margin-bottom:14px;align-items:flex-start;cursor:pointer;padding:5px 4px` : `display:flex;gap:8px;margin-bottom:14px;align-items:flex-end;flex-direction:${isMe ? 'row-reverse' : 'row'};animation:cpIn .2s ease;padding:5px 4px`) + (_selP ? ';background:rgba(0,240,255,.09);outline:1px solid #00f0ff;box-shadow:0 0 14px rgba(0,240,255,.22);border-radius:6px' : ''),"
replace_once(old_rowstyle, new_rowstyle, 'row style')
replace_once("        onDbl: () => this.quickReact(m.id),\n        onRow: (active && active.isChannel && isMe) ? (() => this.postTap(m.id)) : (() => { if (this.state.selPosts.length > 0) this.togglePostSel(m.id); }),\n        onRowLong: (active && active.isChannel && isMe) ? ((e) => this.postLong(m.id, e)) : (() => {}),",
'''        onDbl: (e) => this.quickReact(m.id, e),
        onRow: (e) => { if (active && active.isChannel && isMe) this.postTap(m.id, e); else if (this._selectionActive()) { this._stopMessageEvent(e, true); this.togglePostSel(m.id); } },
        onRowLong: (e) => this.postLong(m.id, e),''', 'row handlers')
replace_once("        avatarTap: this.tapAvatar,", "        avatarTap: (e) => this._messageInteraction(m.id, e, () => this.tapAvatar(e)),", 'avatar guard')
replace_once("        jumpToReply: (e) => { try { if (e && e.stopPropagation) e.stopPropagation(); } catch (x) {} this.jumpToMsg(m.replyTo); },",
             "        jumpToReply: (e) => this._messageInteraction(m.id, e, () => this.jumpToMsg(m.replyTo)),", 'reply guard')
replace_once("        openImg: (e) => { if (this.state.selPosts.length > 0) { try { if (e && e.stopPropagation) e.stopPropagation(); } catch (x) {} this.togglePostSel(m.id); } else { this.openViewer('image', m.imgSrc, e); } },\n        openVid: (e) => { if (this.state.selPosts.length > 0) { try { if (e && e.stopPropagation) e.stopPropagation(); } catch (x) {} this.togglePostSel(m.id); } else { this.openViewer('video', m.vidSrc, e); } },",
'''        openImg: (e) => this._messageInteraction(m.id, e, () => this.openViewer('image', m.imgSrc, e)),
        openVid: (e) => this._messageInteraction(m.id, e, () => this.openViewer('video', m.vidSrc, e)),
        openFile: (e) => this._messageInteraction(m.id, e, () => this.saveMedia(m.fileData, m.fileName || 'file.dat', e)),''', 'media guards')
replace_once("        cycleSpeed: (e) => this.cycleSpeed(e),", "        cycleSpeed: (e) => this._messageInteraction(m.id, e, () => this.cycleSpeed(e)),", 'speed guard')
replace_once("        playVoice: (e) => this.playVoice(m.audioSrc, e, m.duration),", "        playVoice: (e) => this._messageInteraction(m.id, e, () => this.playVoice(m.audioSrc, e, m.duration)),", 'voice guard')
replace_once("pillStyle: 'display:inline-flex;align-items:center;justify-content:center;gap:4px;height:24px;padding:0 8px 0 6px;line-height:1;cursor:pointer;background:' + (isMine ? 'rgba(var(--nc-accent-rgb),.16)' : '#0c0c12') + ';border:1px solid ' + (isMine ? 'var(--nc-accent)' : 'rgba(var(--nc-accent-rgb),.35)') + ';box-shadow:' + (isMine ? '0 0 8px rgba(var(--nc-accent-rgb),.3)' : 'none'), tap: (e) => { try { if (e && e.stopPropagation) e.stopPropagation(); } catch (x) {} this.toggleReaction(m.id, r); }",
             "pillStyle: 'display:inline-flex;align-items:center;justify-content:center;gap:4px;height:24px;padding:0 8px 0 6px;line-height:1;cursor:pointer;background:' + (isMine ? 'rgba(var(--nc-accent-rgb),.16)' : '#0c0c12') + ';border:1px solid ' + (isMine ? 'var(--nc-accent)' : 'rgba(var(--nc-accent-rgb),.35)') + ';box-shadow:' + (isMine ? '0 0 8px rgba(var(--nc-accent-rgb),.3)' : 'none'), tap: (e) => this._messageInteraction(m.id, e, () => this.toggleReaction(m.id, r))",
             'reaction guard')
replace_once("        iceUnlock: (e) => { try { if (e && e.stopPropagation) e.stopPropagation(); } catch (x) {} this.openIceUnlock(m.id); },",
             "        iceUnlock: (e) => this._messageInteraction(m.id, e, () => this.openIceUnlock(m.id)),", 'ice guard')
replace_once("        callBack: (e) => { try { if (e && e.stopPropagation) e.stopPropagation(); } catch (x) {} if (this.state.selPosts.length > 0) { this.togglePostSel(m.id); } else { this.goCall(m.callKind || 'audio'); } },",
             "        callBack: (e) => this._messageInteraction(m.id, e, () => this.goCall(m.callKind || 'audio')),", 'call guard')
_sel_prop_variants = [
  "        isPostSelected: s.selPosts.map(String).includes(String(m.id)),",
  "        isPostSelected: s.selPosts.includes(m.id),"
]
_found = [v for v in _sel_prop_variants if v in text]
if len(_found) != 1: raise RuntimeError(f'selected prop: expected one supported variant, found {len(_found)}')
text = text.replace(_found[0], "        isPostSelected: _selP,", 1)
replace_once("        openComments: (e) => { try { if (e && e.stopPropagation) e.stopPropagation(); } catch (x) {} if (this.state.selPosts.length > 0) { this.togglePostSel(m.id); } else { this.openComments(m.id); } },",
             "        openComments: (e) => this._messageInteraction(m.id, e, () => this.openComments(m.id)),", 'comments guard')
replace_once("        onReact: (active && active.isChannel && isMe) ? (() => {}) : ((e) => { try { if (e && e.stopPropagation) e.stopPropagation(); } catch (x) {} if (this.state.selPosts.length > 0) this.togglePostSel(m.id); else this.openMsgMenu(m.id); }),\n        onLong: (active && active.isChannel && isMe) ? (() => {}) : ((e) => { try { if (e && e.preventDefault) e.preventDefault(); if (e && e.stopPropagation) e.stopPropagation(); } catch (x) {} this.togglePostSel(m.id); }),",
'''        onReact: (active && active.isChannel && isMe) ? ((e) => this._messageInteraction(m.id, e, () => this.openPostMenu(m.id))) : ((e) => this._messageInteraction(m.id, e, () => this.openMsgMenu(m.id))),
        onLong: (e) => this.postLong(m.id, e),''', 'bubble handlers')

# render values selection mode and action bindings
replace_once("      composerShow: !(active && active.blockedByMe),", "      composerShow: !selectionActive && !(active && active.blockedByMe),", 'composer selection hide')
replace_once("      postSelMode: (s.selPosts || []).filter(pid => (s.threads[s.activeId] || []).some(mm => String(mm.id) === String(pid))).length > 0, selPostCount: (s.selPosts || []).filter(pid => (s.threads[s.activeId] || []).some(mm => String(mm.id) === String(pid))).length,",
'''      postSelMode: selectionActive, selPostCount: selectedMessageIds.length,
      selActionPending: !!s.selActionPending,
      pinSelDisabled: !!s.selActionPending || selectedMessageIds.length !== 1,
      pinSelLabel: selectedMessageIds.length === 1 && this._normMsgId(active && active.pinnedId) === selectedMessageIds[0] ? 'ОТКРЕПИТЬ' : 'ЗАКРЕПИТЬ',''', 'render selection values')
_binding_variants = [
  "      copySelPosts: this.copySelPosts, bookmarkSelPosts: this.bookmarkSelPosts, deleteSelPosts: this.deleteSelPosts,",
  "      copySelPosts: this.copySelPosts, deleteSelPosts: this.deleteSelPosts,"
]
_found = [v for v in _binding_variants if v in text]
if len(_found) != 1: raise RuntimeError(f'render action bindings: expected one supported variant, found {len(_found)}')
text = text.replace(_found[0], "      copySelPosts: this.copySelPosts, pinSelPosts: this.pinSelPosts, deleteSelPosts: this.deleteSelPosts,", 1)
replace_once("      chIsChannel: !!(active && active.isChannel),", "      chIsChannel: !!(active && active.isChannel && !selectionActive),", 'hide channel settings')
replace_once("      gsIsGroup: !!(active && active.isGroup),", "      gsIsGroup: !!(active && active.isGroup && !selectionActive),", 'hide group settings')
replace_once("      chatSettingsShow: !!(active && !active.isChannel && !active.isGroup),", "      chatSettingsShow: !!(active && !active.isChannel && !active.isGroup && !selectionActive),", 'hide chat settings')
replace_once("      openAnySettings: () => { const a = this.state.contacts.find(c => c.id === this.state.activeId); if (a && a.isChannel) this.openChannelSettings(); else if (a && a.isGroup) this.openGroupSettings(); else this.openProfile(); },",
             "      openAnySettings: selectionActive ? (() => {}) : (() => { const a = this.state.contacts.find(c => c.id === this.state.activeId); if (a && a.isChannel) this.openChannelSettings(); else if (a && a.isGroup) this.openGroupSettings(); else this.openProfile(); }),",
             'header guard')
replace_once("      hasPinned: !!(active && active.pinnedId && (s.threads[active.id] || []).some(m => m.id === active.pinnedId)),\n      pinnedText: (active && active.pinnedId) ? (((s.threads[active.id] || []).find(m => m.id === active.pinnedId) || {}).text || '[медиа]') : '',",
'''      hasPinned: !!(!selectionActive && active && active.pinnedId != null && (s.threads[active.id] || []).some(m => this._normMsgId(m.id) === this._normMsgId(active.pinnedId))),
      pinnedText: (active && active.pinnedId != null) ? (((s.threads[active.id] || []).find(m => this._normMsgId(m.id) === this._normMsgId(active.pinnedId)) || {}).text || '[медиа]') : '', ''', 'pinned normalized')
replace_once("      callButtonsShow: !!(active && !active.isChannel),", "      callButtonsShow: !!(active && !active.isChannel && !selectionActive),", 'hide calls')
replace_once("      gcJoinShow: !!(s.gcRoomActive && s.screen === 'chat'),", "      gcJoinShow: !!(s.gcRoomActive && s.screen === 'chat' && !selectionActive),", 'hide group call')

# forward target source filter
replace_once("      fwdEmpty: !!s.fwdIds && s.contacts.filter(c => c.id !== s.activeId && c.id !== 'fav').length === 0,\n      fwdTargets: s.fwdIds ? s.contacts.filter(c => c.id !== s.activeId && c.id !== 'fav').map(c =>",
             "      fwdEmpty: !!s.fwdIds && s.contacts.filter(c => c.id !== (s.fwdSourceChatId || s.activeId) && c.id !== 'fav').length === 0,\n      fwdTargets: s.fwdIds ? s.contacts.filter(c => c.id !== (s.fwdSourceChatId || s.activeId) && c.id !== 'fav').map(c =>",
             'forward target filter')

# goList unified clear
replace_once("      goList: () => { this.setState({ selPosts: [], msgMenu: null }); try { if (this._msgUnsub) { this._msgUnsub(); this._msgUnsub = null; } if (this._metaUnsub) { this._metaUnsub(); this._metaUnsub = null; } if (this._profUnsub) { this._profUnsub(); this._profUnsub = null; } } catch (e) {} this._saveDraftNow(); this.setState({ screen: 'list', attachOpen: false, inChatSearch: false, inChatQuery: '' }); },",
'''      goList: () => { this._selActionLock = null; this._forwardLock = null; this._cancelMessageGestures(); try { if (this._msgUnsub) { this._msgUnsub(); this._msgUnsub = null; } if (this._metaUnsub) { this._metaUnsub(); this._metaUnsub = null; } if (this._profUnsub) { this._profUnsub(); this._profUnsub = null; } } catch (e) {} this._saveDraftNow(); this.setState({ screen: 'list', selPosts: [], selChatId: null, selActionPending: false, selActionToken: null, fwdIds: null, fwdSourceChatId: null, msgMenu: null, postFor: null, attachOpen: false, inChatSearch: false, inChatQuery: '' }); },''', 'goList cleanup')

# normalize pin helpers
replace_once("  pinMsg = () => { const id = this.state.activeId, mid = this.state.msgMenu; const _c = this.state.contacts.find(x => x.id === id) || {}; const _np = (String(_c.pinnedId) === String(mid)) ? null : mid;",
             "  pinMsg = () => { const id = this.state.activeId, mid = this._normMsgId(this.state.msgMenu); const _c = this.state.contacts.find(x => x.id === id) || {}; const _np = (this._normMsgId(_c.pinnedId) === mid) ? null : mid;",
             'pin msg normalize')
replace_once("  jumpToPinned = () => { const a = this.state.contacts.find(c => c.id === this.state.activeId); if (a && a.pinnedId != null) this.jumpToMsg(a.pinnedId); };",
             "  jumpToPinned = () => { if (this._selectionActive()) return; const a = this.state.contacts.find(c => c.id === this.state.activeId); if (a && a.pinnedId != null) this.jumpToMsg(a.pinnedId); };",
             'pinned guard')

# prevent swipe reply while selected at method level too
replace_once("  replyToMsg = (mid) => this.setState({ replyTo: mid, msgMenu: null, editing: null });",
             "  replyToMsg = (mid) => { if (!this._selectionActive()) this.setState({ replyTo: mid, msgMenu: null, editing: null }); };",
             'reply method guard')

# ensure selection clear on direct call screen transitions commonly triggered while selected
replace_once("  goCall = (kind) => {", "  goCall = (kind) => { if (this._selectionActive()) return;", 'call method guard')

# source marker
marker = '<!-- NC_SELECTION_AUDIT_FIX_2026_07_14 -->\n'
text = text.replace('<html><head>', '<html><head>\n' + marker, 1)

out.write_text(text, encoding="utf-8")
print(f"selection patch stage complete: {out} ({len(text)} chars)")
