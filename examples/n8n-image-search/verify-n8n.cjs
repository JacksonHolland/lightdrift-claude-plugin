// Optional maintainer compatibility check; see VALIDATION.md for dependencies.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {NodeHelpers} = require('n8n-workflow');
const dist=process.argv[2];
if (!dist) throw Error('Pass extracted n8n-nodes-base@2.40.2 package/dist path');
const w=JSON.parse(fs.readFileSync(path.join(__dirname,'workflow.json')));
const source=(p)=>fs.readFileSync(path.join(dist,p),'utf8');
const scope={exports:{},require(name){
  // Unused HTML response optimization needs browser parser dependencies.
  // Omit only that unrelated property group, not HTTP/auth/body/response options.
  assert.equal(name,'../shared/optimizeResponse');
  return {optimizeResponseProperties:[]};
}};
vm.runInNewContext(source('nodes/HttpRequest/V3/Description.js'),scope);
const node=w.nodes.find(n=>n.type==='n8n-nodes-base.httpRequest');
const normalized=NodeHelpers.getNodeParameters(scope.exports.mainProperties,node.parameters,true,false,node);
assert.equal(normalized.method,'POST');
assert.equal(normalized.url,node.parameters.url);
assert.equal(normalized.authentication,'genericCredentialType');
assert.equal(normalized.genericAuthType,'httpHeaderAuth');
assert.equal(normalized.sendBody,true);
assert.equal(normalized.contentType,'json');
assert.equal(normalized.specifyBody,'json');
assert.equal(normalized.jsonBody,'={{ $json }}');
assert.equal(normalized.options.redirect.redirect.followRedirects,false);
assert.equal(normalized.options.response.response.responseFormat,'json');
assert.equal(normalized.options.response.response.neverError,false);
assert.equal(normalized.options.timeout,60000);
assert.match(source('nodes/HttpRequest/HttpRequest.node.js'),/4\.4: new HttpRequestV3/);
assert.match(source('nodes/Set/Set.node.js'),/3\.4: new SetV2/);
assert.match(source('nodes/Set/v2/manual.mode.js'),/name: 'assignments'/);
assert.match(source('nodes/Code/Code.node.js'),/version: \[1, 2\]/);
assert.match(source('nodes/ManualTrigger/ManualTrigger.node.js'),/version: 1/);
const {HttpHeaderAuth}=require(path.resolve(dist,'credentials/HttpHeaderAuth.credentials.js'));
const auth=new HttpHeaderAuth();
assert.equal(auth.name,'httpHeaderAuth');
assert.equal(auth.authenticate.properties.headers['={{$credentials.name}}'],'={{$credentials.value}}');
console.log('PASS: published HTTP Request parameter schema normalized by n8n-workflow@2.40.1; Header Auth mapping; published node versions Manual Trigger 1, Set 3.4, Code 2, HTTP Request 4.4.');
console.log('Source package n8n-nodes-base@2.40.2 belongs to n8n@2.40.7. This is a package-level compatibility check, not an n8n UI import or workflow-engine execution.');
