import {test} from 'node:test'
import assert from 'node:assert/strict'
import {Schema} from '@sanity/schema'
import types, {imageReviewCandidate, reviewActions} from './schema.mjs'
import {execFileSync} from 'node:child_process'

test('Sanity compiler resolves queue, candidate and nested array types', () => {
  const schema = Schema.compile({name: 'image-review-test', types})
  const queue = schema.get('imageReview')
  assert.equal(queue.type.name, 'document')
  const candidates = queue.fields.find(f => f.name === 'candidates')
  assert.equal(candidates.type.of[0].name, 'imageReviewCandidate')
  const generated = JSON.parse(execFileSync('python3', ['review_queue.py', '--content-draft', 'drafts.article-1'], {encoding:'utf8'})).draft
  for (const key of Object.keys(generated).filter(k => !k.startsWith('_'))) {
    assert.ok(queue.fields.some(f => f.name === key), `schema declares ${key}`)
  }
})
test('approval requires a human audit record', () => {
  const validate = imageReviewCandidate.validation({custom: fn => fn})
  assert.equal(validate({decision:'pending'}), true)
  assert.notEqual(validate({decision:'approved'}), true)
  assert.equal(validate({decision:'approved',reviewer:'Editor',reviewNotes:'Source and intended use checked',reviewedAt:'2026-09-26T00:00:00Z'}), true)
})
test('queue UI permits delete only; content types retain existing actions', () => {
  const previous = ['publish','schedule','delete','duplicate'].map(action=>({action}))
  assert.deepEqual(reviewActions(previous,{schemaType:'imageReview'}),[{action:'delete'}])
  assert.equal(reviewActions(previous,{schemaType:'post'}),previous)
})
