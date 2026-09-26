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
const input = {query_id: 'offline-empty', results: []};
const output = review(input);
assert.equal(output.length, 1);
assert.equal(output[0].json.result_count, 0);
assert.deepEqual(output[0].json.candidates, []);
assert.deepEqual(output[0].json.response, input);
console.log(JSON.stringify(output, null, 2));
assert.throws(() => review({query_id: 'offline-malformed', results: {}}), /response envelope/);
console.log('PASS: empty response preserves one review item; malformed results rejected.');
