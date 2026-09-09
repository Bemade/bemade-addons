# Spec — `bemade_mail_gateway` (module Odoo)

Module Odoo interne à Bemade. Expose un endpoint HTTP authentifié par token
qui permet à des intégrations (au premier chef [`odoo-mail-gateway`](../README.md))
de pousser des courriels bruts dans Odoo via `mail.thread.message_process`,
**sans consommer une licence d'utilisateur Enterprise**.

**Repository cible** : `git.bemade.org/bemade/bemade_mail_gateway`
**Modules requis** : `base`, `mail`
**Compatibilité** : Odoo 19.0+ (référence ; backport 17/18 si requis, à
évaluer)
**Licence** : AGPL-3.0-or-later

---

## 1. Contexte et objectif

### 1.1 Problème à résoudre

L'intégration [`odoo-mail-gateway`](../README.md) pousse les courriels reçus
par Mailcow vers Odoo via `/jsonrpc/common.authenticate`, ce qui requiert
**un utilisateur réel avec le groupe `base.group_user` (Internal User)**.

En Odoo Enterprise, chaque user `Internal User` actif est facturé
**~30 $ CAD/mois**. Avec N tenants Bemade × 1 bot par tenant, le coût
récurrent grossit linéairement : 5 tenants = 1 800 $/an, 10 tenants =
3 600 $/an, **uniquement pour des comptes "robot"** qui ne reçoivent
aucune valeur opérationnelle des fonctionnalités Enterprise.

Tentatives écartées par l'analyse :

- **Réutiliser `OdooBot` (`__system__`, uid=1)** : Odoo 19 refuse
  explicitement `active = True` sur le superuser (`UserError: You cannot
  activate the superuser`), et la création de clé API en RPC est interdite
  (`_generate` privé, `create()` AccessError).
- **Réutiliser le user `admin`** : risque de blast radius inacceptable —
  une fuite de clé API donne un contrôle total de la base à l'attaquant.
- **Créer un user `Portal`** : ne peut pas appeler `mail.thread.message_process`
  (permissions ORM insuffisantes ; un alias routant vers `helpdesk.ticket`
  ou `crm.lead` requiert des accès qu'un Portal n'a pas).

### 1.2 Solution

Un addon Odoo qui expose `POST /bemade/mail-gateway/process` :

- Authentification par **token partagé** (`X-Bemade-Token: <secret>`)
- Aucun utilisateur Odoo impliqué dans l'auth
- Token validé en **temps constant** (anti-timing-attack)
- L'appel à `message_process` est exécuté côté Odoo avec `SUPERUSER_ID`
  (`env(SUPERUSER_ID)`) — la confiance est **dans le secret du token**,
  pas dans une identité utilisateur

Côté `odoo-mail-gateway`, on remplace la classe `OdooClient` par un
`BemadeGatewayClient` qui POST au nouvel endpoint au lieu de
`/jsonrpc`. ~50 lignes Python, mêmes 3 classes d'erreur typées.

### 1.3 Modèle économique attendu

| Approche | Coût initial | Coût récurrent par tenant |
|---|---|---|
| `MailGatewayBot` (Internal User) | 5 min | ~30 $ CAD/mois |
| Ce module | ~1 jour de dev | **0 $** |

Amortissement : **1 mois sur un seul tenant**. Réutilisable pour toute
future intégration Bemade nécessitant un push sans humain (webhook
inbound, ETL, etc.).

---

## 2. Contraintes techniques

### 2.1 Stack

- **Langage** : Python 3.12+ (Odoo 19 requirement)
- **Framework** : Odoo 19 controllers (`odoo.http.Controller`,
  `@route(type='http', auth='none')`)
- **Stockage des tokens** : modèle Odoo dédié `bemade.mail_gateway.token`
  (pas `ir.config_parameter` — voir §5)
- **Hashing** : `hashlib.sha256` côté token (jamais le token brut en BD)
- **Comparaison** : `hmac.compare_digest` pour éviter les timing attacks
- **Génération de token** : `secrets.token_urlsafe(32)` (256 bits d'entropie)
- **Logging** : logger Odoo standard (`_logger = logging.getLogger(__name__)`)

### 2.2 Sécurité

- **HTTPS obligatoire** — l'endpoint refuse les requêtes en HTTP clair
  (`request.httprequest.is_secure` check, désactivable via setting pour
  les dev locaux).
- **Tokens stockés en clair impossible** : seul le hash sha256 est
  persisté. Le token brut est montré **une seule fois** au moment de la
  création (wizard), comme GitLab/GitHub PATs.
- **Aucun token dans les logs** — un test unitaire dédié vérifie cette
  propriété.
- **Aucun token retourné par l'API** une fois créé (pas de
  `read()` qui expose le hash, pas de `name_search` qui inclut le token).
- **IP allowlist optionnelle** par token (CIDR), V2.
- **Rate limiting** — V2 (s'appuyer sur `ir.http`'s rate limiter ou un
  middleware externe type `fail2ban` si nécessaire).
- **Audit** : chaque appel persiste la date d'utilisation et l'IP source
  sur le record token.

### 2.3 Performance

- Cible latence P95 endpoint → ACK : **< 200 ms** pour un mail de 50 KB
  Odoo répondant normalement (le coût marginal vs. `/jsonrpc` est
  négligeable, on évite juste un round-trip d'authentification).
- Idempotence : héritée de `message_process` (déduplication sur
  Message-Id côté Odoo).

---

## 3. Architecture

### 3.1 Flux nominal

```
┌────────────────────┐                         ┌──────────────────────┐
│ odoo-mail-gateway  │  POST /bemade/mail-     │  Odoo (this module)  │
│ (LMTP sidecar)     │  gateway/process        │                      │
│                    │  X-Bemade-Token: …      │  controller          │
│ BemadeGatewayClient├────────────────────────▶│   ↓ validate token   │
│                    │  body: raw RFC 5322     │   ↓ env(SUPERUSER)   │
│                    │                         │   ↓ message_process  │
│                    │◀────────────────────────┤  → JSON response     │
│                    │  200 {"ok":true,...}    │                      │
└────────────────────┘                         └──────────────────────┘
```

### 3.2 Composants internes

- **`bemade.mail_gateway.token`** (modèle) — stocke les tokens (hashés),
  leur métadonnées (label, IPs autorisées, date d'expiration optionnelle,
  date de dernière utilisation).
- **`MailGatewayController`** (controller HTTP) — route `/bemade/mail-gateway/*`,
  valide le token, dispatche.
- **`bemade.mail_gateway.token.create.wizard`** (wizard) — génère un nouveau
  token, l'affiche **une fois** à l'admin, ne le re-stocke jamais en clair.
- **`group_bemade_mail_gateway_admin`** (groupe de sécurité) — seul ce
  groupe peut créer/révoquer des tokens. Interface non visible aux autres
  utilisateurs.

### 3.3 Choix : SUPERUSER_ID vs un user technique côté Odoo

Le code du controller exécute `env(user=SUPERUSER_ID).['mail.thread'].message_process(...)`.

**Pourquoi SUPERUSER plutôt qu'un user technique non-Internal-User** :

- Un user technique non-Internal-User (Portal, ou groupes custom) ne peut
  pas appeler `message_process` — les access rules `mail.thread` exigent
  Internal User. On retomberait dans le problème de licence.
- Élever en SUPERUSER **après validation explicite du token** est un
  pattern défensible : la confiance est ancrée dans le secret cryptographique,
  pas dans une identité réutilisable.
- C'est le même pattern que les **scheduled actions Odoo**, qui tournent
  toutes en SUPERUSER après validation que le cron est légitime.

Risque assumé : si un attaquant met la main sur un token, il a effectivement
accès SUPERUSER pour `message_process`. Mitigation :
- Token rotatable en 1 clic (UI)
- Audit (date + IP)
- Allowlist IP (V2)
- Le scope du controller est **uniquement** `message_process`, pas un
  `execute_kw` générique → l'attaquant ne peut que créer des messages,
  pas modifier la BD librement.

### 3.4 Endpoint API

#### `POST /bemade/mail-gateway/process`

**Headers** :

| Header | Requis | Description |
|---|---|---|
| `X-Bemade-Token` | oui | Token authentifiant l'intégration |
| `Content-Type` | oui | `message/rfc822` ou `text/plain` |
| `X-Bemade-Sender` | non | Override du sender (sinon parsé du `From:`) |
| `X-Bemade-Save-Original` | non | `1`/`0`, default `0` |
| `X-Bemade-Strip-Attachments` | non | `1`/`0`, default `0` |

**Body** : message brut RFC 5322 (texte ou bytes).

**Réponses** :

| HTTP | Body JSON | Cas |
|---|---|---|
| `200` | `{"ok":true,"result":<id>,"model":"<model>","message_id":"<rfc>"}` | Record créé ou alias résolu |
| `400` | `{"ok":false,"error":"bad_request","detail":"..."}` | Body manquant / non parsable |
| `401` | `{"ok":false,"error":"unauthorized"}` | Token absent, invalide ou expiré |
| `403` | `{"ok":false,"error":"forbidden","detail":"ip_not_allowed"}` | IP source pas dans la allowlist du token (V2) |
| `422` | `{"ok":false,"error":"no_route","detail":"..."}` | Pas d'alias correspondant côté Odoo |
| `500` | `{"ok":false,"error":"internal","detail":"..."}` | Erreur ORM inattendue |
| `503` | `{"ok":false,"error":"unavailable"}` | Module en maintenance (V2) |

#### `GET /bemade/mail-gateway/health`

Healthcheck non-authentifié.

```json
{"ok": true, "module_version": "1.0.0", "odoo_version": "19.0"}
```

Toujours `200`. Utilisé par les load balancers et par `odoo-mail-gateway`
pour son `/ready` endpoint.

#### `POST /bemade/mail-gateway/check`

Authentifié, sans side-effect. Permet à un client de tester un token sans
envoyer de mail.

```json
// 200 si token valide
{"ok": true, "token_label": "omg-sugar"}
// 401 sinon
{"ok": false, "error": "unauthorized"}
```

---

## 4. Modèle de données

### 4.1 `bemade.mail_gateway.token`

| Champ | Type | Description |
|---|---|---|
| `id` | int | PK |
| `name` | char (required) | Label humain (ex: `omg-sugar`, `omg-pneumac`) |
| `description` | text | Notes libres |
| `token_hash` | char(64) (required, indexed, readonly) | sha256 hex du token |
| `active` | bool (default True) | Désactivable sans suppression |
| `created_at` | datetime (readonly) | Date de création |
| `created_by_uid` | many2one(res.users) (readonly) | User qui a créé |
| `expires_at` | datetime (optional) | NULL = jamais |
| `last_used_at` | datetime (readonly) | Mis à jour à chaque appel valide |
| `last_used_ip` | char(45) (readonly) | IPv4 ou IPv6 |
| `use_count` | int (readonly, default 0) | Compteur d'usages |
| `allowed_ips` | char (optional, V2) | CIDR list comma-separated |

**Contraintes** :

- `_sql_constraints = [('token_hash_unique', 'unique(token_hash)', '...')]`
- `name` unique aussi (cohérence UI)

**Méthodes** :

- `@api.model action_generate_token()` → ouvre le wizard de création
- `validate_token(token: str, ip: str) -> Self | None` (cls method) —
  hash + recherche en temps constant + check expiration + check IP allowlist
  + update du `last_used_*`. Retourne le record validé ou `None`.
- `action_revoke()` → set `active = False`

### 4.2 `bemade.mail_gateway.token.create.wizard` (Transient)

| Champ | Type | Description |
|---|---|---|
| `name` | char (required) | Label du token à créer |
| `expires_at` | datetime (optional) | Expiration |
| `generated_token` | char (readonly, transient) | Affiché une fois |

Bouton **Generate** :
1. Vérifie l'unicité du `name`
2. `token = secrets.token_urlsafe(32)` (256 bits)
3. `token_hash = sha256(token).hexdigest()`
4. `bemade.mail_gateway.token.create({'name':..., 'token_hash':...})`
5. `self.generated_token = token` (transient → disparaît à la fermeture du wizard)
6. Renvoie une vue qui affiche le token avec copy-button et un avertissement
   "**This is the only time you will see this token. Save it now.**"

### 4.3 Sécurité ACL

- `group_bemade_mail_gateway_admin` (créé par le module) — seul groupe
  ayant CRUD sur `bemade.mail_gateway.token`
- L'endpoint controller (`auth='none'`) ne traverse **aucune ACL** Odoo —
  il s'appuie uniquement sur la validation du token

---

## 5. Sécurité — détails

### 5.1 Pourquoi `bemade.mail_gateway.token` (modèle dédié) plutôt que `ir.config_parameter`

- `ir.config_parameter` n'a pas de hash natif — on stockerait le token en
  clair, lisible par tout user `base.group_system`
- Pas d'audit (date d'utilisation, compteur, IP)
- Pas de rotation en place (il faut écraser la valeur)
- Liste de tokens difficile (clés serialisées dans une string)

### 5.2 Validation en temps constant

```python
import hmac, hashlib
def validate_token(self, raw_token: str, ip: str) -> Optional[Self]:
    if not raw_token:
        return None
    h = hashlib.sha256(raw_token.encode()).hexdigest()
    # Récupère TOUS les tokens actifs et compare en temps constant
    for tok in self.search([('active', '=', True)]):
        if hmac.compare_digest(tok.token_hash, h):
            if tok.expires_at and tok.expires_at < fields.Datetime.now():
                return None
            tok.sudo().write({
                'last_used_at': fields.Datetime.now(),
                'last_used_ip': ip[:45],
                'use_count': tok.use_count + 1,
            })
            return tok
    return None
```

Note : itérer sur tous les tokens actifs ne scale pas indéfiniment, mais
pour un déploiement Bemade typique (< 50 tokens par DB), c'est trivial.
Si nécessaire, V2 : indexer sur `token_hash` (déjà prévu) + lookup direct
(perd un peu de la garantie temps-constant mais reste acceptable vu que
le hash est non-réversible).

### 5.3 Tests obligatoires côté sécurité

- Aucun token brut ne doit apparaître dans `mail.message`, `ir.logging`,
  ou `_logger.info/.warning/.error/.debug` calls
- Le `token_hash` ne doit pas être exposé via `read()` aux non-admins
- Les wizards `name_search` ne doivent pas inclure le hash
- L'endpoint refuse HTTP non-TLS sauf si setting `bemade_mail_gateway.allow_http = True` (dev only)

---

## 6. Module Odoo — structure de fichiers

```
bemade_mail_gateway/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── mail_gateway.py             # endpoints HTTP
├── models/
│   ├── __init__.py
│   └── bemade_mail_gateway_token.py
├── wizards/
│   ├── __init__.py
│   └── token_create_wizard.py
├── views/
│   ├── token_views.xml             # form, list, search
│   ├── menus.xml
│   └── wizard_views.xml
├── security/
│   ├── ir.model.access.csv
│   └── security.xml                # group_bemade_mail_gateway_admin
├── data/
│   └── (vide en V1)
├── tests/
│   ├── __init__.py
│   ├── test_token_model.py
│   ├── test_controller.py
│   ├── test_security_redaction.py
│   └── fixtures/
│       └── sample_message.eml
├── README.md
├── LICENSE                          # AGPL-3.0
└── i18n/
    └── (en, fr_CA générés ultérieurement)
```

### 6.1 `__manifest__.py`

```python
{
    "name": "Bemade Mail Gateway Endpoint",
    "version": "19.0.1.0.0",
    "category": "Tools",
    "summary": "Token-authenticated HTTP endpoint to push raw mail into Odoo "
               "without consuming a user license.",
    "author": "Bemade Inc.",
    "website": "https://git.bemade.org/bemade/bemade_mail_gateway",
    "license": "AGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/token_views.xml",
        "views/wizard_views.xml",
        "views/menus.xml",
    ],
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
}
```

---

## 7. Tests

### 7.1 Modèle (`test_token_model.py`)

- Generation : `token_urlsafe(32)` → 43+ chars, hash unique
- Hash : sha256 cohérent, jamais le token en BD
- Validate : token correct → record retourné + `last_used_*` mis à jour
- Validate : token incorrect → `None`
- Validate : token expiré → `None`
- Validate : token désactivé (`active=False`) → `None`
- Constant-time : timing pour bons vs. mauvais tokens reste indistinguable
  (test statistique léger, ou simplement vérifier que `hmac.compare_digest`
  est bien utilisé)
- Revoke : `active=False`, le token ne valide plus

### 7.2 Controller (`test_controller.py`)

Avec `HttpCase` :

- POST sans token → `401`
- POST avec token invalide → `401`
- POST avec token valide + alias inexistant → `422` `no_route`
- POST avec token valide + alias existant → `200` `ok=True` + record créé
- POST avec body malformé → `400`
- POST en HTTP clair (sans `is_secure`) avec setting strict → `403`
- POST en HTTP clair avec setting permissif → `200`
- GET `/health` → `200`
- POST `/check` avec token valide → `200`
- POST `/check` avec token invalide → `401`

### 7.3 Sécurité (`test_security_redaction.py`)

- Caplog sur tous les loggers du module → aucun token brut n'apparaît
- `read([token_id], ['token_hash'])` en tant que user non-admin → AccessError
- `name_search('test-token-')` ne renvoie pas le hash

### 7.4 Coverage cible

- Modèle : 100 %
- Controller : > 90 %
- Sécurité : tests critiques tous présents (pas de gate de coverage)

---

## 8. Intégration avec `odoo-mail-gateway`

### 8.1 Côté `odoo-mail-gateway`

Nouveau client `BemadeGatewayClient` parallèle à `OdooClient`, sélectionné
par config :

```yaml
# config.yml
targets:
  durpro_prod:
    url: https://odoo.durpro.com
    auth_mode: bemade_token       # nouveau, default reste 'jsonrpc'
    token_env: DURPRO_PROD_TOKEN  # remplace api_key_env
    timeout: 30
```

`BemadeGatewayClient.message_process(raw)` :

```python
async def message_process(self, raw: bytes | str, **kwargs) -> Any:
    headers = {
        "X-Bemade-Token": self._target.token.get_secret_value(),
        "Content-Type": "message/rfc822",
    }
    if kwargs.get("save_original"):
        headers["X-Bemade-Save-Original"] = "1"
    if kwargs.get("strip_attachments"):
        headers["X-Bemade-Strip-Attachments"] = "1"
    body = raw if isinstance(raw, bytes) else raw.encode("utf-8")
    response = await self._client.post(
        "/bemade/mail-gateway/process", content=body, headers=headers
    )
    # Map HTTP status → 3 typed exceptions, identique à OdooClient
    ...
```

Mapping erreurs → exceptions identiques à `OdooClient` (Auth/Transient/Permanent),
donc `LMTPHandler` et la couche tests ne changent **pas**.

### 8.2 Migration tenant par tenant

1. Installer `bemade_mail_gateway` sur l'Odoo cible
2. Créer un token via Settings → Bemade → Mail Gateway Tokens → Generate
3. Mettre le token dans le `.env` du LXC (variable `DURPRO_PROD_TOKEN`)
4. Modifier `config.yml` du tenant : `auth_mode: bemade_token`,
   `token_env: DURPRO_PROD_TOKEN`
5. Redémarrer le sidecar
6. Désactiver/supprimer `MailGatewayBot` côté Odoo (économie facturation)

---

## 9. Hors scope (V1)

- **IP allowlist par token** (V2 — champ `allowed_ips` déjà au schéma)
- **Rate limiting au niveau du module** (V2 — pour V1, s'appuyer sur le
  load balancer / `fail2ban` si nécessaire)
- **Multi-DB par token** (V2 — un token est lié à une DB Odoo)
- **Webhook outbound** vers la gateway (notifications de back-pressure)
- **Auth alternative** (mTLS, OAuth, JWT) — token suffit pour le MVP
- **Mass-revoke** (V2 — UI bouton "rotate all")
- **Délégation utilisateur** (impersonification d'un user spécifique pour
  ce mail) — V2, utile pour préserver `mail.message.author_id`

---

## 10. Plan d'implémentation

Découpage en commits atomiques :

1. **Squelette** : `__manifest__.py`, structure dossiers, README, LICENSE,
   sécurité de base (`group_bemade_mail_gateway_admin`).
2. **Modèle `bemade.mail_gateway.token`** + tests unitaires `test_token_model.py`
   (génération, hash, validate, revoke). Coverage 100 %.
3. **Wizard de création** + vue qui affiche le token brut une fois.
4. **Vues admin** (form/list/search) + menu sous Settings.
5. **Controller `MailGatewayController`** : `/process`, `/check`, `/health`
   + tests `HttpCase`.
6. **Tests sécurité** (`test_security_redaction.py`) — token jamais loggé,
   ACL respectées.
7. **Documentation** : README avec exemple cURL, intégration
   `odoo-mail-gateway`, procédure de rotation.
8. **CI GitLab** pour le module : `lint` (flake8/ruff) + `test` Odoo
   (tournée dans le runner Bemade-Odoo CI).

À chaque étape : `pylint-odoo` + tests verts avant commit.

---

## 11. Critères d'acceptation

- [ ] Module installe proprement sur Odoo 19 (`./odoo-bin -i bemade_mail_gateway -d <db>`)
- [ ] Un membre du groupe `bemade_mail_gateway_admin` peut créer un token via
      l'UI ; non-membres ne voient pas le menu
- [ ] Le token brut est affiché **une fois** dans le wizard, plus jamais après
- [ ] `POST /bemade/mail-gateway/process` avec token valide + alias existant
      crée un `mail.message` (vérifié par test `HttpCase`)
- [ ] `POST` avec token invalide retourne `401` et le temps de réponse ne
      diffère pas significativement du cas token valide (mesuré par test)
- [ ] Aucun token brut dans aucun log (`ir.logging`, stdout, fichiers
      d'application Odoo) — vérifié par `caplog`-style test
- [ ] Tests : modèle 100 %, controller > 90 %, security tests présents
- [ ] README documente :
      - Installation
      - Création/rotation/révocation de token
      - Intégration `odoo-mail-gateway` (snippet `config.yml` + curl
        d'exemple)
      - Liste des codes HTTP retournés
- [ ] CI GitLab verte sur main + tags

---

## 12. Réflexions ouvertes

- **Faut-il limiter le scope du token à `message_process` uniquement, ou
  prévoir d'autres "actions" sous le même endpoint** (ex: `/bemade/mail-gateway/notify`,
  `/bemade/mail-gateway/attachment`) ? V1 : strictement `message_process`.
  Si un autre besoin émerge, on créera un nouveau controller plutôt que
  d'élargir celui-là.
- **Faut-il supporter la signature HMAC du body** (pas juste un token
  bearer) pour aussi authentifier l'**intégrité** du payload ? Probablement
  V2 si on craint des MITM (peu probable sur réseau interne TLS).
- **Module générique `bemade_token_endpoint`** dont `bemade_mail_gateway`
  serait un plug-in ? Tentant pour l'avenir, mais YAGNI en V1 — quand un
  2e endpoint apparaîtra, refactorer.
