import logging
from typing import Callable, Dict, Optional, Type

from fastapi import APIRouter
from pydantic import BaseModel

from eunomia.fetchers.base import BaseFetcher, BaseFetcherConfig


class FetcherRegistryEntry(BaseModel):
    fetcher_cls: Type[BaseFetcher]
    config_cls: Type[BaseFetcherConfig]
    router_factory: Optional[Callable[[BaseFetcher], APIRouter]] = None


class FetcherFactory:
    """
    Factory for creating and managing fetcher instances.

    This factory allows registering fetchers and creating
    instances based on configuration.
    """

    _registry: Dict[str, FetcherRegistryEntry] = {}
    _instances: Dict[str, BaseFetcher] = {}
    _routers: Dict[str, APIRouter] = {}

    @classmethod
    def register_fetcher(
        cls,
        fetcher_id: str,
        fetcher_cls: Type[BaseFetcher],
        config_cls: Type[BaseFetcherConfig],
        router_factory: Optional[Callable[[BaseFetcher], APIRouter]] = None,
    ) -> None:
        cls._registry[fetcher_id] = FetcherRegistryEntry(
            fetcher_cls=fetcher_cls,
            config_cls=config_cls,
            router_factory=router_factory,
        )
        logging.info(f"Registered fetcher: {fetcher_id}")

    @classmethod
    def create_fetcher(cls, fetcher_id: str, config: BaseFetcherConfig) -> BaseFetcher:
        # Avoid repeated dict lookups and attribute accesses for speed
        try:
            registry_entry = cls._registry[fetcher_id]
        except KeyError:
            raise ValueError(f"Fetcher not registered: {fetcher_id}")

        # Cache attribute lookups to local variables
        config_cls = registry_entry.config_cls
        fetcher_cls = registry_entry.fetcher_cls

        # model_validate could be slow; avoid redundant validations if config is already the right type
        if type(config) is config_cls:
            # Assume config is already validated if type matches exactly
            fetcher_config = config
        else:
            fetcher_config = config_cls.model_validate(config)

        return fetcher_cls(fetcher_config)

    @classmethod
    def initialize_fetchers(cls, fetcher_configs: dict[str, BaseFetcherConfig]) -> None:
        instances = {}
        routers = {}

        for fetcher_id, fetcher_config in fetcher_configs.items():
            fetcher = cls.create_fetcher(fetcher_id=fetcher_id, config=fetcher_config)
            instances[fetcher_id] = fetcher
            logging.info(f"Initialized fetcher: {fetcher_id}")

            # Create router if a router factory is available
            registry_entry = cls._registry[fetcher_id]
            if registry_entry.router_factory:
                router = registry_entry.router_factory(fetcher)
                routers[fetcher_id] = router
                logging.info(f"Initialized router for fetcher: {fetcher_id}")

        cls._instances = instances
        cls._routers = routers

        # Call post_init for all fetchers
        for fetcher in cls._instances.values():
            fetcher.post_init()

        logging.info("All fetchers initialized")

    @classmethod
    def get_fetcher(cls, fetcher_id: str) -> BaseFetcher:
        if fetcher_id not in cls._instances:
            raise ValueError(f"Fetcher not initialized: {fetcher_id}")
        return cls._instances[fetcher_id]

    @classmethod
    def get_all_fetchers(cls) -> Dict[str, BaseFetcher]:
        return cls._instances

    @classmethod
    def get_router(cls, fetcher_id: str) -> APIRouter:
        if fetcher_id not in cls._routers:
            raise ValueError(f"Router not available for fetcher: {fetcher_id}")
        return cls._routers[fetcher_id]

    @classmethod
    def get_all_routers(cls) -> Dict[str, APIRouter]:
        return cls._routers
