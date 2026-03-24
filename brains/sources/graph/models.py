from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from brains.config import GraphPaths, get_config


class GraphIndexConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    paths: GraphPaths

    @classmethod
    def from_settings(
        cls,
        *,
        paths: GraphPaths,
    ) -> "GraphIndexConfig":
        return cls(paths=paths)


class GraphSearchConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    paths: GraphPaths
    query: str
    k: int = Field(default_factory=lambda: get_config().graph.k)
    max_hops: int = Field(default_factory=lambda: get_config().graph.max_hops)

    @classmethod
    def from_settings(
        cls,
        *,
        paths: GraphPaths,
        query: str,
        k: int | None = None,
        max_hops: int | None = None,
    ) -> "GraphSearchConfig":
        config = get_config()
        return cls(
            paths=paths,
            query=query,
            k=config.graph.k if k is None else k,
            max_hops=config.graph.max_hops if max_hops is None else max_hops,
        )


class GraphPathConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    paths: GraphPaths
    source: str
    target: str
    max_hops: int = Field(default=3)

    @classmethod
    def from_settings(
        cls,
        *,
        paths: GraphPaths,
        source: str,
        target: str,
        max_hops: int | None = None,
    ) -> "GraphPathConfig":
        config = get_config()
        return cls(
            paths=paths,
            source=source,
            target=target,
            max_hops=config.graph.max_hops if max_hops is None else max_hops,
        )
