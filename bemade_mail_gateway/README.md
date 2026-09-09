# bemade_mail_gateway

Token-authenticated HTTP endpoint that lets external mail relays push raw
RFC 5322 messages into Odoo via `mail.thread.message_process` **without
consuming an Internal User license**.

Companion to [`odoo-mail-gateway`](https://git.bemade.org/bemade/odoo-mail-gateway)
(the LMTP sidecar deployed next to Mailcow), but usable by any HTTP
client.

## Why

Odoo Enterprise bills every active `Internal User` (~30 $ CAD/month). A
mail-bot user per tenant becomes ~30 × N $/month for no business value —
the bot is a robot, not a person. This module replaces user-API-key
authentication with a hashed shared-secret **token** managed under
*Settings → Bemade → Mail Gateway*, validated in a custom HTTP
controller, and elevated to `SUPERUSER_ID` only for the scoped
`message_process` call.

See [`docs/SPEC.md`](docs/SPEC.md) for the full design (architecture,
threat model, data model, hors-scope, acceptance criteria).

## Installation

```bash
# In your Odoo addons path
git clone git@git.bemade.org:bemade/bemade_mail_gateway.git
# Restart Odoo, then install via UI (Apps → search "Bemade Mail
# Gateway" → Install) or CLI:
odoo-bin -i bemade_mail_gateway -d <db>
```

The module depends only on `base` and `mail` (no Enterprise modules).

## Quick start

### 1. Generate a token

1. Log in to Odoo as a user member of **Bemade Mail Gateway Administrator**
   (auto-created at install; implies `Settings`).
2. Navigate to *Settings → Bemade → Mail Gateway → Generate Token*.
3. Enter a label (e.g. `omg-sugar`), optionally an expiration date.
4. Click **Generate**.
5. **Copy the displayed token immediately** — it is shown exactly once.
   Once you close the dialog the raw value is gone forever; only the
   sha256 hash remains in the database. If you lose it, generate a new
   one and retire the old.

### 2. Push a message

```bash
TOKEN='<the-token-shown-once>'
curl -sS -X POST \
  -H "X-Bemade-Token: $TOKEN" \
  -H "Content-Type: message/rfc822" \
  --data-binary @- \
  https://odoo.example.com/bemade/mail-gateway/process <<'EOF'
From: customer@example.com
To: support@example.com
Subject: I need help
Message-Id: <abc123@example.com>

Hello, the printer is on fire again.
EOF
```

Success response (HTTP 200):

```json
{"ok": true, "result": 42, "message_id": "<abc123@example.com>"}
```

### 3. Verify a token without side-effects

```bash
curl -sS -X POST \
  -H "X-Bemade-Token: $TOKEN" \
  https://odoo.example.com/bemade/mail-gateway/check
# {"ok": true, "token_label": "omg-sugar"}
```

### 4. Liveness probe

```bash
curl -sS https://odoo.example.com/bemade/mail-gateway/health
# {"ok": true, "module_version": "19.0.1.0.0", "odoo_version": "19.0.0"}
```

## API reference

### `POST /bemade/mail-gateway/process`

**Headers**

| Header                       | Required | Description                                            |
|------------------------------|----------|--------------------------------------------------------|
| `X-Bemade-Token`             | yes      | The shared secret                                      |
| `Content-Type`               | yes      | `message/rfc822` or `text/plain`                       |
| `X-Bemade-Save-Original`     | no       | `1` to save the original message (default `0`)         |
| `X-Bemade-Strip-Attachments` | no       | `1` to drop attachments before processing (default `0`)|

**Body** — raw RFC 5322 message (bytes preferred).

**Responses**

| Status | Body                                                           | Meaning                                                |
|--------|----------------------------------------------------------------|--------------------------------------------------------|
| 200    | `{"ok":true,"result":<id>,"message_id":"<rfc>"}`               | Record created or alias resolved                        |
| 400    | `{"ok":false,"error":"bad_request","detail":"..."}`            | Empty body / unparseable                                |
| 401    | `{"ok":false,"error":"unauthorized"}`                          | Token absent, invalid, expired or revoked               |
| 403    | `{"ok":false,"error":"forbidden","detail":"HTTPS required"}`   | Plain HTTP (override with `bemade_mail_gateway.allow_http=True`) |
| 422    | `{"ok":false,"error":"no_route","detail":"..."}`               | No `mail.alias` matches the recipient                   |
| 500    | `{"ok":false,"error":"internal","detail":"..."}`               | Unexpected ORM exception                                |

### `POST /bemade/mail-gateway/check`

Same auth as `/process`. Returns 200 with the token label on success,
401 otherwise. No state mutation — useful for clients to verify a
credential after rotation.

### `GET /bemade/mail-gateway/health`

Unauthenticated. Returns 200 with module + Odoo version. Use it for
load-balancer healthchecks and as a smoke test from monitoring tools.

## Token rotation

Rotation is a 4-step procedure:

1. **Generate** a new token via the wizard. Note the new value.
2. **Update** the consumer (e.g. `odoo-mail-gateway`'s `.env`) with the
   new token. Restart it.
3. **Verify** the consumer is using the new token via the `last_used_at`
   on the new token record (it should advance) AND on the old token
   record (it should stop advancing).
4. **Revoke** the old token via the *Revoke* button on its form.

`mail.thread.message_process` is idempotent on `Message-Id`, so even
if the consumer briefly retries with both old and new tokens during
the cutover, no duplicate records appear.

## Integration with `odoo-mail-gateway`

In `config.yml` of the LMTP sidecar:

```yaml
targets:
  sugar_diverse:
    url: https://sugar.diverse-cite.com
    auth_mode: bemade_token         # instead of the default jsonrpc
    token_env: SUGAR_DIVERSE_TOKEN  # env var holding the raw token
    timeout: 30
```

In the sidecar's `.env`:

```ini
SUGAR_DIVERSE_TOKEN=<the-token-from-the-wizard>
```

The sidecar's `BemadeGatewayClient` POSTs the raw LMTP body to
`/bemade/mail-gateway/process`, surfacing 401 → `OdooAuthError`,
422/500/connection-failures → `OdooTransientError` (Postfix retries),
400 → `OdooPermanentError` (Postfix bounces).

See `odoo-mail-gateway` SPEC §8 for the full migration recipe per
tenant.

## Security model

- Tokens stored as **sha256 hex digests only**. The raw value lives
  exclusively in the operator's clipboard / password manager.
- Validation uses [`hmac.compare_digest`](https://docs.python.org/3/library/hmac.html#hmac.compare_digest)
  in a **constant-time loop over all active candidates** — timing
  cannot reveal whether any token matched.
- HTTPS enforced by default; override via
  `bemade_mail_gateway.allow_http=True` (only for dev / CI).
- Only `group_bemade_mail_gateway_admin` (which implies
  `base.group_system`) can create, read, modify or revoke tokens. The
  controller bypasses ACL only for the validation lookup itself
  (auth='none' + sudo) — every other access path goes through the
  group.
- Raw tokens **never logged**, including at DEBUG level. Verified by a
  dedicated test suite that captures every LogRecord and asserts
  absence.
- The blast radius if a token leaks is bounded by what `message_process`
  can do — i.e. create/post messages on `mail.thread`-inheriting models
  via existing aliases. The endpoint does **not** expose a generic
  `execute_kw` escape hatch.

## Troubleshooting

| Symptom                                                     | Likely cause                                       | Fix                                                                 |
|-------------------------------------------------------------|----------------------------------------------------|---------------------------------------------------------------------|
| 401 with a freshly-generated token                          | Wrong header name (must be `X-Bemade-Token`)       | Check the case-insensitive but exact header                         |
| 401 after some uptime                                       | Token expired or revoked                           | Check `expires_at` / `active` in the token form view                |
| 403 "HTTPS required"                                        | Hitting the endpoint over plain HTTP               | Use HTTPS, or temporarily set `bemade_mail_gateway.allow_http=True` |
| 422 `no_route`                                              | No `mail.alias` matches the `To:` address          | Create an alias under *Settings → Technical → Email → Aliases*      |
| 500 with a stack about a missing model                      | Module installed in wrong DB or missing dependency | Reinstall the module; check `mail` is installed                     |
| Token works but `last_used_at` stays empty                  | Caching layer (Cloudflare etc.) is intercepting    | Confirm requests reach Odoo via `docker logs odoo`                  |

## Development

```bash
# Run the test suite (requires a working Odoo dev setup)
odoo-bin -d test_db -i bemade_mail_gateway --test-enable --stop-after-init \
    --log-level=test --test-tags=bemade_mail_gateway
```

Module tests are tagged `bemade_mail_gateway` so you can run only this
module's suite in a shared DB.

## License

[AGPL-3.0-or-later](LICENSE).
