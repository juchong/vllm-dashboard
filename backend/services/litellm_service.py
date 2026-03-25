"""
LiteLLM model sync service.

Keeps LiteLLM's model registry in sync with the vLLM dashboard's active
configurations so that downstream consumers (Open WebUI) always see the
currently loaded models.
"""

import os
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

MANAGED_BY_TAG = "vllm-dashboard"
DEFAULT_TIMEOUT = 600


class LiteLLMService:
    """Manages model entries in LiteLLM via its admin API."""

    def __init__(self, api_base: str, master_key: str):
        self.api_base = api_base.rstrip("/")
        self.master_key = master_key
        self._headers = {
            "Authorization": f"Bearer {master_key}",
            "Content-Type": "application/json",
        }

    async def _get_managed_models(self, instance_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch models from LiteLLM tagged as managed by vllm-dashboard.

        If instance_id is given, only return models for that instance.
        """
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.api_base}/model/info",
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])

        results = []
        for model in data:
            info = model.get("model_info", {})
            if info.get("managed_by") != MANAGED_BY_TAG:
                continue
            if instance_id is not None and info.get("vllm_instance_id") != instance_id:
                continue
            results.append(model)
        return results

    async def _delete_model(self, model_id: str) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.api_base}/model/delete",
                headers=self._headers,
                json={"id": model_id},
            )
            resp.raise_for_status()

    async def _add_model(
        self,
        instance_id: str,
        served_model_name: str,
        api_base: str,
        api_key: str,
    ) -> None:
        payload = {
            "model_name": served_model_name,
            "litellm_params": {
                "model": f"hosted_vllm/{served_model_name}",
                "api_base": api_base,
                "api_key": api_key,
                "stream_timeout": DEFAULT_TIMEOUT,
                "timeout": DEFAULT_TIMEOUT,
            },
            "model_info": {
                "managed_by": MANAGED_BY_TAG,
                "vllm_instance_id": instance_id,
            },
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.api_base}/model/new",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()

    async def sync_instance_model(
        self,
        instance_id: str,
        served_model_name: str,
        container_name: str,
        port: int,
        api_key: str,
    ) -> None:
        """Replace the LiteLLM model entry for a vLLM instance with the new model."""
        vllm_api_base = f"http://{container_name}:{port}/v1"
        try:
            old_models = await self._get_managed_models(instance_id)
            for model in old_models:
                mid = model.get("model_info", {}).get("id")
                if mid:
                    await self._delete_model(mid)
                    logger.info("[litellm-sync] Deleted old model %s for instance %s", mid, instance_id)

            await self._add_model(instance_id, served_model_name, vllm_api_base, api_key)
            logger.info(
                "[litellm-sync] Added model '%s' for instance %s -> %s",
                served_model_name, instance_id, vllm_api_base,
            )
        except Exception:
            logger.exception("[litellm-sync] Failed to sync instance %s", instance_id)

    async def remove_instance_models(self, instance_id: str) -> None:
        """Remove all LiteLLM model entries for a vLLM instance."""
        try:
            models = await self._get_managed_models(instance_id)
            for model in models:
                mid = model.get("model_info", {}).get("id")
                if mid:
                    await self._delete_model(mid)
                    logger.info("[litellm-sync] Removed model %s for instance %s", mid, instance_id)
            if not models:
                logger.debug("[litellm-sync] No models to remove for instance %s", instance_id)
        except Exception:
            logger.exception("[litellm-sync] Failed to remove models for instance %s", instance_id)

    async def sync_all_instances(self, instance_registry) -> None:
        """Sync all instances that have an active config to LiteLLM.

        Intended for startup. Also cleans up orphaned dashboard-managed
        models that no longer correspond to a registered instance.
        """
        try:
            instances = instance_registry.list_instances()
        except Exception:
            logger.exception("[litellm-sync] Failed to list instances for startup sync")
            return

        active_instance_ids = set()

        for inst in instances:
            inst_id = inst["id"]
            try:
                svc = instance_registry.get_vllm_service(inst_id)
                active = svc.get_active_config()
                if not active:
                    continue

                config = active.get("config", {})
                served_name = config.get("served_model_name") or config.get("model", "")
                if not served_name:
                    continue

                container_name = inst["container_name"]
                port = inst["port"]
                api_key = svc.api_key or os.environ.get("VLLM_API_KEY", "")

                await self.sync_instance_model(inst_id, served_name, container_name, port, api_key)
                active_instance_ids.add(inst_id)
            except Exception:
                logger.exception("[litellm-sync] Startup sync failed for instance %s", inst_id)

        try:
            all_managed = await self._get_managed_models()
            for model in all_managed:
                mid = model.get("model_info", {}).get("id")
                orphan_id = model.get("model_info", {}).get("vllm_instance_id")
                if orphan_id and orphan_id not in {i["id"] for i in instances} and mid:
                    await self._delete_model(mid)
                    logger.info("[litellm-sync] Cleaned up orphaned model %s (instance %s)", mid, orphan_id)
        except Exception:
            logger.exception("[litellm-sync] Failed to clean up orphaned models")
