export const meta = {
  name: 'design-review',
  description: 'Незалежна перевірка конструкції: рецензенти з різними лінзами, потім спроба спростувати кожну суттєву знахідку; кожен агент одразу пише результат у файл',
  whenToUse: 'Після значних змін моделі/розрахунків, перед різанням металу. args: {runName, repo?, context?, lenses?, verify?: "none"|"critical-major"|"all", maxVerify?, maxFindings?}',
  phases: [
    { title: 'Review', detail: 'рецензенти з різними лінзами' },
    { title: 'Verify', detail: 'спростування суттєвих знахідок' },
  ],
}

const A = args || {}
const REPO = A.repo || '.'                             // типово — корінь репозиторію (робоча тека агентів)
const RUN = A.runName || 'review'                      // мітку часу передає викликач (Date у скриптах недоступний)
const OUT = A.outDir || `${REPO}/docs/reviews/${RUN}`
const MAXF = A.maxFindings || 8
const VERIFY = A.verify || 'critical-major'
const MAXV = A.maxVerify || 8

const CONTEXT = A.context || `
You are reviewing a parametric OpenSCAD design of a mini-excavator working equipment (boom + stick + bucket linkage) for a homebuilt towable excavator.
Repository: ${REPO} (all paths below are relative to it). Read README.md and CLAUDE.md first, then the files relevant to your lens:
 - scad/excavator_boom.scad — parametric model (angles are primary parameters; limits computed from cylinder lengths; part selector, flat projection, BOM echo).
 - tools/kinematics.py — independent Python solver of the same geometry; tools/strength.py — planar statics + section/pin/weld checks.
 - docs/01-design-inputs.md — purchased cylinders, available steel, hydraulics, norms. Latest generated reports: versions/<highest>/docs/.
Tools: 'openscad -o /tmp/x.echo scad/excavator_boom.scad' for echo(); '-D name=value' (one -D per value) to override; 'tools/check_overlaps.sh'; python3 scripts run from tools/.
Do NOT modify repository files, EXCEPT writing your own result file described below.
Conventions: side view X forward, Z up; boom chord angle theta to horizontal; stick interior angle psi at joint B; bucket angle omega relative to stick axis (+ = curl).`

const SAVE = (file) => `
PERSISTENCE (mandatory, do this BEFORE returning): run 'mkdir -p ${OUT}' and write your complete result as JSON to '${OUT}/${file}'. A previous run lost all reviewer output to a usage limit because results lived only in the return value.`

const FINDINGS = {
  type: 'object',
  properties: {
    findings: { type: 'array', items: { type: 'object', properties: {
      title: { type: 'string' }, severity: { type: 'string', enum: ['critical', 'major', 'minor'] },
      file: { type: 'string' }, location: { type: 'string' }, problem: { type: 'string' }, evidence: { type: 'string' }, fix: { type: 'string' } },
      required: ['title', 'severity', 'file', 'problem', 'evidence', 'fix'] } },
    overall: { type: 'string' },
  },
  required: ['findings', 'overall'],
}
const VERDICT = { type: 'object', properties: { refuted: { type: 'boolean' }, reasoning: { type: 'string' }, corrected_fix: { type: 'string' } }, required: ['refuted', 'reasoning'] }

const RULES = `Report only findings you are confident are REAL and material (bugs, wrong formulas or conventions, unsafe assumptions, missing checks, collisions, unbuildable details). For each: file, location, what is wrong, evidence with numbers, concrete fix. Rank by severity. At most ${MAXF} findings.`

const DEFAULT_LENSES = [
  { key: 'kinematics', prompt: 'LENS: KINEMATICS & MODEL CONSISTENCY. Independently re-derive angle limits from cylinder lengths (own small script under /tmp) and compare with the SCAD echo and tools/kinematics.py. Check sign conventions, branch choice of the bucket linkage, limit solver logic, cylinder base/rod orientation, collisions of cylinder bodies and moving parts at the extremes (render with -D and compute clearances numerically), dead-centre risk (transmission angle < ~12 deg).' },
  { key: 'strength', prompt: 'LENS: STATICS & STRENGTH. Verify tools/strength.py: member equilibrium for one hand-picked configuration, signs of cylinder forces (digging is done by PUSH), internal-force diagrams incl. jumps at eccentric brackets, section properties vs standard tables, composite sections with plates, completeness of load cases, stability cap, safety-factor criteria, pin bending/bearing, weld checks. Flag every non-conservative assumption.' },
  { key: 'build', prompt: 'LENS: BUILDABILITY (experienced welder/fabricator). Judge joints, clevis gaps vs real cylinder eye widths, pin lengths vs purchased pins, load paths from brackets into tube walls, weld access, mitre joint practice, assembly order, grease points, clearances for moving parts and hoses. Suggest concrete improvements with dimensions.' },
  { key: 'scad', prompt: 'LENS: OPENSCAD CODE & USABILITY. Compile for warnings, Customizer compatibility, -D overrides, robustness under unusual parameters (no undef, clear warnings), part selector and flat projection for every registered part, consistency between SCAD parameters, kinematics.py GEOM and strength.py, plate placement conventions (plates abut, never overlap: run tools/check_overlaps.sh).' },
]
const lenses = A.lenses || DEFAULT_LENSES

phase('Review')
const reviews = await parallel(lenses.map(l => () =>
  agent(`${CONTEXT}\n${l.prompt}\n${RULES}\n${SAVE(`review-${l.key}.json`)}`, { label: `review:${l.key}`, phase: 'Review', schema: FINDINGS })
    .then(r => (r && r.findings) ? { key: l.key, ...r } : null)))
const ok = reviews.filter(Boolean)
const all = ok.flatMap(r => (r.findings || []).map(f => ({ lens: r.key, ...f })))
log(`рецензентів завершило: ${ok.length}/${lenses.length}; знахідок: ${all.length} (critical: ${all.filter(f => f.severity === 'critical').length})`)

let toVerify = VERIFY === 'none' ? [] : all.filter(f => VERIFY === 'all' || f.severity !== 'minor')
if (toVerify.length > MAXV) { log(`верифікацію обмежено: ${MAXV} із ${toVerify.length} (решту розібрати вручну)`); toVerify = toVerify.slice(0, MAXV) }

phase('Verify')
const verified = await parallel(toVerify.map((f, i) => () =>
  agent(`${CONTEXT}\nA reviewer (lens: ${f.lens}) reported the finding below. Try hard to REFUTE it by reading the actual code/docs and running the tools. Default to refuted=true if it is speculative, already handled, or not material. If it stands, restate the minimal correct fix.\nFINDING: ${JSON.stringify(f)}\n${SAVE(`verdict-${String(i + 1).padStart(2, '0')}-${f.lens}.json`)}`,
    { label: `verify:${f.lens}:${(f.title || '').slice(0, 30)}`, phase: 'Verify', schema: VERDICT })
    .then(v => v ? ({ ...f, verdict: v }) : null)))
const v = verified.filter(Boolean)
return {
  outDir: OUT,
  confirmed: v.filter(f => !f.verdict.refuted),
  refuted: v.filter(f => f.verdict.refuted).map(f => ({ title: f.title, lens: f.lens, why: f.verdict.reasoning })),
  unverified: all.filter(f => !v.find(x => x.title === f.title)),
  overall: ok.map(r => ({ key: r.key, overall: r.overall })),
}
