# 13 · Security

Four separate mechanisms, each solving a different problem.

---

## 1 · Passwords: hashing

**The problem.** If DevPulse stored passwords as text, anyone who obtained the
database would have every user's password — and, because people reuse passwords,
their other accounts too.

**Hashing** is a one-way transformation. From the password you can compute the
hash; from the hash you cannot recover the password.

```python
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())
```

Login never compares passwords. It hashes what you typed and compares *hashes*.

### Why bcrypt and not SHA-256

This is the point most people get wrong.

SHA-256 is a fine hash — and **completely inappropriate here**, because it is
*fast*. A modern GPU computes billions of SHA-256 hashes per second, so an
attacker with a stolen database can test every common password in minutes.

bcrypt is **deliberately slow** — milliseconds per hash. That barely matters for
a login, and it makes brute force impractical. **The slowness is the entire
defence.** A fast hash is the wrong tool precisely because it is fast.

### Salt

`bcrypt.gensalt()` generates random bytes mixed into each hash. So:

```text
hash_password("hunter2")  →  $2b$12$K3f...   (different every time)
hash_password("hunter2")  →  $2b$12$9xQ...
```

Two users with the same password get different hashes. Without salt an attacker
could precompute hashes for common passwords once and crack every database at a
glance ("rainbow tables"), and identical hashes would reveal who shares a
password.

### The 72-byte rule

bcrypt silently ignores anything past 72 bytes. A 100-character passphrase would
be **truncated without warning** — the user believes it is strong, and only the
first 72 bytes are checked.

DevPulse rejects rather than truncates:

```python
if len(encoded) > MAX_PASSWORD_BYTES:
    raise ValueError("Password must be at most 72 bytes; bcrypt would "
                     "silently ignore anything beyond that.")
```

### Failing closed

```python
except ValueError:
    return False
```

A corrupt stored hash denies access. It does not raise into the request handler,
which could leak a stack trace or behave unpredictably.

---

## 2 · Sessions: JWTs

**The problem.** HTTP is stateless — every request arrives with no memory of the
last. Re-sending a password each time would be terrible.

A **JWT** (JSON Web Token) is a signed note the server issues at login and the
client presents afterwards:

```text
eyJhbGciOiJIUzI1NiJ9  .  eyJzdWIiOiI0MiIsImV4cCI6MTc...  .  4f3a9c...
      header                      payload                   signature
```

The signature is computed from the header, payload and a **secret key only the
server knows**. Change any character and the signature stops matching.

### Signed, not encrypted

This is the critical property.

Anyone can base64-decode a JWT and read the payload. The signature prevents
*modification*, not *reading*. So a JWT must **never carry a secret**.

DevPulse's payload is exactly three claims:

```python
payload = {
    "sub": str(user_id),                                      # who
    "exp": datetime.now(timezone.utc) + timedelta(...),        # until when
    "iat": datetime.now(timezone.utc),                         # issued when
}
```

No email, no name, no role. A test asserts the claim set is exactly
`{sub, exp, iat}`, so nothing can be added carelessly later.

### Verification, and why it re-reads the user

```python
user_id = decode_access_token(credentials.credentials)
user = db.query(User).filter(User.id == user_id).first()
if user is None or not user.is_active:
    raise _UNAUTHENTICATED
```

Checking the signature alone would keep honouring a token for a **deleted or
deactivated account** until it expired — twelve hours of access for someone who
was removed. So the user is re-loaded and re-checked on every request.

Two tests cover exactly this.

### Not revealing which check failed

```python
if user is None or not user.is_active or not verify_password(...):
    raise HTTPException(401, detail="Incorrect email or password.")
```

One message for every failure. Distinguishing "no such account" from "wrong
password" turns the login form into an **account enumeration tool** — try ten
thousand emails, keep the ones that say "wrong password", and you know who is
registered.

A test asserts both failures produce an identical status and body.

---

## 3 · Webhooks: HMAC signatures

**The problem.** `POST /api/webhooks/github` is a public URL. Anyone can send it
anything. Without verification, anyone could invent deployments and pull
requests — **every metric in DevPulse would be forgeable**.

GitHub signs each delivery using a shared secret. DevPulse recomputes the
signature and compares.

```python
expected = hmac.new(secret.encode(), msg=raw_body, digestmod=hashlib.sha256).hexdigest()
return hmac.compare_digest(expected, provided)
```

Since only GitHub and DevPulse know the secret, a matching signature proves both
origin and that the payload was not altered in transit.

### The raw body

The signature covers the **exact bytes** GitHub sent. Parsing the JSON and
re-serialising it produces equivalent JSON with possibly different spacing or key
order — and a different signature. So the body is read raw, before parsing.

### Timing-safe comparison

`hmac.compare_digest` instead of `==`, and this is subtle but real.

`==` returns as soon as it finds a difference. Comparing a signature that is
wrong in the first character is *marginally faster* than one wrong in the last.
Measure enough attempts and you can determine the correct signature **one
character at a time** — a timing attack.

`compare_digest` always takes the same time regardless of where the difference
is.

### Refusing when unconfigured

```python
if not settings.github_webhook_secret or settings.github_webhook_secret == "change_me":
    raise HTTPException(503, "Webhooks are not configured.")
```

With no secret, **refuse**. Accepting unverified payloads would be worse than
being unavailable.

---

## 4 · CORS

**The problem.** Browsers let any page make requests. If you are signed into
DevPulse and visit a malicious site, that site's JavaScript could call the
DevPulse API using your session.

**CORS** (Cross-Origin Resource Sharing) is the browser asking the server which
origins are allowed.

The MVP had `allow_origins=["*"]` — any website. That is fine for an API with no
authentication and dangerous the moment there is one.

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=settings.cors_origins != "*",
    ...
)
```

Now configurable, and `CORS_ORIGINS=http://localhost:5173` is set once auth is
enabled. Note `allow_credentials` is only true when origins are narrowed —
browsers reject the combination of wildcard origins and credentials, and rightly.

---

## Secrets hygiene

- `backend/.env` holds real secrets; it is gitignored, untracked, and has
  **never appeared in git history** (verified during the Stage 0 audit).
- `backend/.env.example` documents every variable with placeholder values only.
- `.dockerignore` keeps `.env` out of built images, because images get pushed to
  registries.
- `SECRET_KEY` ships as an obviously-invalid default, with the generation
  command in `.env.example`.
- No token is ever logged. The auth middleware logs the *email* on a failed
  login, never the password or token.

---

## Auth is opt-in, and why

`AUTH_ENABLED` defaults to **false**.

A local single-user install should not be forced through a login it does not
need, and a tool that demands a password before showing anything gets abandoned
during evaluation. One variable turns it on, and `.env.example` states plainly
that it must be on before exposing DevPulse beyond localhost.

## Router-level enforcement

Covered in chapter 03, repeated because it is the highest-leverage decision:

```python
for _router in (...ten data routers...):
    app.include_router(_router, dependencies=[Depends(current_user)])
```

Per-handler dependencies are **how auth holes appear** — someone adds an
endpoint and forgets. Declared once, a new route is protected by default.

A test walks eight endpoints and asserts 401 on each.

---

## What is not done

- **No rate limiting.** A determined attacker can try passwords as fast as
  bcrypt allows. bcrypt's slowness is meaningful mitigation, but real rate
  limiting is missing.
- **No refresh tokens.** Tokens last 12 hours, then you sign in again.
- **No roles.** Every authenticated user sees everything.
- **No password reset.** There is no email delivery.
- **Single owner account.** Registration closes after the first account; there
  is no invite flow.

These are honest gaps, not oversights — each is a deliberate scope decision
recorded in ADR-027.

---

**Next:** [14 · Defending the project](14-defending-the-project.md)
