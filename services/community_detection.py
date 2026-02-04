"""Community detection service for GraphRAG."""

from dataclasses import dataclass
from typing import Any

import networkx as nx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.community import CommunitySummary, EntityCommunity
from models.entity import Entity
from models.relationship import Relationship


@dataclass
class DetectedCommunity:
    """A detected community with its members."""

    community_id: int
    members: list[str]
    level: int


class CommunityDetection:
    """Detect communities in the knowledge graph."""

    def __init__(self, resolution: float = 1.0):
        self.resolution = resolution

    async def detect_communities(
        self,
        db: AsyncSession,
    ) -> list[DetectedCommunity]:
        """Detect communities in the knowledge graph."""
        result = await db.execute(select(Relationship.source_id, Relationship.target_id))
        relationships = result.all()

        if not relationships:
            return []

        G = nx.Graph()

        for rel in relationships:
            G.add_edge(rel.source_id, rel.target_id)

        result = await db.execute(select(Entity.entity_id))
        all_entities = [row[0] for row in result.all()]
        G.add_nodes_from(all_entities)

        communities = nx.community.greedy_modularity_communities(
            G,
            resolution=self.resolution,
        )

        detected = []
        for idx, community in enumerate(communities):
            detected.append(
                DetectedCommunity(
                    community_id=idx,
                    members=list(community),
                    level=1,
                )
            )

        return detected

    async def save_communities(
        self,
        db: AsyncSession,
        communities: list[DetectedCommunity],
    ) -> None:
        """Save detected communities to database."""
        await db.execute(delete(EntityCommunity))
        await db.execute(delete(CommunitySummary))

        for community in communities:
            for entity_id in community.members:
                db.add(
                    EntityCommunity(
                        entity_id=entity_id,
                        community_id=community.community_id,
                        community_level=community.level,
                    )
                )

        await db.commit()

    async def compute_and_save(
        self,
        db: AsyncSession,
    ) -> list[DetectedCommunity]:
        """Detect and save communities in one operation."""
        communities = await self.detect_communities(db)
        await self.save_communities(db, communities)
        return communities

    async def get_community_stats(
        self,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Get statistics about communities."""
        result = await db.execute(select(EntityCommunity.community_id, EntityCommunity.entity_id))
        memberships = result.all()

        if not memberships:
            return {
                "total_communities": 0,
                "total_entities": 0,
                "avg_community_size": 0,
                "largest_community": 0,
                "smallest_community": 0,
            }

        community_sizes: dict[int, int] = {}
        for membership in memberships:
            cid = membership.community_id
            community_sizes[cid] = community_sizes.get(cid, 0) + 1

        sizes = list(community_sizes.values())

        return {
            "total_communities": len(community_sizes),
            "total_entities": len({m.entity_id for m in memberships}),
            "avg_community_size": sum(sizes) / len(sizes),
            "largest_community": max(sizes),
            "smallest_community": min(sizes),
        }
