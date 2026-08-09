# Privacy and model choice

**Uriel offers model suggestions but endorses no model, provider, hosting company, or data policy.** Capability, price, access, retention, and terms change. The project owner is responsible for deciding whether a tool is authorized for the material being processed.

## Decision order

1. Can the task be completed by Uriel Core or a human without exporting content?
2. Can the task be reduced to public metadata, hashes, one sanitized claim, or one non-sensitive source?
3. Can an offline model on controlled hardware do it?
4. Is there an institutionally approved provider and account type for this data class?
5. Only then consider a general web or free endpoint.

## Classification guidance

| Classification | Default Uriel position | Suggested route |
|---|---|---|
| public | optional external review permitted by policy | any reviewed provider; verify all output |
| internal | acknowledgement and minimization | local model or approved business account |
| confidential | redact by default; external export exceptional | verified offline model or formally approved provider |
| restricted | external AI normally denied | isolated offline environment plus governing authorization |

Edit `privacy.classification` and `privacy.external_ai` in `uriel.project.json`. Set `external_ai` to `deny` when policy forbids remote use.

## “Offline” verification checklist

A downloaded model is not enough. Check that the runtime:

- binds only to localhost or no socket;
- does not send telemetry;
- does not use cloud embeddings, search, moderation, fallback, or tool servers;
- does not auto-share sessions;
- stores chats and model caches where expected;
- has encrypted storage and appropriate user permissions;
- is patched and obtained from a verifiable source;
- is licensed for the intended use.

## Free endpoints

Free endpoints can be excellent for public, bounded tasks and can make serious research assistance available to people without money. They may also have small usage pools, changing availability, queues, or data-use exceptions. Treat “free” as a price property, not a privacy property.

Use bursts: one claim or source per session, preserve the response, verify locally, and import only the structured review record.

## Provider terms are live policy

Before every sensitive deployment, consult the chosen provider's current
official data controls, retention terms, training-use terms, endpoint-specific
state behavior, account-tier controls, and institutional agreement. Record the
review date and authorization outside the public project. A model name,
consumer privacy toggle, temporary-chat feature, or old documentation snapshot
does not establish that a deployment is approved for regulated or restricted
material. Uriel deliberately does not freeze retention periods in this guide.

## External AI Agents & Adapters

External AI agents can call many providers or local models. The selected provider and hosting environment determine important data behavior. Review your provider's current data controls and privacy terms before processing sensitive research material.
