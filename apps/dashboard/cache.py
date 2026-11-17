from typing import Callable
from django.core.cache import cache

DASHBOARD_VERSION_KEY = "dashboard:aggregate:version"
DEFAULT_DASHBOARD_CACHE_TTL = 60  # 60 seconds


def get_dashboard_cache_version() -> int:
    """
    Returns the current monotonic cache version for school-wide dashboard aggregations.
    """
    version = cache.get(DASHBOARD_VERSION_KEY)
    if version is None:
        version = 1
        cache.set(DASHBOARD_VERSION_KEY, version, timeout=None)
    return int(version)


def bump_dashboard_cache_version() -> int:
    """
    Increments the dashboard cache version, instantaneously invalidating all
    previously cached administrator analytics and overview payloads.
    """
    try:
        return cache.incr(DASHBOARD_VERSION_KEY)
    except ValueError:
        cache.set(DASHBOARD_VERSION_KEY, 2, timeout=None)
        return 2


def get_or_compute_admin_aggregate(
    namespace: str,
    params: dict,
    builder_fn: Callable[[], dict],
    force_refresh: bool = False,
    ttl: int = DEFAULT_DASHBOARD_CACHE_TTL,
) -> dict:
    """
    Safely caches school-wide, non-personal administrator aggregate payloads.
    Scoped by the current cache version and normalized query parameters.
    """
    version = get_dashboard_cache_version()
    sorted_params = ":".join(f"{k}={v or 'default'}" for k, v in sorted(params.items()))
    cache_key = f"dashboard:v{version}:{namespace}:{sorted_params}"

    if not force_refresh:
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            return cached_payload

    payload = builder_fn()
    cache.set(cache_key, payload, timeout=ttl)
    return payload