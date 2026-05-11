import time

try:
    import routeros_api  # type: ignore
except Exception:  # pragma: no cover - dependency may be absent in development/self-test envs
    routeros_api = None


class RouterDependencyError(RuntimeError):
    pass


def connect_to_router(router: dict, retries: int = 3):
    if routeros_api is None:
        return None, None, "Missing dependency: routeros-api is not installed. Run pip install -r requirements.txt"
    last = None
    for attempt in range(1, retries + 1):
        try:
            pool = routeros_api.RouterOsApiPool(
                router["address"],
                username=router["username"],
                password=router["password"],
                port=int(router.get("port", 8728)),
                plaintext_login=True,
            )
            api = pool.get_api()
            return pool, api, None
        except Exception as e:
            last = str(e)
            if attempt < retries:
                time.sleep(2)
    return None, None, last or "unknown RouterOS API error"


def get_resource_data(api, resource_path: str, properties: list[str] | tuple[str, ...] | None = None, **filters) -> list:
    """Return RouterOS resource rows, optionally using .proplist filtering.

    RouterOS selective property reads reduce payload size for large PPP/DHCP/HS
    tables. If the RouterOS API library or device rejects .proplist, this
    helper falls back to the unfiltered read so older installs keep working.
    """
    try:
        resource = api.get_resource(resource_path)
        request = dict(filters or {})
        if properties:
            request[".proplist"] = ",".join([str(x) for x in properties if x])
        try:
            result = resource.get(**request) if request else resource.get()
        except Exception:
            # Some RouterOS/API combinations may not accept .proplist through
            # the wrapper. Fall back to the previous full-resource behavior.
            if properties:
                result = resource.get(**filters) if filters else resource.get()
            else:
                raise
        if isinstance(result, list):
            return result
        try:
            return list(result)
        except Exception:
            return []
    except Exception:
        return []


def selective_enabled(config: dict) -> bool:
    return bool(config.get("collector", {}).get("selective_fields", True))


def read_resource(api, resource_path: str, config: dict, properties: list[str] | tuple[str, ...], **filters) -> list:
    if selective_enabled(config):
        return get_resource_data(api, resource_path, properties=properties, **filters)
    return get_resource_data(api, resource_path, **filters)


def test_router_connection(router: dict):
    start = time.time()
    pool, api, err = connect_to_router(router, retries=1)
    latency = round((time.time() - start) * 1000, 2)
    if pool:
        try:
            pool.disconnect()
        except Exception:
            pass
    return {"ok": api is not None, "latency_ms": latency if api else None, "error": err}
