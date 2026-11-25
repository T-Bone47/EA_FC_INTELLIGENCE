import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'

for (const [mode, exit] of Object.entries({ pass: 0, warning: 0, assertion: 1, crash: 1,
  launch: 1, config: 1, missing: 1, emptySuite: 1, artifact: 1, cleanup: 1 })) {
  test(mode, t => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'fc-qa-'))
    t.after(() => fs.rmSync(dir, { recursive: true, force: true }))
    const report = path.join(dir, 'run.json')
    const source = `
      import { runQA } from ${JSON.stringify(new URL('./qa.mjs', import.meta.url).href)}
      import fs from 'node:fs'
      const mode = process.env.CASE
      process.exitCode = await runQA({
        base: mode === 'config' ? '' : 'http://localhost',
        out: process.env.REPORT, shots: process.env.SHOTS,
        requiredSuites: ['live'], screenshots: mode === 'artifact' ? ['required'] : [],
        launch: async () => {
          if (mode === 'launch') throw Error('launch failed')
          return { version: async () => 'fixture', close: async () => {
            fs.writeFileSync(process.env.REPORT + '.closed', 'closed')
            if (mode === 'cleanup') throw Error('close failed')
          } }
        },
        run: async ({guard, check}) => {
          if (mode !== 'missing') await guard('live', async () => {
            if (mode === 'crash') throw Error('page load failed')
            if (mode === 'emptySuite') return
            check('required', mode !== 'assertion')
            if (mode === 'warning') check('diagnostic', false, 'minor', 'WARNING')
          })
        }
      })
    `
    const child = spawnSync(process.execPath, ['--input-type=module', '-e', source],
      { env: { ...process.env, CASE: mode, REPORT: report, SHOTS: dir }, encoding: 'utf8' })
    assert.equal(child.status, exit, child.stderr)
    const result = JSON.parse(fs.readFileSync(report, 'utf8'))
    assert.equal(result.exitCode, exit)
    assert.equal(result.status, exit ? 'FAIL' : 'PASS')
    assert.equal(fs.existsSync(report + '.closed'), !['config', 'launch'].includes(mode))
  })
}
