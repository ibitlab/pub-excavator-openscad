#!/usr/bin/env python3
"""Аналітика агентної роботи за журналами Claude Code: головна сесія + субагенти workflow.
Використання: tools/agent_analytics.py [шлях_до_теки_проєкту_в_~/.claude/projects] > звіт.json"""
import json, glob, os, re, sys, collections, datetime

def default_base():
    """Claude Code тримає журнали в ~/.claude/projects/<шлях проєкту, де все, крім літер і цифр, замінено на «-»>."""
    root = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    return os.path.expanduser('~/.claude/projects/' + re.sub(r'[^A-Za-z0-9]', '-', root))

BASE = sys.argv[1] if len(sys.argv) > 1 else default_base()
ts = lambda s: datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))

def usage_of(path):
    """Сумарне використання за файлом транскрипту (дедуплікація за message.id)."""
    msgs = {}; tools = collections.Counter(); times = []; user_msgs = 0
    for line in open(path):
        try: d = json.loads(line)
        except Exception: continue
        if d.get('timestamp'): times.append(ts(d['timestamp']))
        m = d.get('message') or {}
        if d.get('type') == 'assistant' and 'usage' in m:
            mid = m.get('id') or len(msgs); u = m['usage']
            if mid not in msgs or u.get('output_tokens', 0) >= msgs[mid]['output_tokens']: msgs[mid] = u
            for b in m.get('content') or []:
                if isinstance(b, dict) and b.get('type') == 'tool_use': tools[(mid, b.get('id'))] = b.get('name')
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
    toolc = collections.Counter(tools.values())
    return dict(api_calls=len(msgs), tokens=dict(tot), tools=dict(toolc.most_common()), tool_calls=sum(toolc.values()),
                start=times[0].isoformat() if times else None, end=times[-1].isoformat() if times else None,
                wall_min=round((times[-1] - times[0]).total_seconds() / 60, 1) if times else 0, active_min=round(active / 60, 1), user_msgs=user_msgs)

out = dict(main=None, workflows=[])
for f in glob.glob(os.path.join(BASE, '*.jsonl')):
    out['main'] = usage_of(f); out['main']['session'] = os.path.basename(f)[:8]
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
