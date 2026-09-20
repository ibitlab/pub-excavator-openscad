export const meta = {
  name: 'research-sweep',
  description: 'Паралельний збір фактів із джерелами за переліком тем + критик повноти; кожен дослідник одразу пише результат у файл',
  whenToUse: 'Коли для рішення потрібні зовнішні дані з кількох незалежних тем. args: {runName, context, topics: [{key, prompt}], repo?, outDir?, critic?: true}',
  phases: [
    { title: 'Research', detail: 'по одному досліднику на тему' },
    { title: 'Critique', detail: 'суперечності, прогалини, зведена таблиця' },
  ],
}

const A = args || {}
if (!A.topics || !A.topics.length) throw new Error('research-sweep: потрібні args.topics = [{key, prompt}, ...] і бажано args.context')
const REPO = A.repo || '.'                             // типово — корінь репозиторію (робоча тека агентів)
const OUT = A.outDir || `${REPO}/docs/research/${A.runName || 'sweep'}`
const CONTEXT = A.context || ''

const FACTS = {
  type: 'object',
  properties: {
    summary: { type: 'string' },
    facts: { type: 'array', items: { type: 'object', properties: {
      item: { type: 'string' }, value: { type: 'string' }, source_url: { type: 'string' }, confidence: { type: 'string', enum: ['high', 'medium', 'low'] } },
      required: ['item', 'value', 'confidence'] } },
    open_questions: { type: 'array', items: { type: 'string' } },
  },
  required: ['summary', 'facts'],
}
const SAVE = (file) => `
PERSISTENCE (mandatory, BEFORE returning): run 'mkdir -p ${OUT}' and write your result to '${OUT}/${file}' as Markdown: a summary, then one bullet per fact "- [confidence] **item**: value <source_url>", then open questions.`
const RULES = 'Use WebSearch/WebFetch. Give raw numeric facts with source URLs; mark estimates as estimates; if a link is dead, search the same site by product code/name. Keep original-language product names verbatim.'

phase('Research')
const res = await parallel(A.topics.map(t => () =>
  agent(`${CONTEXT}\nTASK: ${t.prompt}\n${RULES}\n${SAVE(`${t.key}.md`)}`, { label: `research:${t.key}`, phase: 'Research', schema: FACTS })
    .then(r => (r && r.facts) ? { key: t.key, ...r } : null)))
const got = res.filter(Boolean)
log(`дослідників завершило: ${got.length}/${A.topics.length}`)
if (A.critic === false || !got.length) return { outDir: OUT, research: got }

phase('Critique')
const critic = await agent(`${CONTEXT}
You are a completeness critic. The research results are in '${OUT}/' (one Markdown file per topic: ${got.map(r => r.key).join(', ')}). Read them all. Identify: (1) contradictions between researchers, (2) key numbers still missing for the decision at hand, (3) facts you can quickly verify or fix yourself (max 6 searches — do it), (4) a consolidated table of design inputs with the value to use and its confidence.
${SAVE('_critic.md')}`, { label: 'critic:completeness', phase: 'Critique', schema: {
  type: 'object',
  properties: { contradictions: { type: 'array', items: { type: 'string' } }, missing: { type: 'array', items: { type: 'string' } }, fixes: { type: 'array', items: { type: 'string' } },
    design_inputs: { type: 'array', items: { type: 'object', properties: { parameter: { type: 'string' }, value: { type: 'string' }, confidence: { type: 'string' }, note: { type: 'string' } }, required: ['parameter', 'value', 'confidence'] } } },
  required: ['contradictions', 'missing', 'fixes', 'design_inputs'] } })
return { outDir: OUT, research: got.map(r => ({ key: r.key, summary: r.summary, facts: r.facts.length })), critic }
