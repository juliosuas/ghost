# Plan: Ghost hardening (OSS local tool)

**Deadline:** viernes 25 sep 2026, fin de día (America/Lima o UTC; si no hay merge, kill parcial).
**Repo inspeccionado:** `https://github.com/juliosuas/ghost` · `main` @ `22ef1c2` (2026-09-21).
**Tesis de la empresa:** Express (Tu Web Ideal). Ghost es side project. Fairway no se toca.

Este archivo es el único entregable de planning. No implementa código. No abre PRs de app.

---

## 0. Veredicto (Richard)

Ghost es **viable SÍ**, y **solo** como herramienta **OSS local** de self-audit / case-file:

- CLI + SQLite + reporte con provenance + `ghost doctor`.
- API Flask **local** (bind loopback + token), no producto hosted.

Ghost **NO** es:

- producto de incubator
- SaaS
- marketplace
- waitlist
- “AI Platform”
- competencia de Express

**Scope máximo esta semana (nada más):**

1. README honesto (cortar marketing de AI Platform)
2. `ghost doctor` FAIL en defaults inseguros (secret / host / token)
3. Contrato de provenance para el reporte de self-audit
4. `darkweb` / `social` experimental y **off-by-default**
5. Auth API + bind `127.0.0.1` + Docker non-root
6. Unificar `pyproject.toml` vs `requirements.txt` **solo si sobra tiempo**

Express **no está bloqueado**. Si Ghost compite con Express esta semana, **Ghost espera** y se cierra el tren. Cash priority = Express. Ghost = carril OSS.

---

## 1. No-objetivos (explícitos)

**Prohibido esta semana (Jared gate → HOLD):**

- Cualquier spend, DNS, dominio, hosting, cloud deploy
- Tocar Express, caja, Fairway, tuwebideal
- Recomendaciones de SaaS / cloud / marketplace / waitlist
- Postgres “de verdad”, dashboard HTML, plugin system, bot Telegram, mobile, monitoring continuo
- Publicar PyPI (`ghost-osint` sigue unpublished; no es el problema de esta semana)
- Más módulos OSINT, más plataformas, “deep dive” social/darkweb
- Tests de módulos más allá de lo que rompa un PR de esta lista (Dinesh: *module tests later*)
- Refactors cosméticos, rename de paquete, graph DB, STIX/TAXII

Si un agente paralelo mete cualquiera de esos en un PR de hardening: **no merge**. Recortar.

---

## 2. Estado real del repo (no el README)

Inspección de `main` @ `22ef1c2`. Código vs marketing.

### Lo que sí existe y es el wedge real

| Pieza | Dónde |
|---|---|
| Paquete canónico | `ghost/` (CLI `ghost` / `python3 -m ghost`) |
| Case store SQLite | `ghost/backend/db.py` · schema v2 · `authorized_use` + `scope` |
| Orquestador | `ghost/core/investigator.py` |
| Doctor reutilizable | `ghost/core/doctor.py` + `ghost doctor` / `--json` |
| Provenance en reporte | `ghost/core/report_generator.py` `_build_provenance` |
| Demo self-audit | `docs/self-audit-demo.md` + `examples/sample-username-case.json` |
| CI | `.github/workflows/ci.yml` — `pip install -e ".[dev]"` + ruff + pytest 3.10/3.11/3.12 |
| Calibración parcial del README | PR #13 (Quick Start, vs maigret, PyPI unpublished, dashboard *not shipped*) |

### Agujeros de seguridad (Gilfoyle — confirmados en código)

| Hallazgo | Evidencia |
|---|---|
| API Flask **sin auth** | `ghost/backend/server.py`: `/api/investigate`, `/api/investigations`, `/api/investigation/<id>` (y graph) no leen ningún token. Cualquiera que alcance el puerto lee **todos** los case files (target, findings, errores). |
| CORS abierto | `CORS(app)` sin `origins`. |
| Bind default `0.0.0.0` | `ghost/core/config.py` `GHOST_HOST` default `"0.0.0.0"`; `.env.example` igual. Expone la API a la LAN. |
| Secret default | `GHOST_SECRET_KEY` default `"ghost-dev-key"`. **Además Flask nunca asigna `app.secret_key`** — el campo es dead config. |
| `GHOST_API_TOKEN` **no existe** | Cero referencias en el árbol. Hay que crearlo. |
| Rate limit no enforced | `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_PERIOD` viven en `Config` y **nunca se usan** en `server.py`. No hay Flask-Limiter ni middleware. |
| Docker root | `Dockerfile`: `python:3.11-slim`, no `USER`, no health binary. |
| Healthcheck roto | `docker-compose.yml` hace `curl -f http://localhost:5000/api/health`. **`/api/health` no existe.** `curl` no está en la imagen slim. |
| Volumen Docker desalineado | Compose monta `ghost_data:/app/data` y `./investigations:/app/investigations`. El código escribe en `ghost/core/config.py` → `DATA_DIR = <ghost>/data` = `/app/ghost/data`. El volume no persiste la DB real. |
| Dashboard 404 | `server.py` sirve `ghost/ui/dashboard.html`. **Ese archivo no existe.** `Makefile` target `dashboard` es marketing residual. |

### Doctor **no** falla en defaults inseguros (Dinesh B — confirmado)

`ghost/core/doctor.py` hoy chequea: SQLite, OpenAI key (warn), imports (`aiohttp`, `rich`, `flask`, `phonenumbers`, `dns`), binario `sherlock`, lista `enabled_modules`.

No mira `GHOST_SECRET_KEY`, `GHOST_HOST`, ni token.

Tests que **van a romper** en cuanto doctor sea honesto (hoy asumen default = OK):

- `tests/test_investigator.py` `test_doctor_checks_return_structured_results` (`has_error is False`, `summary["ok"] is True`)
- `tests/test_investigator.py` `test_doctor_cli_json_output` (`exit_code == 0`, `payload["ok"] is True`)

Esos tests corren contra `Config()` de import-time. CI **no** setea secret/host/token. El PR de doctor **debe** monkeypatchar un config seguro para el path verde, y añadir path rojo para defaults.

### README todavía miente (Dinesh A — resto post-PR #13)

PR #13 recortó parte del humo (maigret, PyPI, dashboard no shipped). Sigue siendo copy de “platform”:

- H1: **“AI-Powered OSINT Investigation Platform”** (`README.md` L5, `ghost/ui/cli.py` banner L39, `ghost/__init__.py`, `pyproject.toml` `description`)
- Social + darkweb marcados **✅** como features de producción (`README.md` tabla de módulos)
- Roadmap SaaS-shaped: Team Collaboration, Telegram Bot, Mobile App, Scheduled Monitoring, Graph Database
- “Areas We Need Help”: Dashboard UI, translations, new OSINT modules
- Quick Start de Docker: “REST API → http://localhost:5000 (dashboard HTML is not shipped yet)” — no menciona bind `0.0.0.0`, root, ni API sin token

### Módulos ToS / abuso (Richard max-scope: off-by-default, no reescribir)

`Config.enabled_modules` default incluye `social` y `darkweb`.

`INPUT_TYPE_MODULES` mete `social`+`darkweb` en `username` / `email` / `name` **sin que el usuario los pida**:

```python
# ghost/core/investigator.py
"username": ["username", "social", "darkweb"],
"email": ["email", "username", "social", "darkweb"],
"phone": ["phone", "social"],
"name": ["username", "social", "darkweb"],
```

- `ghost/modules/social.py`: GET a Instagram, X, TikTok, LinkedIn con UA de Chrome; Reddit `/about.json`; GitHub API. Scraping de ToS, no API oficial (salvo X bearer / GitHub público).
- `ghost/modules/darkweb.py`: scrape Ahmia; HIBP; Google CSE sobre paste sites; DeHashed es stub (`available: False`).
- `ghost/core/config.py` `user_agent` = Mozilla Chrome. Mentir el UA no es “OSINT profesional”; es fingerprint de scraper.

`tests/test_investigator.py` `TestModuleRouting.test_username_modules` **exige** `"social" in INPUT_TYPE_MODULES["username"]`. Ese assert es el conflicto #1 del PR off-by-default.

`TestGhostInvestigator.test_investigate_username` mockea Social/Darkweb. Tras el cambio, para `input_type="username"` **no** deben llamarse a menos que `--modules` los pida. Actualizar el test, no dejar el mock “por si acaso” como contrato.

### Provenance: hay tests, no hay contrato

Existe:

- `TestReportProvenance.test_json_report_includes_provenance` — payload sintético `johndoe`, no el self-audit demo
- `tests/test_examples.py` `test_sample_case_report_provenance` — sample JSON, un subset de asserts

Falta un contrato **cerrado de keys** alineado con `examples/expected-report-snippet.md` + `docs/self-audit-demo.md`. Hoy no se falla si alguien borra `generated_at`, `investigation_id`, `module_count`, o `global_errors`.

Keys reales que `_build_provenance` emite hoy:

`generated_at`, `target`, `input_type`, `investigation_id`, `scope`, `authorized_use`, `modules_run`, `module_count`, `source_urls`, `source_url_count`, `module_errors`, `global_errors`

Ojo: `ReportGenerator` carga templates desde `ghost/templates/` (`BASE_DIR` = paquete `ghost/`). El HTML real está en **`templates/report.html` en la raíz del repo**. Los HTML reports caen al fallback inline. El contrato de esta semana es **JSON**, no arreglar el path del template salvo que un PR lo toque por accidente (no es scope).

### Deps rotas en dos fuentes de verdad

| Fuente | Quién la usa | Drift |
|---|---|---|
| `pyproject.toml` | CI, `pip install -e .`, console script `ghost` | Core liviano. **No incluye `whois`/`python-whois`** aunque `ghost/modules/domain.py` y `email.py` hacen `import whois` lazy. |
| `requirements.txt` | **solo Docker** (`COPY requirements.txt` + `pip install -r`) | Más gordo: `face-recognition` (dlib; el Dockerfile **no** instala cmake/boost — build frágil), `sqlalchemy`/`alembic` (**cero imports** en el código; `db.py` es sqlite3 crudo), `pydantic`, `questionary`, `tiktoken`, `flask-socketio`, `weasyprint`, `sherlock-project`, pytest. |

CI **no** construye Docker. Un `docker-compose up` que “funciona en la laptop de alguien” no está gateado.

### Agentes cloud ya lanzados (no duplicar)

Al escribir este plan (2026-09-21) hay **dos agentes RUNNING** sobre el mismo repo, más este plan:

| Agente | Cursor | Mandato | Status al planear |
|---|---|---|---|
| Ghost A+B: doctor insecure defaults + CI | https://cursor.com/agents/bc-63308fb6-461e-5a92-9c84-33e68336dca2 | Dinesh A+B | RUNNING, branch aún `null` |
| ghost: API auth, localhost bind, Docker non-root | https://cursor.com/agents/bc-e84f13e5-271a-5682-9c0a-cbf35e1b6d9d | Gilfoyle auth/bind/Docker | RUNNING, branch aún `null` |
| este plan | `cursor/hardening-plan-72fb` | Solo este markdown | — |

También existe (IDLE, **ya mergeado** vía PR #13): [Ghost: polish for ethical star growth](https://cursor.com/agents/bc-f061350b-525a-5b7f-95c0-6ac569ce29a3) branch `cursor/ethical-discoverability-29a3`. No reabrir.

**Regla:** si A+B o auth abren un feature PR, Julio **revisa contra este plan** y rebasea. Nadie abre un segundo PR que toque los mismos files. Este plan **secuencia**; no reimplementa.

---

## 3. Env names (locked Gilfoyle × Dinesh)

No inventar aliases. No `SECRET_KEY`, no `HOST`, no `API_KEY` genérico.

| Variable | Rol | Default inseguro hoy | Default post-hardening |
|---|---|---|---|
| `GHOST_SECRET_KEY` | Flask `app.secret_key` (hoy unused) | `"ghost-dev-key"` | **sin default**. Proceso API no arranca si falta o es el valor de ejemplo. |
| `GHOST_HOST` | bind | `"0.0.0.0"` | `"127.0.0.1"` |
| `GHOST_API_TOKEN` | header auth en `/api/*` | no existe | **sin default**. Vacío = doctor FAIL + API no arranca (o arranca y rechaza todo; preferir fail-fast al boot). |

Otras vars que **sí** existen y se quedan: `GHOST_PORT` (5000), `GHOST_DEBUG`, `DATABASE_URL`, `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_PERIOD`, keys opcionales (`OPENAI_API_KEY`, `HIBP_API_KEY`, …).

Valores prohibidos para secret (doctor + boot de API):

- vacío
- `ghost-dev-key`
- `change-this-to-a-random-string`
- cualquier string < 16 chars (regla simple, no teatro de entropy)

Host inseguro (doctor FAIL, y API no debe bindirlos salvo flag explícita que **esta semana no se añade**):

- `0.0.0.0`
- `::`
- `*`

Token: ausente o whitespace → FAIL.

Header propuesto (Gilfoyle, un solo esquema, no dos):

```
Authorization: Bearer <GHOST_API_TOKEN>
```

No Basic, no querystring, no cookie. `/api/health` es la **única** ruta API sin token (liveness, cero PII). El resto de `/api/*` exige token. `GET /` dashboard 404 puede quedarse; no es el wedge.

---

## 4. Tren de PRs — orden de merge

Owners: **Dinesh** (producto/código A+B), **Gilfoyle** (infra/security), **Julio** (conductor de merge + PRs chicos + kill viernes).

Merge **en este orden**. PRs posteriores rebasean sobre `main` después de cada merge. No stacked-PR teatro: ramas independientes desde `main`, rebase obligatorio.

```
PR0  plan (este archivo)           Julio      merge YA
  │
  ├─► PR1  README honesty          Dinesh     merge primero de código (docs)
  │
  ├─► PR2  doctor FAIL insecure    Dinesh     merge 2º  [agente A+B ya launched]
  │         (puede ir junto a PR1 si el agente A+B ya lo unificó;
  │          entonces es UN solo PR "A+B" y este tren colapsa 1+2)
  │
  ├─► PR3  auth + bind + Docker    Gilfoyle   merge 3º  [agente auth ya launched]
  │
  ├─► PR4  provenance contract     Julio      merge 4º  (tests only)
  │
  ├─► PR5  social/darkweb off      Dinesh o Julio   merge 5º
  │
  └─► PR6  unificar deps           Julio      SOLO si PR3 ya mergeó y es <vie 25
```

**Por qué este orden (conflictos reales, no ceremonia):**

1. **PR1 README** casi no toca Python. Gilfoyle no reescribe el H1 ni el roadmap. Máximo un párrafo “Local API” **después** de PR3, no ahora.
2. **PR2 doctor** es dueño de `ghost/core/doctor.py` y de los tests `test_doctor_*`. Lee env/`Config`; **no** cambia defaults de bind/secret (eso es PR3). Así A+B puede aterrizar **antes** de que el token exista en código: doctor FAIL por token ausente es correcto.
3. **PR3** es dueño de `ghost/backend/server.py`, `Dockerfile`, `docker-compose.yml`, `.env.example`, y de **defaults** en `ghost/core/config.py`. No reescribe `doctor.py`. Si necesita un check de boot, llama `run_doctor_checks()` ya existente.
4. **PR4** solo tests (+ quizá constante de keys). Cero overlap con Flask/Docker.
5. **PR5** toca `config.enabled_modules` + `INPUT_TYPE_MODULES` + tests de routing. Si aterriza **antes** de PR3, pelea `config.py` con Gilfoyle. Por eso va **después**.
6. **PR6** toca `pyproject.toml` / `requirements.txt` / `Dockerfile`. Si aterriza antes de PR3, Gilfoyle instala Flask-Limiter en el archivo que PR6 borra. Por eso **último**.

### Candado de files (anti-colisión)

| File | Dueño esta semana | Quién no lo toca |
|---|---|---|
| `docs/HARDENING_PLAN.md` | Julio (PR0) | nadie más, salvo update de kill el viernes |
| `README.md` | Dinesh (PR1). Gilfoyle: **máximo** sección API local en PR3, 15 líneas, rebase post-PR1 | no reescribir features/roadmap en PR3 |
| `CHANGELOG.md` | cada PR añade **una** viñeta Unreleased; no reformat del resto | — |
| `ghost/core/doctor.py` + tests doctor | Dinesh PR2 | Gilfoyle no |
| `ghost/backend/server.py` | Gilfoyle PR3 | Dinesh no |
| `Dockerfile` `docker-compose.yml` `.env.example` | Gilfoyle PR3 | PR6 rebase; Dinesh no |
| `ghost/core/config.py` | Gilfoyle PR3 para host/secret/token fields. PR5 **después** para `enabled_modules` | Dinesh PR2 lee, no escribe defaults |
| `ghost/core/investigator.py` | PR5 | PR3 no |
| `ghost/core/report_generator.py` | PR4 **no lo cambia** salvo bug de contrato. Si hay que cambiar keys, Julio en PR4 con test | no “mejorar” provenance de paso |
| `pyproject.toml` `requirements.txt` | PR6 (y PR3 solo si añade `flask-limiter` / `gunicorn` — entonces PR6 rebase) | Dinesh no unifica deps en A+B |
| `tests/test_investigator.py` | Pedazoado: doctor tests = PR2; API tests = PR3; routing/username investigate = PR5; provenance class = PR4 o se mueve a archivo nuevo | **preferir archivos nuevos** para no pelear el mismo hunk |
| `tests/test_modules.py` | **fuera de semana** salvo que un default de Config rompa `test_default_config` (PR5) | no “aprovechar” para cobertura de módulos |

Si A+B ya abre **un** PR que mezcla README+doctor: Julio lo trata como PR1+PR2 colapsados. Gilfoyle rebasea PR3 encima. No splittearlo a la fuerza si CI está verde y el diff respeta el candado.

Si el agente auth mezcla doctor+README: **recortar** esos files del PR3 en review. Auth no es dueño de doctor.

---

## 5. Detalle por PR

### PR0 — este plan (Julio)

- Branch: `cursor/hardening-plan-72fb`
- Título: `plan: ghost hardening (OSS local tool)`
- Files: **solo** `docs/HARDENING_PLAN.md`
- Merge: inmediato. No espera CI de app (markdown).

### PR1 — README honesty (Dinesh)

**Intent:** Ghost se presenta como herramienta local OSS de self-audit / case-file. Cero “AI Platform”. Cero roadmap de startup.

**Files (allowlist):**

- `README.md` (principal)
- `pyproject.toml` campo `description` (una línea; no tocar deps)
- `ghost/__init__.py` docstring
- `ghost/ui/cli.py` **solo** el string `BANNER` / help del grupo click (una línea). Si pelea con PR2, dejar el banner para PR2.
- `CHANGELOG.md` viñeta Unreleased
- Opcional: `docs/self-audit-demo.md` talk track si todavía dice “Postgres comes later for team deployments” como promesa de producto — bajarlo a “SQLite is the supported backend; Postgres is explicitly out of scope until someone needs it”. No reescribir storage-adapter.

**Edits concretos al README:**

- H1 subtitle: no “AI-Powered OSINT Investigation Platform”. Algo literal: herramienta local de case-file OSINT para self-audit autorizado.
- Primer párrafo bajo el H1: local, SQLite, authorized, provenance. No “actionable intelligence”.
- Tabla de módulos: `social` y `darkweb` = **experimental / opt-in**, no ✅ de producción (aunque PR5 aún no haya apagado el default; mentir al revés también es mal — si el código todavía los prende, el README debe decir “hoy corren por default; PR5 los apaga”. Tras PR5, actualizar esa frase en el mismo PR5).
- Borrar o marcar **Won't** el roadmap: Team Collaboration, Telegram Bot, Mobile App, Scheduled Monitoring, Graph Database, Plugin System, Geospatial Timeline, STIX. No reemplazarlos por otro wishlist.
- “Areas We Need Help”: testing + docs de self-audit. No Dashboard UI, no translations, no new modules.
- Docker: “local only, broken until PR3” o quitar el happy-path `docker-compose up -d` hasta que PR3 aterrice. No documentar `0.0.0.0` como recomendado.
- No añadir waitlist, Discord, cloud, “hosted Ghost”, pricing.

**Acceptance:**

- [ ] Grep del README: cero hits de `AI-Powered OSINT Investigation Platform`
- [ ] Grep: cero `waitlist`, `SaaS`, `marketplace`, `hosted`
- [ ] Quick Start sigue siendo copy-paste real (`python3 -m pip install -e .`, `python3 -m ghost doctor`, `investigate … --no-ai --authorized`)
- [ ] Comparación vs maigret de PR #13 **se queda** (eso sí es honesto)
- [ ] CI verde (docs-only no debería romper tests)

**No hacer:** reescribir `V2_PLAN.md` (histórico). No tocar Express. No “también check out” spam extra.

### PR2 — `ghost doctor` FAIL insecure defaults (Dinesh)

**Intent:** un operador con `.env.example` copiado tal cual **no** ve `ok: true`. Exit code 1. Checks `severity="error"`.

**Files:**

- `ghost/core/doctor.py`
- tests **nuevos** preferidos: `tests/test_doctor_security.py` (evita pelear `test_investigator.py` con PR3)
- ajuste mínimo a `test_doctor_checks_return_structured_results` y `test_doctor_cli_json_output` para que el path verde use un `Config` seguro (token set, secret largo, host `127.0.0.1`)
- `ghost/ui/cli.py` solo si hay que documentar el FAIL en el help

**Checks a añadir (nombres estables para `--json`):**

| `name` | FAIL cuando | `severity` |
|---|---|---|
| `GHOST_SECRET_KEY` | missing / default de ejemplo / corto | `error` |
| `GHOST_HOST` | `0.0.0.0` / `::` / `*` | `error` |
| `GHOST_API_TOKEN` | missing / whitespace | `error` |

CLI doctor ya hace `Exit(1)` si `has_error()`. No reinventar. JSON `ok` ya deriva de errors.

**Acceptance:**

- [ ] `Config()` con defaults actuales de `main` → `summarize_doctor_checks()["ok"] is False` y `error_count >= 3` (secret, host, token). Si PR3 ya cambió el default de host a `127.0.0.1` **antes** de merge de PR2, el check de host en default deja de fallar — entonces el test rojo de host usa `cfg.host = "0.0.0.0"` explícito, no el default. **Escribir los tests así desde el día 1** para no depender del orden.
- [ ] Config monkeypatched seguro → doctor `ok` True (resto de checks actuales siguen)
- [ ] `ghost doctor --json` exit 1 en el path inseguro
- [ ] CI **no** añade un job que exija `ghost doctor` verde en el runner sin env. Eso sería un auto-fail permanente. Los tests unitarios cubren ambos paths.
- [ ] No cambia bind real, no añade Flask auth (carril Gilfoyle)

**Trampa:** `Config` evalúa `os.getenv` **en el dataclass field default** a import-time. Tests deben construir `cfg = Config()` y **asignar** atributos, o parchear env **antes** de instanciar. No asumas que `monkeypatch.setenv` muta el singleton `from ghost.core.config import config` ya importado. Usar `config_override=` que `run_doctor_checks` ya acepta.

### PR3 — API token + bind loopback + Docker non-root (Gilfoyle)

**Intent:** la API deja de ser un dump abierto de PII en `0.0.0.0:5000` como root.

**Files:**

- `ghost/core/config.py` — default `host="127.0.0.1"`; `secret_key` **sin** default de desarrollo; añadir `api_token: str = os.getenv("GHOST_API_TOKEN", "")`
- `ghost/backend/server.py` — `app.secret_key`; auth; CORS; rate limit real; `/api/health`; fail-fast en `main()`
- `Dockerfile` `docker-compose.yml` `.env.example`
- tests **nuevos**: `tests/test_api_auth.py` (no inflar `TestApiSafetyGates` en el mismo hunk que Dinesh)
- `CHANGELOG.md` + **después de rebase PR1** un bloque corto en README “Local API”

**Comportamiento API:**

1. `main()`: si secret inválido o token vacío → `SystemExit` con mensaje que apunta a `ghost doctor`. No servir en inseguro.
2. `app.run(host=config.host, …)` con default 127.0.0.1.
3. Decorator / `before_request`: toda ruta `/api/*` excepto `/api/health` exige `Authorization: Bearer` coincidente (compare_digest). 401 si falta, 403 si no coincide.
4. CORS: **quitar** `CORS(app)` abierto. Si hace falta CORS para un frontend futuro: `origins=["http://127.0.0.1:5000"]`. Esta semana no hay frontend. Preferir cero CORS.
5. Rate limit: usar de verdad `config.rate_limit_requests` / `rate_limit_period` (Flask-Limiter **o** un contador in-memory por IP; no añadir Redis). Aplicar a `/api/investigate` como mínimo; preferible a todo `/api/*` menos health.
6. `GET /api/health` → `{"ok": true}` sin DB dump, sin lista de investigations.
7. El gate `authorized_use: true` **se queda**. Token ≠ autorización de OSINT. Los tests actuales `TestApiSafetyGates` deben seguir pasando **con header de token** (actualizar).

**Docker:**

- `USER` no-root (`UID` fijo, p.ej. 1000), dirs de data con write para ese user.
- Volume alineado a `/app/ghost/data` **o** `DATA_DIR` configurable; no dejar el mismatch.
- Healthcheck: **no** depender de `curl` si no está instalado. Opciones aceptables: `python -c` contra `/api/health`, o instalar `curl` en la imagen. El endpoint debe existir.
- Bind: compose `ports: "127.0.0.1:${GHOST_PORT:-5000}:5000"` — no publicar `0.0.0.0:5000` al host.
- `env_file: .env` puede quedarse, pero `.env.example` debe documentar `GHOST_API_TOKEN=` vacío con comentario “required to start API”.
- No instalar `face-recognition` en la imagen default (rompe build). Si PR6 no llegó, Dockerfile puede `pip install .` en vez de `-r requirements.txt`, o un requirements recortado. **No** arrastrar dlib “porque ya estaba”.
- No `restart: unless-stopped` en una herramienta local si implica reabrir un bind inseguro; no es hill to die on. Non-root + loopback + token sí lo son.

**Acceptance:**

- [ ] `python -m ghost.backend.server` sin env → no arranca
- [ ] con token+secret+host 127.0.0.1 → arranca; `GET /api/investigations` sin header → 401; con header → 200
- [ ] `POST /api/investigate` sin `authorized_use: true` sigue 400 **aunque** el token sea válido
- [ ] CORS `Access-Control-Allow-Origin: *` **ausente**
- [ ] test client cubre 401/403/200 y health
- [ ] Dockerfile tiene `USER` no-root; compose healthcheck no usa un binario inexistente ni una ruta 404
- [ ] compose no publica `0.0.0.0`
- [ ] `ghost doctor` (post-PR2) en un `.env` de ejemplo **sigue** FAIL hasta que el operador ponga token/secret — no “arreglar” doctor para que Docker pase verde con defaults

**No hacer en PR3:** unificar todo pyproject (PR6). No apagar social/darkweb (PR5). No reescribir README entero (PR1). No “deploy to Fly/Render”.

### PR4 — Provenance contract test (Julio; Gilfoyle si Julio está en Express)

**Intent:** el reporte JSON del self-audit no puede perder el bloque de auditoría sin que CI grite.

**Files:**

- **Nuevo** `tests/test_provenance_contract.py`
- No cambiar `report_generator.py` salvo bug (key ausente vs snippet)

**Contrato a congelar** (set equality de keys de `report["provenance"]` contra esta lista):

```
generated_at, target, input_type, investigation_id, scope, authorized_use,
modules_run, module_count, source_urls, source_url_count, module_errors, global_errors
```

Fixture: `examples/sample-username-case.json` pasado por `ReportGenerator().generate(..., "json")`.

Asserts mínimos:

- `authorized_use is True`
- `scope == "authorized self-audit demo"`
- `modules_run == ["username"]` y `module_count == 1`
- `source_url_count == 3` y todos los URLs contienen `.example.com` (no prod leaks)
- `module_errors == {}` y `global_errors == []`
- `target == "demo_user"`
- `generated_at` parseable ISO-8601
- `investigation_id ==` id del sample

Opcional y barato: leer `examples/expected-report-snippet.md` y assertar que cada key del snippet JSON embebido existe en el reporte vivo (el snippet no incluye `generated_at` / `investigation_id`; el contrato de keys es el de `_build_provenance`, no una copia 1:1 del markdown).

**Acceptance:**

- [ ] Test nuevo falla si se borra una key de `_build_provenance`
- [ ] No hace HTTP, no llama OpenAI, no corre módulos live
- [ ] `tests/test_examples.py` existente se queda (no es duplicado dañino; el nuevo es el contrato de keys)

**No hacer:** “confidence per finding” (V2_PLAN lo menciona; **no** está en `_build_provenance` hoy). Añadirlo es scope creep. El contrato congela lo que hay.

### PR5 — `darkweb` / `social` experimental off-by-default (Dinesh o Julio)

**Intent:** `ghost investigate demo_user --type username` **no** pega a Instagram/Ahmia salvo `--modules social` / `--modules darkweb`.

**Files:**

- `ghost/core/config.py` — sacar `social` y `darkweb` de `enabled_modules` default
- `ghost/core/investigator.py` — sacar de `INPUT_TYPE_MODULES` defaults (`username`, `email`, `phone`, `name`)
- `tests/test_investigator.py` `TestModuleRouting` + `test_investigate_username` (social/darkweb **not** called)
- `tests/test_modules.py` `test_default_config` si aserta la lista completa
- README tabla de módulos (estado experimental + cómo opt-in)
- `examples/sample-email-investigation.md` (ya avisa que email fanea social/darkweb — actualizar)
- `CHANGELOG.md`

Módulos **no se borran**. `GhostInvestigator._modules` puede seguir registrándolos. Filtro ya existe: `module_names = [m for m in module_names if m in self.config.enabled_modules]`. Off-by-default = no están en la lista default **y** no están en el mapa de input type.

Opt-in:

```bash
python3 -m ghost investigate demo_user --type username --modules username,social --authorized --scope "..."
```

Eso requiere que `social` esté en `enabled_modules`. Documentar env futuro (`GHOST_ENABLE_SOCIAL=1`) **solo si es trivial**; no es requisito del viernes. `--modules` + lista default basta.

**Acceptance:**

- [ ] `INPUT_TYPE_MODULES["username"] == ["username"]` (o equivalente sin social/darkweb)
- [ ] `INPUT_TYPE_MODULES["phone"]` no incluye `social`
- [ ] investigacion username mockeada **no** llama `SocialModule.run` ni `DarkWebModule.run`
- [ ] `--modules social` sigue pudiendo correr el módulo (test unitario de routing, no live HTTP)
- [ ] README no marca esos módulos como ✅ producción
- [ ] Doctor “enabled modules” sigue OK con la lista más corta

**No hacer:** reescribir `social.py` / `darkweb.py`. No “arreglar ToS” scrape. Off es el control de daño. Borrar código es fuera de semana.

### PR6 — Unificar pyproject vs requirements (Julio, stretch)

**Intent:** una sola fuente de deps. Docker y CI instalan lo mismo.

**Propuesta mínima (no poetry drama):**

- `pyproject.toml` es la fuente.
- `Dockerfile`: `pip install .` (core) o `pip install .[dev]` no. Extra `full` opcional.
- `requirements.txt` o se genera con un comentario “derived, do not hand-edit” **o** se borra y se actualiza el Dockerfile. Preferir: `requirements.txt` reducido a `-e .` + pin comment, para no romper copy-paste externos.
- Mover `python-whois` / `whois` a dependencias **core** (el código las importa) **o** hacer el import un fail suave ya existente — hoy Docker las tiene y CI no. Elegir: añadir a pyproject core.
- **No** promover a core: `face-recognition`, `sqlalchemy`, `alembic`, `pydantic`, `questionary`, `flask-socketio`, `tiktoken`, `weasyprint`, `sherlock-project`. Esos, si acaso, extras.
- Flask-Limiter, si PR3 lo añadió a pyproject, se queda.

**Acceptance:**

- [ ] `pip install -e ".[dev]"` (CI) instala lo que el código core importa
- [ ] Docker build **sin** dlib/face-recognition
- [ ] `ruff` + pytest verdes
- [ ] No “opportunistic” upgrade de Flask/OpenAI

Si viernes 12:00 y PR6 no está en review: **KILL**. Documentar en §7.

---

## 6. Qué hace cada persona (sin romance)

| Quién | Esta semana | No |
|---|---|---|
| **Dinesh** | PR1 README. PR2 doctor. Si A+B agente ya abrió el PR, **review + recortar**, no abrir otro. PR5 si da tiempo post-PR3. | Auth Flask, Docker, Express |
| **Gilfoyle** | PR3 auth/bind/Docker. Provenance (PR4) **solo si Julio no puede** y PR3 ya mergeó. | README rewrite, apagar módulos, deps unify, doctor.py |
| **Julio** | Merge conductor. PR0. PR4 contrato. PR6 stretch. Rebase police. Kill doc viernes. Si Express pisa Ghost: **cierra el tren**. | No gastar cash, no DNS, no Fairway |

Agentes cloud = mano de obra. Un humano (Julio) mergea. No merge automático.

---

## 7. Kill criteria — viernes 25 sep 2026

Evaluar en `main`. Parcial > teatro.

### MUST merge (si falta alguno: Ghost queda en HOLD hasta que Express respire)

- [ ] PR1 README honesty
- [ ] PR2 doctor FAIL insecure defaults

Sin eso, el repo sigue vendiéndose como platform y `ghost doctor` miente. Inaceptable para un tool de case-file.

### SHOULD merge (si no entra: se documenta aquí el viernes, no se “sigue la semana que viene” en silencio)

- [ ] PR3 auth + bind 127.0.0.1 + Docker non-root/healthcheck
- [ ] PR4 provenance contract
- [ ] PR5 social/darkweb off-by-default

### DROP sin culpa (no son el wedge)

- [ ] PR6 deps unify
- [ ] Tests de módulos (`tests/test_modules.py` ampliación)
- [ ] Template HTML path (`templates/` raíz vs `ghost/templates/`)
- [ ] Dashboard HTML
- [ ] Rate limit “de producto” más allá de un limiter in-memory en PR3

### Kill switch Express

Si Express (Tu Web Ideal) necesita a Julio/Gilfoyle/Dinesh **antes** del viernes:

1. Merge lo MUST que ya esté verde.
2. Cerrar (no merge) el resto de PRs de Ghost.
3. Añadir una sección “Kill 2026-09-25” al final de **este** archivo con la lista de lo que no entró. Un commit, no un essay.
4. Ghost espera. No “pequeño follow-up” que se coma el lunes de Express.

### Cómo rellenar el viernes (plantilla)

```
## Kill 2026-09-25
- Merged: …
- Open / not merged: …
- Reason: tiempo | conflicto Express | CI rojo | agente paralelo divergió
- Next: Ghost waits. No SaaS. No DNS.
```

---

## 8. Riesgos (los que importan)

### API PII (bloqueante hasta PR3)

SQLite local guarda targets, findings (emails, teléfonos, perfiles, URLs), summaries, errores. `GET /api/investigations` y `GET /api/investigation/<id>` los serializan **sin auth**.

Con `GHOST_HOST=0.0.0.0` + CORS `*` + Docker root:

- Cualquier proceso en la LAN (o un HTML malicioso si el browser puede alcanzar localhost… CORS abierto facilita exfil desde páginas locales) lee case files.
- `POST /api/investigate` lanza OSINT contra el target que le pongan, solo frenado por `authorized_use: true` (un boolean en el JSON, no un secreto).

Mitigación = PR3. Hasta entonces: README no debe invitar a `docker-compose up -d` como “API lista”. Doctor FAIL (PR2) es el parche social; el parche técnico es no bindir `0.0.0.0` y exigir token.

No loguear `GHOST_API_TOKEN` ni secret en doctor `--json` `detail`. Decir `missing` / `insecure default` / `set`. Nunca el valor.

### ToS / abuse de módulos (bloqueante de producto, no de merge de PR1)

`social` y `username` (70 HTTP probes) y `darkweb` (Ahmia) pueden violar ToS de terceros y parecer stalking toolkit. Richard: wedge = self-audit autorizado. Por eso PR5 apaga social/darkweb por default. Username HTTP checks se quedan (es el demo); el Quick Start **ya** usa `--modules username`. No ampliar cobertura.

Disclaimer legal del README se queda. No es un control. Off-by-default sí lo es.

No hay trabajo de “compliance SaaS” ni DPA ni GDPR product. Local tool. El riesgo operativo es: un default ruidoso pega a redes ajenas. Apagarlo.

### Carrera de agentes

Dos agentes de código ya corren. Riesgo real: doble PR de doctor, o auth que reescribe README. Julio cierra el duplicado. Este plan es la tie-break, no el segundo implementador.

### CI vs doctor

Si alguien añade `ghost doctor` al workflow de CI sin env seguro, CI queda rojo para siempre post-PR2. **Prohibido** hasta tener un job explícito con env dummy de test. Los unit tests cubren FAIL/OK.

---

## 9. Verificación por PR (comando)

Común a todo PR de código:

```bash
python -m pip install -e ".[dev]"
python -m ruff check ghost tests conftest.py
python -m ruff format --check ghost tests conftest.py
python -m pytest -q
```

Extra:

| PR | Extra |
|---|---|
| PR2 | `python -m ghost doctor --json ; echo exit:$?` en env limpio (expect ≠ 0) y en env seguro (expect 0) |
| PR3 | test client 401/200; `docker build` **si** Docker está en la máquina del agente; no inventar registry |
| PR4 | `pytest -q tests/test_provenance_contract.py` |
| PR5 | `pytest -q tests/test_investigator.py` y grep `INPUT_TYPE_MODULES` |
| PR6 | `docker build` + pytest |

No hay browser app que verificar. No usar Lovable. No gastar DNS.

---

## 10. Recordatorio para Julio

Ghost no es el negocio. Express sí. Este plan cabe en una semana de OSS **si** los agentes paralelos respetan el candado de files. Si no respetan: recortar diffs, no negociar roadmap.

Max scope otra vez: README honesto + doctor FAIL + provenance contract + social/darkweb off + auth/bind/Docker. Luego stop.
