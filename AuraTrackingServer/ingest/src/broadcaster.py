import asyncio
import time
import structlog
from typing import Dict, Set, Optional, Any

logger = structlog.get_logger("broadcaster")

class TelemetryBroadcaster:
    """
    Gerencia o broadcast interno de telemetria em memória.
    
    Funcionalidades:
    - Throttling por device_id (default 5s)
    - Thread-safe (pode ser chamado da thread MQTT)
    - Desacoplado (fire-and-forget)
    """
    
    def __init__(self, throttle_seconds: float = 5.0):
        self.throttle_seconds = throttle_seconds
        self._subscribers: Set[asyncio.Queue] = set()
        self._last_broadcast: Dict[str, float] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stats = {
            "events_received": 0,
            "events_emitted": 0,
            "events_dropped_throttle": 0,
            "events_dropped_queue_full": 0
        }

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Define o event loop principal (chamado no startup do FastAPI)."""
        self._loop = loop
        logger.info("broadcaster_loop_set")

    def publish(self, device_id: str, payload: Any):
        """
        Publica um evento de telemetria.
        Pode ser chamado de qualquer thread (ex: MQTT).
        """
        self._stats["events_received"] += 1
        
        # 1. Throttling (Check rápido em memória)
        now = time.time()
        last_time = self._last_broadcast.get(device_id, 0)
        
        if (now - last_time) < self.throttle_seconds:
            self._stats["events_dropped_throttle"] += 1
            return

        # 2. Atualiza timestamp
        self._last_broadcast[device_id] = now
        
        # 3. Despacha para o loop principal
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(
                self._broadcast_to_subscribers, 
                payload
            )
        else:
            # Se o loop não estiver pronto, dropamos silenciosamente (fase de startup/shutdown)
            pass

    def _broadcast_to_subscribers(self, payload: Any):
        """Executa no loop principal: distribui para filas."""
        if not self._subscribers:
            return

        self._stats["events_emitted"] += 1
        
        # Copia para evitar erro de modificação durante iteração
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                self._stats["events_dropped_queue_full"] += 1
                # Estratégia: Drop tail (ignora o novo)
                # Alternativa: Drop head (remove antigo e insere novo) - mais complexo
                pass

    async def subscribe(self) -> asyncio.Queue:
        """Cria uma nova fila de assinatura."""
        queue = asyncio.Queue(maxsize=100) # Buffer limitado para evitar OOM
        self._subscribers.add(queue)
        logger.debug("subscriber_added", total=len(self._subscribers))
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Remove uma fila de assinatura."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)
            logger.debug("subscriber_removed", total=len(self._subscribers))

    def cleanup_stale_devices(self, max_age_seconds: float = 3600):
        """Remove dispositivos que não enviam dados há muito tempo."""
        now = time.time()
        to_remove = []
        
        for device_id, last_seen in self._last_broadcast.items():
            if (now - last_seen) > max_age_seconds:
                to_remove.append(device_id)
        
        for device_id in to_remove:
            del self._last_broadcast[device_id]
            
        if to_remove:
            logger.info("cleanup_stale_devices", removed=len(to_remove), remaining=len(self._last_broadcast))

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "active_subscribers": len(self._subscribers),
            "tracked_devices": len(self._last_broadcast)
        }
