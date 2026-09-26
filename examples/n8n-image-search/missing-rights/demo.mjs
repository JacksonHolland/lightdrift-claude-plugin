// Synthetic fixtures. Executes only the trusted bundled review node; no HTTP or credentials.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const workflow = JSON.parse(fs.readFileSync(new URL('./workflow.json', import.meta.url)));
const code = workflow.nodes.find(n => n.name === 'Review image candidates').parameters.jsCode;
function review(response) {
  return JSON.parse(JSON.stringify(vm.runInNewContext('(function(){'+code+'})()', {
    $input: {all: () => [{json: response}]}
  }, {timeout: 1000})));
}
const input = {query_id: 'offline-missing-rights', results: [{asset_id: 'offline-placeholder'}]};
const output = review(input);
const candidate = output[0].json.candidates[0];
assert.equal(candidate.rights, null);
assert.equal(candidate.source_page, null);
assert.equal(output[0].json.review_status, 'Human source and license review required before use');
assert.deepEqual(output[0].json.response, input);
console.log(JSON.stringify(output, null, 2));
const partial = {commercial: null, attribution_required: false};
const partialOutput = review({query_id: 'offline-partial-rights', results: [{asset_id: 'offline-partial', rights: partial}]})[0].json.candidates[0];
assert.deepEqual(partialOutput.rights, partial);
assert.equal(partialOutput.source_page, null);
console.log('PARTIAL', JSON.stringify({rights: partialOutput.rights, source_page: partialOutput.source_page}));
console.log('PASS: absent rights/source page stay null; partial rights and false flags survive unchanged.');
