"""Compute and update graph metrics for entities.

This script calculates graph centrality metrics (PageRank, degree centrality,
betweenness) for all entities in the knowledge graph and updates the database.

Usage:
    python scripts/compute_graph_metrics.py

"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.database import get_session_maker
from models.entity import Entity
from models.relationship import Relationship


try:
    import networkx as nx

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    print("Warning: networkx not installed. Install with: pip install networkx")


async def fetch_relationships(db: AsyncSession) -> list[tuple[str, str, str]]:
    """Fetch all relationships as (source_id, target_id, relation_type) tuples."""
    result = await db.execute(
        select(Relationship.source_id, Relationship.target_id, Relationship.relation_type)
    )
    return [(row.source_id, row.target_id, row.relation_type) for row in result.all()]


async def fetch_all_entities(db: AsyncSession) -> list[Entity]:
    """Fetch all entities."""
    result = await db.execute(select(Entity))
    return list(result.scalars().all())


def compute_graph_metrics(relationships: list[tuple[str, str, str]]) -> dict[str, dict]:
    """Compute graph metrics using NetworkX.

    Returns dict mapping entity_id -> metrics dict.
    """
    if not NETWORKX_AVAILABLE:
        raise RuntimeError("networkx is required to compute graph metrics")

    # Build directed graph
    G = nx.DiGraph()

    # Add all entities as nodes (we'll get entity list separately)
    # Add edges from relationships
    for source_id, target_id, relation_type in relationships:
        G.add_edge(source_id, target_id, relation_type=relation_type)

    # Compute metrics
    metrics = {}

    # PageRank (for directed graph)
    try:
        pagerank = nx.pagerank(G)
    except:
        # Fallback if PageRank fails (e.g., on certain graph structures)
        pagerank = {}

    # Degree centrality (normalized)
    in_degree = dict(G.in_degree())
    out_degree = dict(G.out_degree())
    degree = dict(G.degree())

    # Betweenness centrality (can be expensive on large graphs)
    try:
        betweenness = nx.betweenness_centrality(G)
    except:
        betweenness = {}

    # Combine all entities
    all_entities = set(G.nodes())

    for entity_id in all_entities:
        metrics[entity_id] = {
            "pagerank_score": pagerank.get(entity_id, 0.0),
            "degree_centrality": degree.get(entity_id, 0),
            "betweenness_score": betweenness.get(entity_id, 0.0),
            "relationship_count": degree.get(entity_id, 0),
            "in_degree": in_degree.get(entity_id, 0),
            "out_degree": out_degree.get(entity_id, 0),
        }

    return metrics


async def update_entity_metrics(
    db: AsyncSession,
    entity: Entity,
    metrics: dict,
) -> None:
    """Update entity with computed metrics."""
    entity.pagerank_score = metrics.get("pagerank_score", 0.0)
    entity.degree_centrality = metrics.get("degree_centrality", 0)
    entity.betweenness_score = metrics.get("betweenness_score", 0.0)
    entity.relationship_count = metrics.get("relationship_count", 0)
    entity.in_degree = metrics.get("in_degree", 0)
    entity.out_degree = metrics.get("out_degree", 0)
    entity.metrics_updated_at = datetime.now(timezone.utc).replace(tzinfo=None)


async def compute_and_update_metrics() -> None:
    """Main function to compute and update all graph metrics."""
    if not NETWORKX_AVAILABLE:
        print("Error: networkx is required. Install with: pip install networkx")
        sys.exit(1)

    session_maker = get_session_maker()
    if session_maker is None:
        print("Error: Database not configured")
        sys.exit(1)

    async with session_maker() as db:
        print("Fetching relationships...")
        relationships = await fetch_relationships(db)
        print(f"  Found {len(relationships)} relationships")

        if not relationships:
            print("No relationships found. Nothing to compute.")
            return

        print("Fetching entities...")
        entities = await fetch_all_entities(db)
        print(f"  Found {len(entities)} entities")

        print("Computing graph metrics...")
        metrics_by_entity = compute_graph_metrics(relationships)
        print(f"  Computed metrics for {len(metrics_by_entity)} entities")

        print("Updating database...")
        updated_count = 0
        for entity in entities:
            if entity.entity_id in metrics_by_entity:
                await update_entity_metrics(db, entity, metrics_by_entity[entity.entity_id])
                updated_count += 1
            else:
                # Entity has no relationships - set defaults
                entity.pagerank_score = 0.0
                entity.degree_centrality = 0
                entity.betweenness_score = 0.0
                entity.relationship_count = 0
                entity.in_degree = 0
                entity.out_degree = 0
                entity.metrics_updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                updated_count += 1

        await db.commit()
        print(f"  Updated {updated_count} entities")

        # Print top entities by PageRank
        sorted_by_pagerank = sorted(
            metrics_by_entity.items(),
            key=lambda x: x[1]["pagerank_score"],
            reverse=True,
        )[:10]

        print("\nTop 10 entities by PageRank:")
        for entity_id, metrics in sorted_by_pagerank:
            entity = next((e for e in entities if e.entity_id == entity_id), None)
            if entity:
                print(f"  {entity.name}: {metrics['pagerank_score']:.4f}")

        print("\nDone!")


if __name__ == "__main__":
    asyncio.run(compute_and_update_metrics())
