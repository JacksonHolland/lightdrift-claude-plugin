# Compatibility evidence — September 26, 2026

Outcome: local fixture checks and published n8n package contract checks passed. No n8n server/UI import, authenticated API search, media fetch, license clearance, customer activation, or public publication is claimed by this report.

## Tested versions and scope

- Local runtime: Node.js `v24.21.0`.
- Official npm `n8n@2.40.7` resolved on September 26, 2026. Its dependencies specify `n8n-nodes-base@2.40.2` and `n8n-workflow@2.40.1`.
- Workflow versions: Manual Trigger `1`, Edit Fields/Set `3.4`, Code `2`, HTTP Request `4.4`. These are registered in that published nodes-base package. They need not be each node's newest version.
- `verify.mjs`: runs the exact two Code node bodies in Node VM with n8n-shaped `$input` fixture data. Checks default false/strict boolean opt-in, blank/overlong/non-string queries, Unicode length, rejection of multiple inputs, fixed request shape, graph edges, credential placeholder, one HTTP node, Execute Once, no retries/redirects/pagination, timeout, rights and degraded response preservation, empty results, null/missing fields, and malformed envelopes.
- `verify-n8n.cjs`: loads the published HTTP Request description and normalizes configured parameters with real `n8n-workflow` NodeHelpers. Confirms POST, endpoint, Generic Header Auth, JSON body, response format, fail-on-non-2xx, timeout, and redirect flag survive normalization. Checks the published Header Auth credential's header mapping. This omits the unrelated HTML response-optimization property group to avoid pulling browser parser dependencies. It does not mock the tested HTTP/auth/body/response parameter declarations.
- Lightdrift live OpenAPI `info.version: 1.0`: request fields, text maxLength 1000, k range 1–100 and filter types checked. The orientation enum is documented in the API introduction; OpenAPI exposes a string. OpenAPI's success response schema is unconstrained, so response fields come from the current official response docs. `contract-snapshot.json` contains the relevant public subset, with retrieval URL/date.

## Reproduce

Offline checks need only Node.js:

```sh
node verify.mjs
```

For the optional maintainer package check, install `n8n-workflow@2.40.1` in an isolated directory, download/extract the official `n8n-nodes-base@2.40.2` npm tarball, then use:

```sh
NODE_PATH=/path/to/isolated/node_modules node verify-n8n.cjs /path/to/extracted/package/dist
```

Package sources: https://registry.npmjs.org/n8n/2.40.7 , https://registry.npmjs.org/n8n-workflow/2.40.1 , https://registry.npmjs.org/n8n-nodes-base/-/n8n-nodes-base-2.40.2.tgz . No n8n installation or hosted connection is required for the fixture check. Package installation is maintainer tooling, not a workflow requirement.

## Recorded results

```text
PASS: topology/default-off gate, one-item request bound, query validation, request contract, credential placeholder, no retry/redirect/pagination, fixture rights/degraded preservation, empty/missing fields, malformed envelope.
OFFLINE ONLY: no n8n server import, authenticated search, media fetch, or rights clearance is claimed.
PASS: published HTTP Request parameter schema normalized by n8n-workflow@2.40.1; Header Auth mapping; published node versions Manual Trigger 1, Set 3.4, Code 2, HTTP Request 4.4.
```

## Cost and external effects

Public docs/OpenAPI/pricing, GitHub repository, and npm package reads only. Zero Lightdrift searches and zero new paid commitments/upgrades. No public repository writes, emails, customer data access, production changes, or deployments. Existing infrastructure/model quota usage is not measured by these tests. Fixture output is synthetic and has no commercial-rights meaning.

## Remaining user-side acceptance

Import in your n8n instance, bind your own credential, supply your query, explicitly opt in to one manual request, inspect the returned query ID and account usage, then turn the flag off. Instance-specific permissions, UI behavior, JavaScript runner configuration, and account authentication are not proved here. Rerunning with the flag left true can bill again; this is not an account-wide limiter. Rollback is removal of the example/workflow and any unused dedicated credential; no production rollback is needed.
