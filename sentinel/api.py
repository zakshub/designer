"""Authenticated HTTP adapter. Domain transitions remain in Brain."""

import copy
import json
import math
import sqlite3
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth import Auth, AuthError, ROLES, migrate_auth, public_user
from .engine import Brain
from .evaluation import evaluate
from .model import Conflict, Invalid, NotFound, eligible
from .review import review_packet, review_queue
from .store import Store

Role = Literal["viewer", "editor", "reviewer", "admin"]
Reason = Annotated[str, Field(min_length=1, max_length=2000, pattern=r"\S")]
Username = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{2,63}$")]
Revision = Annotated[int, Field(ge=1)]
MAX_BODY = 1_048_576


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Login(Payload):
    username: Username
    password: Annotated[SecretStr, Field(min_length=1, max_length=128)]


class NewUser(Login):
    role: Role
    reason: Reason


class UserChange(Payload):
    role: Role | None = None
    active: bool | None = None
    reason: Reason


class PasswordChange(Payload):
    current_password: Annotated[SecretStr, Field(min_length=1, max_length=128)]
    new_password: Annotated[SecretStr, Field(min_length=15, max_length=128)]


class PasswordReset(Payload):
    new_password: Annotated[SecretStr, Field(min_length=15, max_length=128)]
    reason: Reason


class ReasonOnly(Payload):
    reason: Reason


class Transition(ReasonOnly):
    expected: Revision


class RevisionBody(Transition):
    changes: dict


class ReviewBody(Transition):
    decision: Literal["approve", "reject"]


class Retirement(Transition):
    successor_id: str | None = None


class Ingestion(ReasonOnly):
    objects: Annotated[list[dict], Field(min_length=1, max_length=100)]


class EvaluationBody(Payload):
    suite: dict


def error_response(status, code, message, request_id, details=None):
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else {}
    if status == 429:
        headers["Retry-After"] = "300"
    return JSONResponse({"error": error, "request_id": request_id}, status_code=status, headers=headers)


class RequestBoundary:
    """Bound JSON bodies before parsing and prevent duplicate-key ambiguity."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def secure_send(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).extend([
                    (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff"),
                    (b"x-request-id", request_id.encode())])
            await send(message)

        body = bytearray()
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            body.extend(event.get("body", b""))
            if len(body) > MAX_BODY:
                return await error_response(413, "body_too_large", "Maximum request size is 1 MiB", request_id)(scope, receive, secure_send)
            if not event.get("more_body", False):
                break
        if body:
            headers = dict(scope.get("headers", []))
            if headers.get(b"content-type", b"").split(b";")[0].strip().lower() != b"application/json":
                return await error_response(415, "json_required", "Use application/json", request_id)(scope, receive, secure_send)
            try:
                def pairs(items):
                    obj = {}
                    for key, value in items:
                        if key in obj:
                            raise ValueError("Duplicate key")
                        obj[key] = value
                    return obj

                def invalid_number(value):
                    raise ValueError("Non-finite number")

                parsed = json.loads(body.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid_number)
                pending = [parsed]
                while pending:
                    value = pending.pop()
                    if isinstance(value, float) and not math.isfinite(value):
                        raise ValueError("Numeric overflow")
                    if isinstance(value, str):
                        value.encode("utf-8")  # Reject unpaired escaped surrogates.
                    elif isinstance(value, dict):
                        pending.extend(value.keys())
                        pending.extend(value.values())
                    elif isinstance(value, list):
                        pending.extend(value)
            except (ValueError, UnicodeError, RecursionError):
                return await error_response(400, "invalid_json", "Request must contain unambiguous finite JSON", request_id)(scope, receive, secure_send)
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, secure_send)


def create_app(database, fixture_mode=False, auth_clock=time.time):
    if str(database) == ":memory:":
        raise Invalid("API requires a file database so request connections share state")
    database = str(Path(database).resolve())
    setup = Store(database, fixture_mode)
    try:
        migrate_auth(setup)
    finally:
        setup.close()
    app = FastAPI(title="Sentinel Backend", version="0.2.0", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    app.add_middleware(RequestBoundary)
    bearer = HTTPBearer(auto_error=False)

    def connection():
        # FastAPI may resume a sync dependency in another worker thread. Each
        # request still owns one connection; it is never shared across requests.
        store = Store(database, fixture_mode, check_same_thread=False)
        try:
            yield store
        finally:
            store.close()

    def current(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                store: Store = Depends(connection)):
        principal = Auth(store, auth_clock).authenticate(credentials.credentials if credentials else None)
        # Recheck after acquiring the SQLite write lock, not just at request entry.
        # A revocation committed before this transaction must prevent the write.
        def guard():
            fresh = Auth(store, auth_clock).authenticate(credentials.credentials)
            if fresh["role"] != principal["role"]:
                raise AuthError(403, "forbidden", "Account permissions changed; sign in again")
        store.transaction_guard = guard
        store.audit_context = {"user_id": principal["id"], "username": principal["username"], "role": principal["role"],
                               "session_id": principal["session_id"], "request_id": request.state.request_id}
        return principal

    def require(role):
        def check(request: Request, principal=Depends(current), store: Store = Depends(connection)):
            if ROLES[principal["role"]] < ROLES[role]:
                Auth(store, auth_clock).event(principal["id"], "role-denied", request.state.request_id, {"required_role": role})
                raise AuthError(403, "forbidden", f"This operation requires the {role} role")
            return principal
        return check

    viewer, editor, reviewer, admin = (require(role) for role in ROLES)

    def result(request, value):
        return {"data": value, "request_id": request.state.request_id}

    @app.exception_handler(AuthError)
    async def auth_error(request, exc):
        return error_response(exc.status, exc.code, str(exc), request.state.request_id)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return error_response(exc.status_code, code, str(exc.detail), request.state.request_id)

    @app.exception_handler(Invalid)
    async def invalid(request, exc):
        status, code = (404, "not_found") if isinstance(exc, NotFound) else (409, "conflict") if isinstance(exc, Conflict) else (422, "invalid_operation")
        return error_response(status, code, str(exc), request.state.request_id)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Never echo submitted values: login and reset bodies contain secrets.
        details = [{"field": ".".join(map(str, e["loc"])), "type": e["type"]} for e in exc.errors()]
        return error_response(422, "validation_error", "Request fields are invalid", request.state.request_id, details)

    @app.exception_handler(sqlite3.Error)
    async def database_error(request, exc):
        return error_response(503, "storage_unavailable", "Storage is unavailable; retry the request", request.state.request_id)

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        return error_response(500, "internal_error", "An internal error occurred", request.state.request_id)

    @app.get("/health")
    def health(request: Request):
        return result(request, {"status": "ok"})

    @app.post("/v1/auth/login")
    def login(body: Login, request: Request, store: Store = Depends(connection)):
        return result(request, Auth(store, auth_clock).login(body.username, body.password.get_secret_value(),
                      request.client.host if request.client else "unknown", request.state.request_id))

    @app.get("/v1/auth/me")
    def me(request: Request, principal=Depends(viewer)):
        return result(request, {key: value for key, value in principal.items() if key != "session_id"})

    @app.post("/v1/auth/logout")
    def logout(request: Request, principal=Depends(viewer), store: Store = Depends(connection)):
        Auth(store, auth_clock).logout(principal, request.state.request_id)
        return result(request, {"logged_out": True})

    @app.post("/v1/auth/password")
    def password(body: PasswordChange, request: Request, principal=Depends(viewer), store: Store = Depends(connection)):
        Auth(store, auth_clock).change_password(principal, body.current_password.get_secret_value(), body.new_password.get_secret_value(), request.state.request_id)
        return result(request, {"changed": True, "login_required": True})

    @app.get("/v1/users")
    def users(request: Request, principal=Depends(admin), store: Store = Depends(connection)):
        return result(request, [public_user(row) for row in store.db.execute("SELECT * FROM api_users ORDER BY username")])

    @app.post("/v1/users", status_code=201)
    def add_user(body: NewUser, request: Request, principal=Depends(admin), store: Store = Depends(connection)):
        return result(request, Auth(store, auth_clock).create_user(body.username, body.password.get_secret_value(), body.role,
                      principal["id"], request.state.request_id, reason=body.reason))

    @app.patch("/v1/users/{user_id}")
    def update_user(user_id: str, body: UserChange, request: Request, principal=Depends(admin), store: Store = Depends(connection)):
        if body.role is None and body.active is None:
            raise Invalid("Supply role or active state")
        return result(request, Auth(store, auth_clock).update_user(user_id, body.role, body.active, principal["id"], request.state.request_id, body.reason))

    @app.post("/v1/users/{user_id}/password")
    def reset_password(user_id: str, body: PasswordReset, request: Request, principal=Depends(admin), store: Store = Depends(connection)):
        Auth(store, auth_clock).reset_password(user_id, body.new_password.get_secret_value(), principal["id"], request.state.request_id, body.reason)
        return result(request, {"changed": True, "login_required": True})

    @app.get("/v1/audit/security")
    def security_events(request: Request, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                        principal=Depends(admin), store: Store = Depends(connection)):
        rows = [{**dict(row), "details": json.loads(row["details"])} for row in store.db.execute(
            "SELECT * FROM api_security_events ORDER BY sequence DESC LIMIT ? OFFSET ?", (limit, offset))]
        return result(request, rows)

    @app.get("/v1/openapi.json")
    def schema(principal=Depends(viewer)):
        return app.openapi()

    @app.get("/v1/status")
    def status(request: Request, principal=Depends(viewer), store: Store = Depends(connection)):
        brain = Brain(store)
        index = brain.contracts.graph(store.all())
        return result(request, {"mode": "fixture" if fixture_mode else "live", "objects": len(index),
                      "lifecycle": dict(Counter(o["lifecycle"] for o in index.values())),
                      "eligible": sum(eligible(key, index, brain.clock()) for key in index)})

    @app.get("/v1/objects")
    def objects(request: Request, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                principal=Depends(viewer), store: Store = Depends(connection)):
        rows = store.all()
        return result(request, {"items": rows[offset:offset+limit], "total": len(rows), "offset": offset, "limit": limit})

    @app.post("/v1/objects", status_code=201)
    def ingest(body: Ingestion, request: Request, principal=Depends(editor), store: Store = Depends(connection)):
        records = copy.deepcopy(body.objects)
        for record in records:
            record["created_by"] = principal["username"]
        return result(request, Brain(store).ingest(records, principal["username"], body.reason))

    @app.get("/v1/objects/{object_id}")
    def show(object_id: str, request: Request, principal=Depends(viewer), store: Store = Depends(connection)):
        return result(request, store.get(object_id))

    @app.patch("/v1/objects/{object_id}")
    def revise(object_id: str, body: RevisionBody, request: Request, principal=Depends(editor), store: Store = Depends(connection)):
        return result(request, Brain(store).revise(object_id, body.changes, principal["username"], body.reason, body.expected))

    @app.post("/v1/objects/{object_id}/submit")
    def submit(object_id: str, body: Transition, request: Request, principal=Depends(editor), store: Store = Depends(connection)):
        return result(request, Brain(store).submit(object_id, principal["username"], body.reason, body.expected))

    @app.post("/v1/objects/{object_id}/review")
    def review(object_id: str, body: ReviewBody, request: Request, principal=Depends(reviewer), store: Store = Depends(connection)):
        return result(request, Brain(store).review(object_id, principal["username"], body.reason, body.expected, body.decision == "approve"))

    @app.post("/v1/objects/{object_id}/retire")
    def retire(object_id: str, body: Retirement, request: Request, principal=Depends(reviewer), store: Store = Depends(connection)):
        return result(request, Brain(store).retire(object_id, principal["username"], body.reason, body.expected, body.successor_id))

    @app.post("/v1/objects/{object_id}/apply-outcome")
    def apply_outcome(object_id: str, body: Transition, request: Request, principal=Depends(reviewer), store: Store = Depends(connection)):
        return result(request, Brain(store).apply_outcome(object_id, principal["username"], body.reason, body.expected))

    @app.get("/v1/objects/{object_id}/history")
    def history(object_id: str, request: Request, principal=Depends(viewer), store: Store = Depends(connection)):
        return result(request, store.history(object_id))

    @app.get("/v1/objects/{object_id}/review-packet")
    def packet(object_id: str, request: Request, principal=Depends(viewer), store: Store = Depends(connection)):
        store.get(object_id)
        return result(request, review_packet(Brain(store), object_id))

    @app.get("/v1/review-queue")
    def queue(request: Request, principal=Depends(viewer), store: Store = Depends(connection)):
        return result(request, review_queue(Brain(store)))

    @app.get("/v1/retrieve")
    def retrieve(request: Request, query: str = Query(min_length=1, max_length=2000), domain: str = Query(),
                 platform: str = Query(min_length=1, max_length=100), audience: str | None = Query(None, max_length=200),
                 limit: int = Query(10, ge=1, le=100), principal=Depends(viewer), store: Store = Depends(connection)):
        return result(request, Brain(store).retrieve(query, domain, platform, audience, limit))

    @app.get("/v1/skills/{skill_id}/use")
    def skill(skill_id: str, request: Request, principal=Depends(viewer), store: Store = Depends(connection)):
        return result(request, Brain(store).use_skill(skill_id))

    @app.post("/v1/evaluate")
    def evaluation(body: EvaluationBody, request: Request, principal=Depends(viewer), store: Store = Depends(connection)):
        return result(request, evaluate(Brain(store), body.suite))

    @app.post("/v1/maintenance/sweep")
    def sweep(body: ReasonOnly, request: Request, principal=Depends(reviewer), store: Store = Depends(connection)):
        return result(request, Brain(store).sweep(principal["username"], body.reason))

    return app
