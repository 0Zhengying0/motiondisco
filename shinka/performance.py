"""Opt-in phase events for experiment performance, independent of scoring."""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import hashlib
import inspect
import itertools
import json
import logging
import os
from pathlib import Path
import random
from time import monotonic_ns, time

PERFORMANCE_ENV = "MOTIONDISCO_PERFORMANCE"
SEED_ENV = "MOTIONDISCO_SEED"
OLLAMA_SEED_ENV = "MOTIONDISCO_OLLAMA_SEED"
SEED_LIMIT = 2**31
_log = logging.getLogger(__name__)
_trace = ContextVar("performance_trace", default=None)
_parent = ContextVar("performance_span", default=None)
_chat_calls = ContextVar("performance_chat_calls", default=None)
_global_chat_calls = itertools.count()


def enabled():
    return os.environ.get(PERFORMANCE_ENV) == "1"


def append_event(path, event, **fields):
    """Write each event in a single append, including from forked TO workers."""
    payload = dict(event=event, version=1, unix_s=time(), pid=os.getpid(), **fields)
    try:
        line = (json.dumps(payload, allow_nan=False) + "\n").encode()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    except (OSError, ValueError, TypeError) as exc:
        _log.warning("Could not save performance event to %s: %s", path, exc)


def tracing():
    return _trace.get() is not None


def event(name, **fields):
    trace = _trace.get()
    if trace is not None:
        path, identity = trace
        append_event(path, name, **identity, **fields)


@contextmanager
def capture(path, **identity):
    if not enabled():
        yield
        return
    job_id = os.environ.get("MOTIONDISCO_JOB_ID") or os.environ.get("SLURM_JOB_ID")
    previous = _trace.get()
    inherited = previous[1] if previous else {}
    trace = _trace.set((Path(path), {"job_id": job_id, **inherited, **identity}))
    calls = _chat_calls.set(itertools.count())
    parent = _parent.set(None)
    try:
        yield
    finally:
        _parent.reset(parent)
        _chat_calls.reset(calls)
        _trace.reset(trace)


@contextmanager
def phase(stage):
    if _trace.get() is None:
        yield
        return
    start = monotonic_ns()
    span = f"{os.getpid()}:{start}"
    parent = _parent.get()
    event("phase_start", stage=stage, span=span, parent=parent, monotonic_ns=start)
    token = _parent.set(span)
    error = None
    try:
        yield
    except BaseException as exc:
        error = type(exc).__name__
        raise
    finally:
        end = monotonic_ns()
        _parent.reset(token)
        event("phase_end", stage=stage, span=span, parent=parent, monotonic_ns=end,
              seconds=(end - start) / 1e9, exception=error)


def timed(stage):
    def decorate(fn):
        if inspect.iscoroutinefunction(fn):
            @wraps(fn)
            async def measured(*args, **kwargs):
                if _trace.get() is None:
                    return await fn(*args, **kwargs)
                with phase(stage):
                    return await fn(*args, **kwargs)
        else:
            @wraps(fn)
            def measured(*args, **kwargs):
                if _trace.get() is None:
                    return fn(*args, **kwargs)
                with phase(stage):
                    return fn(*args, **kwargs)
        return measured
    return decorate


def observation(fn):
    """Keep optional telemetry failures out of the evaluator result."""
    @wraps(fn)
    def observe(*args, **kwargs):
        if not tracing():
            return
        try:
            fn(*args, **kwargs)
        except Exception as exc:
            _log.warning("Could not record %s: %s", fn.__name__, exc)
    return observe


def configured_seed():
    value = os.environ.get(SEED_ENV)
    if not value:
        return None
    seed = int(value)
    if not 0 <= seed < SEED_LIMIT:
        raise ValueError(f"{SEED_ENV} must be between 0 and {SEED_LIMIT - 1}")
    return seed


def derive_seed(seed, *labels):
    data = json.dumps([seed, *labels]).encode()
    return int.from_bytes(hashlib.sha256(data).digest()[:4], "big") % SEED_LIMIT


def seed_python_numpy(seed):
    import numpy as np

    random.seed(seed)
    np.random.seed(seed)


def local_chat_seed(kwargs):
    if os.environ.get(OLLAMA_SEED_ENV) != "1" or kwargs.get("seed") is not None:
        return kwargs
    seed = configured_seed()
    if seed is None:
        return kwargs
    trace = _trace.get()
    if trace is None:
        labels = ("run_chat", next(_global_chat_calls))
    else:
        identity = trace[1]
        labels = ("candidate_chat", identity.get("generation"), next(_chat_calls.get()))
    return {**kwargs, "seed": derive_seed(seed, *labels)}


def local_chat_request(request):
    """HTTPX hook for each send, including OpenAI SDK transport retries."""
    if _trace.get() is None or request.method != "POST" or not request.url.path.endswith("/chat/completions"):
        return
    # Read only the model and seed, never persist messages, URLs, or headers.
    try:
        body = json.loads(request.content)
        seed, model = body.get("seed"), body.get("model")
    except (ValueError, AttributeError, TypeError, RuntimeError):
        seed, model = None, None
    event("llm_request", model=model, seed=seed, parent=_parent.get())


async def local_chat_request_async(request):
    local_chat_request(request)
