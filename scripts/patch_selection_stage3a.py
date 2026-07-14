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

# openMsgMenu strict + msgById normalized and selected deletion cleanup
replace_once("  openMsgMenu = (mid) => { if (Date.now() - (this._justSwiped || 0) < 400) return; this.setState({ msgMenu: mid }); };",
             "  openMsgMenu = (mid) => { if (this._selectionActive() || Date.now() - (this._justSwiped || 0) < 400) return; this.setState({ msgMenu: mid }); };",
             'open msg menu')
replace_once("  msgById = (mid) => { const id = this.state.activeId; return (this.state.threads[id] || []).find(m => m.id === mid); };",
             "  msgById = (mid) => { const id = this.state.activeId, k = this._normMsgId(mid); return (this.state.threads[id] || []).find(m => this._normMsgId(m.id) === k); };",
             'msgById')
text = text.replace("this.setState(st => ({ selPosts: st.selPosts.map(String).filter(x => x !== _mk) })); return;", "this.setState(st => { const next = st.selPosts.map(String).filter(x => x !== _mk); return { selPosts: next, selChatId: next.length ? st.selChatId : null }; }); return;", 1)
text = text.replace("selPosts: st.selPosts.map(String).filter(x => x !== _mk) }));", "selPosts: (st.selPosts || []).map(String).filter(x => x !== _mk), selChatId: (st.selPosts || []).map(String).filter(x => x !== _mk).length ? st.selChatId : null }));", 1)

# swipeRef with long press + selection guards
sw_start = text.index('  swipeRef = (mid) => (el) => {')
sw_end = text.index('  openMsgMenu =', sw_start)
new_swipe = r'''  swipeRef = (mid) => (el) => {
    if (!el) return;
    el.__mid = this._normMsgId(mid);
    if (el.__swipeWired) return; el.__swipeWired = true;
    let sx = 0, sy = 0, tid = null, active = false, dx = 0, longTimer = null, longFired = false;
    const cancelLong = () => { if (longTimer) clearTimeout(longTimer); longTimer = null; };
    el.__cancelLongPress = cancelLong;
    const reset = () => { cancelLong(); el.style.transition = 'transform .15s'; el.style.transform = ''; active = false; dx = 0; setTimeout(() => { try { el.style.transition = ''; } catch (e) {} }, 170); };
    el.addEventListener('touchstart', (e) => {
      if (!e.touches || !e.touches[0] || this.state.selActionPending) return;
      const t = e.touches[0]; sx = t.clientX; sy = t.clientY; tid = t.identifier; active = !this._selectionActive(); dx = 0; longFired = false;
      try { el.style.transition = ''; } catch (er) {}
      cancelLong();
      if (!this._selectionActive()) longTimer = setTimeout(() => {
        if (!active || Math.abs(dx) > 8) return;
        longFired = true; active = false; this._selectionSuppressClickUntil = Date.now() + 750;
        this.togglePostSel(el.__mid); try { this._vibrate && this._vibrate(24); } catch (x) {}
      }, 500);
    }, { passive: true });
    el.addEventListener('touchmove', (e) => {
      if (!e.touches) return;
      let t = null; for (let k = 0; k < e.touches.length; k++) { if (e.touches[k].identifier === tid) { t = e.touches[k]; break; } }
      if (!t) return;
      const ddx = t.clientX - sx, ddy = t.clientY - sy;
      if (Math.abs(ddx) > 9 || Math.abs(ddy) > 9) cancelLong();
      if (!active || this._selectionActive()) return;
      if (Math.abs(ddy) > Math.abs(ddx)) { active = false; el.style.transform = ''; return; }
      if (ddx < 0) { dx = Math.max(ddx, -80); el.style.transform = 'translateX(' + dx + 'px)'; if (e.cancelable) e.preventDefault(); }
    }, { passive: false });
    const end = () => {
      cancelLong();
      if (longFired) { reset(); return; }
      if (!active || this._selectionActive()) { reset(); return; }
      if (dx < -55) { this._justSwiped = Date.now(); this.replyToMsg(el.__mid); }
      reset();
    };
    el.addEventListener('touchend', end); el.addEventListener('touchcancel', end);
  };
'''
text = text[:sw_start] + new_swipe + text[sw_end:]

# app state clear selection when backgrounded
replace_once("    try { App.addListener('appStateChange', (st) => { this._appActive = !!st.isActive; }); } catch (e) {}",
             "    try { App.addListener('appStateChange', (st) => { this._appActive = !!st.isActive; if (!this._appActive && ((this.state.selPosts || []).length || this.state.selChatId)) this.clearPostSel(); }); } catch (e) {}",
             'app state')

# back priority and duplicate cleanup
replace_once("    // снять выделение сообщений/постов\n    if (s.selPosts && s.selPosts.length) { this.clearPostSel(); return; }\n    // оверлеи и модалки (приоритетно)",
             "    // оверлеи и подтверждения (приоритетно)\n    if (s.confirmBox) { this.confirmNo(); return; }\n    // снять выделение сообщений/постов\n    if ((s.selPosts && s.selPosts.length) || s.selChatId) { this.clearPostSel(); return; }\n    // остальные оверлеи и модалки",
             'back priority')
replace_once("    if (s.selPosts && s.selPosts.length) { this.setState({ selPosts: [] }); return; }\n    if (s.fwdIds) { this.setState({ fwdIds: null }); return; }\n", "", 'remove duplicate back selection')
replace_once("this.setState({ screen: 'list', selPosts: [], msgMenu: null }); return;", "this.setState({ screen: 'list', selPosts: [], selChatId: null, selActionPending: false, selActionToken: null, fwdIds: null, fwdSourceChatId: null, msgMenu: null }); return;", 'back chat cleanup')

# Firebase snapshot reconcile selection
replace_once("      this.setState(st => ({ threads: { ...st.threads, [uid]: mapped } }));",
'''      this.setState(st => {
        const patch = { threads: { ...st.threads, [uid]: mapped } };
        if (st.selChatId === uid && (st.selPosts || []).length) {
          const existing = new Set(mapped.map(m => this._normMsgId(m.id)));
          const next = [...new Set(st.selPosts.map(this._normMsgId).filter(id => existing.has(id)))];
          patch.selPosts = next; patch.selChatId = next.length ? uid : null;
          if (!next.length) { patch.selActionPending = false; patch.selActionToken = null; }
        }
        return patch;
      });''', 'firebase reconcile')

# componentDidUpdate reconciliation and unmount gesture cleanup
replace_once('  componentDidUpdate() {\n    this._matrixEnsure();',
'''  componentDidUpdate() {
    this._matrixEnsure();''', 'component did update signature')
replace_once("    this._lastActiveId = id; this._lastMsgCount = count; if (this.state.screen !== 'auth') this.persist(); }\n  deleteAccount = () => {",
'''    this._lastActiveId = id; this._lastMsgCount = count;
    const st = this.state;
    if (st.selChatId && (st.selPosts || []).length) {
      if (st.screen !== 'chat' || st.activeId !== st.selChatId) {
        this._selActionLock = null; this.setState({ selPosts: [], selChatId: null, selActionPending: false, selActionToken: null }); return;
      }
      const next = this._validSelectionIds(st, st.selChatId);
      const cur = (st.selPosts || []).map(this._normMsgId);
      if (next.length !== cur.length || next.some((v, i) => v !== cur[i])) {
        this.setState({ selPosts: next, selChatId: next.length ? st.selChatId : null, selActionPending: next.length ? st.selActionPending : false, selActionToken: next.length ? st.selActionToken : null }); return;
      }
    }
    if (this.state.screen !== 'auth') this.persist();
  }
  deleteAccount = () => {''', 'component reconciliation')
replace_once("  componentWillUnmount() { clearInterval(this.recTimer); clearInterval(this.callTimer); clearInterval(this.clockTimer); clearTimeout(this.replyTO); clearTimeout(this.copyTO); clearTimeout(this._persistTO); if (!FIREBASE_ENABLED) this._persistRaw(); if (this._msgUnsub) this._msgUnsub(); if (this._contactsUnsub) this._contactsUnsub(); if (this._chatsUnsub) this._chatsUnsub(); }",
             "  componentWillUnmount() { this._cancelMessageGestures(); clearInterval(this.recTimer); clearInterval(this.callTimer); clearInterval(this.clockTimer); clearTimeout(this.replyTO); clearTimeout(this.copyTO); clearTimeout(this._persistTO); if (!FIREBASE_ENABLED) this._persistRaw(); if (this._msgUnsub) this._msgUnsub(); if (this._contactsUnsub) this._contactsUnsub(); if (this._chatsUnsub) this._chatsUnsub(); }",
             'unmount gestures')


out.write_text(text, encoding="utf-8")
print(f"selection patch stage complete: {out} ({len(text)} chars)")
