#!/usr/bin/env python3
"""Аналітика агентної роботи за журналами Claude Code: головна сесія + субагенти workflow.
Використання: tools/agent_analytics.py [шлях_до_теки_проєкту_в_~/.claude/projects] > звіт.json"""
import json, glob, os, re, sys, collections, datetime

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# СЛІД СКІЛА. Кількість викликів Skill нічого не каже про те, чи скілом користувалися:
# він завантажується раз і діє до кінця сесії. Зате видно, чи запускалися інструменти,
# які він приписує, — ось їх і рахуємо. Додав інструмент у скіл — додай сюди рядок.
FOOTPRINT = {
    'browser-verify: проба і знімок':   r'page_shot\.mjs|probe\.mjs',
    'browser-verify: підняти сторінку': r'vite preview|viewer\.py --port',
    'browser-verify: димовий тест':     r'npm test|viewer-wasm\.sh test',
    'build-version: збирання':          r'build_version\.sh',
    'build-version: перевірки моделі':  r'check_overlaps\.sh|check_motion\.sh',
    'print-kit: друкований набір':      r'print3d-parts/make\.sh|check_print\.py|make_bom\.py',
    'media-kit: матеріали':             r'make_media\.sh|compose\.py',
    'число замість ока':                r'trim_png\.py|color\.py',
}

def default_base():
    """Claude Code тримає журнали в ~/.claude/projects/<шлях проєкту, де все, крім літер і цифр, замінено на «-»>."""
    return os.path.expanduser('~/.claude/projects/' + re.sub(r'[^A-Za-z0-9]', '-', ROOT))

BASE = sys.argv[1] if len(sys.argv) > 1 else default_base()
ts = lambda s: datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))

def usage_of(path):
    """Сумарне використання за файлом транскрипту (дедуплікація за message.id)."""
    msgs = {}; tools = {}; skills = {}; foot = {}; times = []; user_msgs = 0
    for line in open(path):
        try: d = json.loads(line)
        except Exception: continue
        if d.get('timestamp'): times.append(ts(d['timestamp']))
        m = d.get('message') or {}
        if d.get('type') == 'assistant' and 'usage' in m:
            mid = m.get('id') or len(msgs); u = m['usage']
            if mid not in msgs or u.get('output_tokens', 0) >= msgs[mid]['output_tokens']: msgs[mid] = u
            for b in m.get('content') or []:
                if isinstance(b, dict) and b.get('type') == 'tool_use':
                    tools[(mid, b.get('id'))] = b.get('name')
                    # Виклики скілів рахуються ЗА КЛЮЧЕМ (mid, id), як і решта інструментів: те саме
                    # повідомлення трапляється в журналі кілька разів (повтори, підсумки стиснення),
                    # і просте grep по назві дає кратне перебільшення.
                    if b.get('name') == 'Skill': skills[(mid, b.get('id'))] = (b.get('input') or {}).get('skill')
                    if b.get('name') == 'Bash':
                        cmd = (b.get('input') or {}).get('command', '')
                        for label, p in FOOTPRINT.items():
                            if re.search(p, cmd): foot[(mid, b.get('id'), label)] = label
        if d.get('type') == 'user' and not d.get('isMeta'):
            c = m.get('content')
            if isinstance(c, str) or (isinstance(c, list) and any(isinstance(b, dict) and b.get('type') == 'text' for b in c)): user_msgs += 1
    tot = collections.Counter()
    for u in msgs.values():
        for k in ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens'): tot[k] += u.get(k, 0) or 0
        tot['thinking_tokens'] += (u.get('output_tokens_details') or {}).get('thinking_tokens', 0) or 0
        stu = u.get('server_tool_use') or {}
        tot['web_search'] += stu.get('web_search_requests', 0) or 0; tot['web_fetch'] += stu.get('web_fetch_requests', 0) or 0
    times.sort(); active = 0.0
    for a, b in zip(times, times[1:]):
        g = (b - a).total_seconds()
        if g < 300: active += g                     # паузи > 5 хв вважаємо простоєм (очікування користувача / ліміту)
    toolc = collections.Counter(tools.values()); skillc = collections.Counter(v for v in skills.values() if v)
    return dict(api_calls=len(msgs), tokens=dict(tot), tools=dict(toolc.most_common()), tool_calls=sum(toolc.values()),
                skills=dict(skillc.most_common()), footprint=dict(collections.Counter(foot.values()).most_common()),
                start=times[0].isoformat() if times else None, end=times[-1].isoformat() if times else None,
                wall_min=round((times[-1] - times[0]).total_seconds() / 60, 1) if times else 0, active_min=round(active / 60, 1), user_msgs=user_msgs)

out = dict(main=None, sessions=[], workflows=[])
# У теці проєкту лежить ПО ФАЙЛУ НА СЕСІЮ, і їх стає більше з кожним запуском claude.
# Раніше цикл перезаписував `main` на кожному кроці, тож у звіт потрапляла випадкова
# остання за алфавітом — семихвилинна замість дев'ятигодинної. Тепер рахуються всі,
# а `main` — найбільша за викликами інструментів (тобто та, де справді працювали).
for f in glob.glob(os.path.join(BASE, '*.jsonl')):
    s = usage_of(f); s['session'] = os.path.basename(f)[:8]; out['sessions'].append(s)
out['sessions'].sort(key=lambda s: s['start'] or '')
if out['sessions']: out['main'] = max(out['sessions'], key=lambda s: s['tool_calls'])

# Скіли: скільки є в проєкті і які з них жодного разу не знадобилися.
used = collections.Counter()
for s in out['sessions']: used.update(s['skills'])
have = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(ROOT, '.claude', 'skills', '*', 'SKILL.md')))
out['skills'] = dict(have=have, used=dict(used.most_common()), never_used=[n for n in have if n not in used])
for wf in sorted(glob.glob(os.path.join(BASE, '*', 'subagents', 'workflows', '*')), key=os.path.getmtime):
    labels = {}; results = set()
    j = os.path.join(wf, 'journal.jsonl')
    if os.path.exists(j):
        for line in open(j):
            try: d = json.loads(line)
            except Exception: continue
            if d.get('type') == 'started': labels[d.get('agentId')] = (d.get('label'), d.get('phase'), d.get('key'))
            if d.get('type') == 'result' and d.get('result'): results.add(d.get('key'))
    agents = []
    for a in sorted(glob.glob(os.path.join(wf, 'agent-*.jsonl'))):
        aid = os.path.basename(a)[6:-6]; u = usage_of(a)
        meta = {}
        try: meta = json.load(open(a.replace('.jsonl', '.meta.json')))
        except Exception: pass
        lab = labels.get(aid, (meta.get('description'), meta.get('workflowPhase'), None))
        u.update(role=lab[0], phase=lab[1], returned_result=lab[2] in results); agents.append(u)
    out['workflows'].append(dict(id=os.path.basename(wf), agents=agents))
print(json.dumps(out, ensure_ascii=False, indent=1))
