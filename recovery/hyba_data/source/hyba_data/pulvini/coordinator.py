"""
Global Cluster Coordinator - Leader election + global state management
"""

import time
from typing import Dict, Optional


class GlobalCoordinator:
    """Leader election + global state management for distributed coordination"""

    def __init__(self, redis_client, node_id: str, leader_ttl: int = 30):
        self.redis = redis_client
        self.node_id = node_id
        self.leader_ttl = leader_ttl
        self.leader_key = "pulvini:leader"
        self.heartbeat_prefix = "pulvini:leader_heartbeat"

    async def elect_leader(self) -> bool:
        """
        Redis-based leader election using SETNX

        Returns:
            True if this node became leader, False otherwise
        """
        # Try to acquire leadership
        acquired = await self.redis.set(self.leader_key, self.node_id, nx=True, ex=self.leader_ttl)

        if acquired:
            # Set initial heartbeat
            await self.redis.set(
                f"{self.heartbeat_prefix}:{self.node_id}", str(time.time()), ex=self.leader_ttl
            )
            return True

        return False

    async def heartbeat(self) -> bool:
        """
        Leader heartbeat to maintain leadership

        Returns:
            True if still leader, False if lost leadership
        """
        current_leader = await self.redis.get(self.leader_key)

        if current_leader and current_leader.decode() == self.node_id:
            # Refresh leadership TTL
            await self.redis.expire(self.leader_key, self.leader_ttl)
            await self.redis.set(
                f"{self.heartbeat_prefix}:{self.node_id}", str(time.time()), ex=self.leader_ttl
            )
            return True

        return False

    async def get_leader(self) -> Optional[str]:
        """Get current leader node ID"""
        leader = await self.redis.get(self.leader_key)
        return leader.decode() if leader else None

    async def is_leader(self) -> bool:
        """Check if this node is the current leader"""
        leader = await self.get_leader()
        return leader == self.node_id

    async def step_down(self):
        """Step down from leadership"""
        if await self.is_leader():
            await self.redis.delete(self.leader_key)
            await self.redis.delete(f"{self.heartbeat_prefix}:{self.node_id}")

    async def get_cluster_state(self) -> Dict:
        """Get cluster state including leader and heartbeats"""
        leader = await self.get_leader()

        # Get all heartbeats
        heartbeat_keys = await self.redis.keys(f"{self.heartbeat_prefix}:*")
        heartbeats = {}

        for key in heartbeat_keys:
            try:
                node_id = key.decode().split(":")[-1]
                heartbeat = await self.redis.get(key)
                if heartbeat:
                    heartbeats[node_id] = {
                        "timestamp": float(heartbeat.decode()),
                        "active": (time.time() - float(heartbeat.decode())) < (self.leader_ttl * 2),
                    }
            except (ValueError, TypeError, AttributeError):
                continue

        return {
            "leader": leader,
            "is_leader": await self.is_leader(),
            "heartbeats": heartbeats,
            "active_nodes": sum(1 for h in heartbeats.values() if h["active"]),
        }

    async def wait_for_leadership(self, timeout: float = 60.0, poll_interval: float = 1.0) -> bool:
        """
        Wait for this node to become leader

        Args:
            timeout: Maximum time to wait in seconds
            poll_interval: Polling interval in seconds

        Returns:
            True if became leader, False if timeout
        """
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            if await self.elect_leader():
                return True
            await asyncio.sleep(poll_interval)

        return False

    async def nominate_leader(self, node_id: str):
        """Nominate a specific node as leader (manual override)"""
        await self.redis.set(self.leader_key, node_id, ex=self.leader_ttl)
        await self.redis.set(
            f"{self.heartbeat_prefix}:{node_id}", str(time.time()), ex=self.leader_ttl
        )


# Import asyncio for wait_for_leadership
import asyncio
