# Lightdrift for Claude

Real images for the things you build. Search Lightdrift by meaning and retrieve hosted image files with natural-language descriptions, content flags, source provenance, and license information.

## Local installation

```sh
claude --plugin-dir /absolute/path/to/lightdrift-claude-plugin
```

Run `/mcp` and authenticate the Lightdrift connection. Use `/lightdrift:find-images` or ask Claude to source images for your project.

## Claude web / desktop connector

In Claude, open Customize → Connectors → Add custom connector. Use `https://lightdrift.ai/mcp`, then sign in to Lightdrift. The custom connector exposes the tools; it does not install this plugin's skill.

## Try it

- Find a landscape photo of a coastal lighthouse at dusk with open sky on the left, then add it to my hero section with its credit.
- Find three real photographs for a presentation about early space exploration. Include source links and required attribution.
- Find a documented photograph of a mola mola for an educational page. Check the subject against the source metadata.

## Tools and costs

| Tool | Function | Cost |
|---|---|---|
| search_images | Semantic image search with filters | Paid; see live tool description |
| find_similar_images | Find images similar to an indexed asset | Paid; see live tool description |
| get_image | Retrieve file URLs and image metadata | Free |

A Lightdrift account and available credit are required for paid searches. This plugin does not include credits or an Anthropic subscription. It uses browser OAuth and contains no API keys, scripts, hooks, or executable dependencies.

## Image rights

Licenses belong to the individual images, not this plugin. Preserve required attribution and source links. Lightdrift reports the source's rights declarations; they are not a blanket clearance for every intended use.

## Privacy and support

The server receives the tool arguments Claude sends, such as search queries, filters, and asset IDs, along with authentication needed to associate calls with your account. Successful searches consume your account's credits. The plugin itself has no separate telemetry or local execution hooks.

- Privacy policy: https://lightdrift.ai/privacy
- Terms: https://lightdrift.ai/terms
- Documentation: https://docs.lightdrift.ai/guides/images-mcp
- Support: jackson@lightdrift.ai

## Publication status

This package is being prepared for submission. It is not yet listed or verified by Anthropic.

## Hosted downloads

Hosted Claude environments must permit outbound access to `api.lightdrift.ai` and the storage URL returned by the download redirect. Search and metadata tools can work even when the session network policy blocks image downloads. Report that restriction accurately; do not bypass it.
