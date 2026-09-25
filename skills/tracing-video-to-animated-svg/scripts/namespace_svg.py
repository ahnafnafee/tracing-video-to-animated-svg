"""Prefix every id, class, and keyframe name in an SVG so it can be inlined in a page.

An inline SVG shares the page's id space and stylesheet: generated ids (g1, clip2) and short classes
(.spin, .prop) collide with the page and with each other. This rewrites the markup and its <style>
blocks so every name starts with the prefix, and sets the root element's id. References through
url(#..), href and xlink:href follow the renamed ids.

Rules that name a class or id are prefixed but NOT scoped under the root id: art drawn through <use>
lives in a shadow tree, where an ancestor selector such as `#root .spin` never matches, so a scoped
rule silently stops animating anything reused with <use>. The prefix alone keeps them unique. Rules
with no class or id (`*`, `path`) would reach the whole page, so those are scoped under the root,
and a universal rule also gets prefixed-class variants that do match inside <use> shadow trees.

usage:
  python namespace_svg.py IN.svg OUT.svg --prefix rb- --root-id ride-bike
"""
import argparse
import re
from pathlib import Path


def keep(prefix, name):
    return name if name.startswith(prefix) else prefix + name


def top_level_rules(css):
    """Split a stylesheet into (prelude, block) pairs at brace depth zero."""
    rules, depth, start, prelude = [], 0, 0, ''
    for i, ch in enumerate(css):
        if ch == '{':
            if depth == 0:
                prelude, start = css[start:i].strip(), i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                rules.append((prelude, css[start:i + 1]))
                start = i + 1
    return rules


def scope_css(css, prefix, root, frames):
    out = []
    for prelude, block in top_level_rules(css):
        if prelude.startswith('@keyframes'):
            out.append(f'@keyframes {keep(prefix, prelude.split()[1])}{block}')
        elif prelude.startswith('@media') or prelude.startswith('@supports'):
            out.append(prelude + '{' + scope_css(block[1:-1], prefix, root, frames) + '}')
        elif prelude.startswith('@'):
            out.append(prelude + block)
        else:
            block = re.sub(r'(animation(?:-name)?\s*:\s*)([\w-]+)',
                           lambda m: m.group(1) + (keep(prefix, m.group(2)) if m.group(2) in frames else m.group(2)), block)
            selectors = []
            for s in prelude.split(','):
                s = s.strip()
                named = re.search(r'[.#]-?[_a-zA-Z]', s)
                s = re.sub(r'\.(-?[_a-zA-Z][\w-]*)', lambda m: '.' + keep(prefix, m.group(1)), s)
                s = re.sub(r'#(-?[_a-zA-Z][\w-]*)', lambda m: '#' + (m.group(1) if m.group(1) == root else keep(prefix, m.group(1))), s)
                if named or s.startswith(f'#{root}'):
                    selectors.append(s)
                elif s == '*':
                    selectors += [f'#{root}', f'#{root} *', f'[class^="{prefix}"]', f'[class*=" {prefix}"]']
                else:
                    selectors.append(f'#{root} {s}')
            out.append(','.join(selectors) + block)
    return ''.join(out)


def namespace(svg, prefix, root):
    styles = re.findall(r'<style[^>]*>(.*?)</style>', svg, re.S)
    frames = set(re.findall(r'@keyframes\s+([\w-]+)', ''.join(styles)))
    body = re.sub(r'<style[^>]*>.*?</style>', '\0', svg, flags=re.S)
    body = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{m.group(1) if m.group(1) == root else keep(prefix, m.group(1))}"', body)
    body = re.sub(r'url\(#([^)]+)\)', lambda m: f'url(#{keep(prefix, m.group(1))})', body)
    body = re.sub(r'((?:xlink:)?href)="#([^"]+)"', lambda m: f'{m.group(1)}="#{keep(prefix, m.group(2))}"', body)
    body = re.sub(r'\bclass="([^"]+)"', lambda m: 'class="' + ' '.join(keep(prefix, c) for c in m.group(1).split()) + '"', body)
    root_tag = re.search(r'<svg\b[^>]*>', body).group(0)
    tagged = re.sub(r'\sid="[^"]*"', '', root_tag).replace('<svg', f'<svg id="{root}"', 1)
    body = body.replace(root_tag, tagged, 1)
    for css in styles:
        body = body.replace('\0', f'<style>{scope_css(css, prefix, root, frames)}</style>', 1)
    return body


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--prefix', required=True); ap.add_argument('--root-id', required=True)
    a = ap.parse_args()
    out = namespace(Path(a.src).read_text(encoding='utf-8'), a.prefix, a.root_id)
    Path(a.dst).write_text(out, encoding='utf-8')
    ids = set(re.findall(r'\bid="([^"]+)"', out))
    refs = set(re.findall(r'url\(#([^)]+)\)', out)) | set(re.findall(r'href="#([^"]+)"', out))
    missing = sorted(refs - ids)
    print(f'{len(ids)} ids, {len(refs)} referenced' + (f'; dangling: {missing[:5]}' if missing else '; no dangling references'))


if __name__ == '__main__':
    main()
