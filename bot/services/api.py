import os
import aiohttp

BASE = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000/api")

class ApiClient:
    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    async def get_categories(self, tree: bool = True):
        url = f"{BASE}/categories/" if tree else f"{BASE}/categories/flat/"
        async with self.session.get(url) as r:
            r.raise_for_status()
            return await r.json()

    async def get_products(self, category_id: int | None = None):
        url = f"{BASE}/products/"
        params = {"category_id": category_id} if category_id else None
        async with self.session.get(url, params=params) as r:
            r.raise_for_status()
            return await r.json()

    async def add_to_cart(self, user_id: str, product_id: int, quantity: int = 1):
        url = f"{BASE}/cart/"
        async with self.session.post(url, json={"user_id": user_id, "product_id": product_id, "quantity": quantity}) as r:
            r.raise_for_status()
            return await r.json()

    async def get_cart(self, user_id: str):
        url = f"{BASE}/cart/"
        async with self.session.get(url, params={"user_id": user_id}) as r:
            r.raise_for_status()
            return await r.json()

    async def checkout(self, user_id: str, seller_username: str | None = None):
        url = f"{BASE}/cart/checkout/"
        payload = {"user_id": user_id}
        if seller_username:
            payload["seller_username"] = seller_username
        async with self.session.post(url, json=payload) as r:
            r.raise_for_status()
            return await r.json()