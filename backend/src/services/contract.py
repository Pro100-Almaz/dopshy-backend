import os
import typing

import fastapi
import httpx

from src.config.manager import settings


class ContractService:
    async def _request(
        self,
        method: str,
        path: str,
        json: typing.Any | None = None,
        params: dict[str, typing.Any] | None = None,
        timeout: float = 10.0,
    ) -> tuple[int, typing.Any]:
        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="BOT_URL is not configured.",
            )

        manager_api_key = (
            os.getenv("X_SERVICE_TOKEN") or os.getenv("MANAGER_API_KEY") or settings.MANAGER_API_KEY or ""
        )
        headers = {
            "Accept": "application/json",
            "X-API-Key": manager_api_key,
        }
        if manager_api_key:
            headers["Authorization"] = f"Bearer {manager_api_key}"
        if json is not None:
            headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.request(
                    method,
                    base_url.rstrip("/") + path,
                    headers=headers,
                    json=json,
                    params=params,
                )
            except httpx.HTTPError as exc:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to reach the bot service.",
                ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="Bot service returned a non-JSON response.",
            ) from exc

        if response.status_code in (
            fastapi.status.HTTP_401_UNAUTHORIZED,
            fastapi.status.HTTP_403_FORBIDDEN,
        ):
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="Bot service authentication failed. Check MANAGER_API_KEY between backend and bot.",
            )

        return response.status_code, payload

    async def list_contracts(self, page: int | None = None, search: str | None = None) -> tuple[int, typing.Any]:
        params: dict[str, typing.Any] = {}
        if page is not None:
            params["page"] = page
        if search is not None:
            params["search"] = search
        return await self._request("GET", "/api/manager/contracts", params=params or None)

    async def get_contract(self, contract_id: int) -> tuple[int, typing.Any]:
        return await self._request("GET", f"/api/manager/contracts/{contract_id}")

    async def create_contract(self, payload: dict[str, typing.Any]) -> tuple[int, typing.Any]:
        # Creation may run the Kaspi check on the payer and expand up to 1000 bookings.
        return await self._request("POST", "/api/manager/contracts", json=payload, timeout=30.0)

    async def update_contract(self, contract_id: int, payload: dict[str, typing.Any]) -> tuple[int, typing.Any]:
        return await self._request("PATCH", f"/api/manager/contracts/{contract_id}", json=payload)

    async def delete_contract(self, contract_id: int) -> tuple[int, typing.Any]:
        return await self._request("DELETE", f"/api/manager/contracts/{contract_id}")

    async def create_contract_bookings(
        self,
        contract_id: int,
        payload: dict[str, typing.Any],
    ) -> tuple[int, typing.Any]:
        return await self._request("POST", f"/api/manager/contracts/{contract_id}/bookings/batch", json=payload)

    async def update_contract_bookings(
        self,
        contract_id: int,
        payload: dict[str, typing.Any],
    ) -> tuple[int, typing.Any]:
        return await self._request("PATCH", f"/api/manager/contracts/{contract_id}/bookings/batch", json=payload)

    async def delete_contract_bookings(
        self,
        contract_id: int,
        payload: dict[str, typing.Any],
    ) -> tuple[int, typing.Any]:
        return await self._request("DELETE", f"/api/manager/contracts/{contract_id}/bookings/batch", json=payload)

    async def check_contract_slots(self, payload: dict[str, typing.Any]) -> tuple[int, typing.Any]:
        return await self._request("POST", "/api/manager/contracts/check-slots", json=payload)

    async def preview_payment_plan(self, payload: dict[str, typing.Any]) -> tuple[int, typing.Any]:
        return await self._request("POST", "/api/manager/contracts/payment-plan/preview", json=payload)

    async def get_contract_payments(self, contract_id: int) -> tuple[int, typing.Any]:
        return await self._request("GET", f"/api/manager/contracts/{contract_id}/payments")

    async def replace_payment_plan(
        self,
        contract_id: int,
        payload: dict[str, typing.Any],
    ) -> tuple[int, typing.Any]:
        return await self._request("PUT", f"/api/manager/contracts/{contract_id}/payment-plan", json=payload)

    async def stop_payment_plan(self, contract_id: int) -> tuple[int, typing.Any]:
        return await self._request("DELETE", f"/api/manager/contracts/{contract_id}/payment-plan")

    async def update_installment(
        self,
        contract_id: int,
        installment_id: int,
        payload: dict[str, typing.Any],
    ) -> tuple[int, typing.Any]:
        return await self._request(
            "PATCH",
            f"/api/manager/contracts/{contract_id}/installments/{installment_id}",
            json=payload,
        )

    async def mark_installment_paid(
        self,
        contract_id: int,
        installment_id: int,
        payload: dict[str, typing.Any],
    ) -> tuple[int, typing.Any]:
        return await self._request(
            "POST",
            f"/api/manager/contracts/{contract_id}/installments/{installment_id}/mark-paid",
            json=payload,
        )

    async def send_installment(self, contract_id: int, installment_id: int) -> tuple[int, typing.Any]:
        return await self._request(
            "POST",
            f"/api/manager/contracts/{contract_id}/installments/{installment_id}/send",
            timeout=30.0,
        )
