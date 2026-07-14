from pathlib import Path
import argparse
import base64, re

parser = argparse.ArgumentParser()
parser.add_argument('src')
parser.add_argument('out')
parser.add_argument('--runtime-out', default='')
args = parser.parse_args()
src = Path(args.src)
out = Path(args.out)
html = src.read_text(encoding='utf-8')

old_loop = '<sc-for list="{{ messages }}" as="m" hint-placeholder-count="0">'
new_loop = '<sc-for list="{{ messages }}" as="m" key="{{ m.mid }}" hint-placeholder-count="0">'
if old_loop not in html:
    raise SystemExit('message sc-for not found')
html = html.replace(old_loop, new_loop, 1)

pat = re.compile(r'src="data:text/javascript;base64,([A-Za-z0-9+/=]+)"')
matches = list(pat.finditer(html))
replaced = False
for m in matches:
    try:
        decoded = base64.b64decode(m.group(1)).decode('utf-8')
    except Exception:
        continue
    if decoded.startswith('// GENERATED from dc-runtime'):
        old1 = '''  function walkFor(el, host) {
    const listGet = compileAttr(el.getAttribute("list") || "");
    const asName = el.getAttribute("as") || "item";
    const hintN = parseInt(el.getAttribute("hint-placeholder-count") || "0", 10);
    const kids = walkChildren(el, host);
    const listSrc = el.getAttribute("list") || "";
'''
        new1 = '''  function walkFor(el, host) {
    const listGet = compileAttr(el.getAttribute("list") || "");
    const asName = el.getAttribute("as") || "item";
    const keyRaw = el.getAttribute("key");
    const keyGet = keyRaw != null ? compileAttr(keyRaw) : null;
    const hintN = parseInt(el.getAttribute("hint-placeholder-count") || "0", 10);
    const kids = walkChildren(el, host);
    const listSrc = el.getAttribute("list") || "";
'''
        old2 = '''        list.map((item, i) => {
          const sub = { ...vals, [asName]: item, $index: i };
          return h(
            getReact().Fragment,
            { key: i },
            kids.map((b, j) => b(sub, ctx, j))
          );
        })
'''
        new2 = '''        list.map((item, i) => {
          const sub = { ...vals, [asName]: item, $index: i };
          let itemKey = keyGet ? keyGet(sub) : i;
          if (itemKey === void 0 || itemKey === null || itemKey === "") itemKey = i;
          return h(
            getReact().Fragment,
            { key: String(itemKey) },
            kids.map((b, j) => b(sub, ctx, j))
          );
        })
'''
        if old1 not in decoded or old2 not in decoded:
            raise SystemExit('runtime walkFor patterns not found')
        decoded = decoded.replace(old1, new1, 1).replace(old2, new2, 1)
        encoded = base64.b64encode(decoded.encode('utf-8')).decode('ascii')
        html = html[:m.start(1)] + encoded + html[m.end(1):]
        if args.runtime_out: Path(args.runtime_out).write_text(decoded, encoding='utf-8')
        replaced = True
        break

if not replaced:
    raise SystemExit('dc-runtime data script not found')
out.write_text(html, encoding='utf-8')
print(out)
print('size', out.stat().st_size)
