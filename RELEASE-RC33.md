# RC33: Claude.ai browser chat

Codelaboon can use the model already available in a signed-in Claude.ai session
as a text provider. A small Firefox add-on carries each prompt from a loopback
bridge to Claude.ai and returns the reply; account cookies and credentials are
never copied into Codelaboon's configuration.

## Setup and use

```bash
codelaboon claude-browser setup
codelaboon claude-browser test
codelaboon chat claude_browser web-default "Explain this function"
```

Setup opens Claude.ai in your default browser and prints the add-on manifest
path. In Firefox, open `about:debugging#/runtime/this-firefox`, choose **Load
Temporary Add-on**, and select the manifest. Firefox removes temporary add-ons
when it restarts. Sign in to Claude.ai normally if needed.

The provider is also available as **Claude.ai (Firefox)** in `codelaboon web`
and as **Claude · Browser default (Firefox)** in native engine model pickers.
The gateway route is `claude_browser/web-default`. Each request starts a new
text conversation and uses the default model of the current session.

## Text-only scope

The browser provider returns text and does not execute engine tools. Native
engines that advertise optional tools continue to work because the gateway
accepts the advertisement without forwarding it; an explicit required tool
choice is rejected with a clear error. Start a new conversation if the previous
one contains tool calls or attachments.

Requests open a Claude.ai tab and return focus to the previous tab when the
prompt is sent in the background. The reply has a 225 second budget after the
add-on connects. Firefox must be signed in and the temporary add-on must be
loaded.

Anthropic's Consumer Terms, section 3 require explicit permission for automated
browser access. Use this provider only if you have that permission.

## Packaging

The wheel now includes the browser add-on manifest, content script and
background script. Release packages also include the updated connector at
version 1.0.33.
