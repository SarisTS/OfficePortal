import redis

from app.core.config import settings

# Lazy-connect Redis client. The constructor only stashes config; the
# first command (ping / setex / get) actually opens the socket. Host
# defaults to localhost so local dev with `redis-server` works without
# any env vars; docker-compose injects REDIS_HOST=redis.
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD or None,  # str "" → None (no auth)
    decode_responses=True,  # commands return str, not bytes
)
