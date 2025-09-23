from rest_framework import generics, permissions, filters, status
from rest_framework.response import Response
from django.db.models import Prefetch

from .models import Category, Product, Banner, CartItem, InfoPage
from .serializers import (
    CategorySerializer, CategoryFlatSerializer,
    ProductSerializer, BannerSerializer, CartItemSerializer,
    InfoPageSerializer,
)

# --- Категории ---

class CategoryTreeView(generics.ListAPIView):
    """
    GET /api/categories/ — категории только верхнего уровня
    с подкатегориями (prefetch).
    """
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        # Prefetch подкатегорий, чтобы не было N+1
        return Category.objects.filter(parent__isnull=True).prefetch_related(
            Prefetch("subcategories", queryset=Category.objects.all())
        )

class CategoryFlatView(generics.ListAPIView):
    """
    GET /api/categories/flat/ — плоский список всех категорий.
    """
    serializer_class = CategoryFlatSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Category.objects.all()
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "id"]
    ordering = ["name"]

# --- Продукты ---

class ProductListView(generics.ListAPIView):
    """
    GET /api/products/?category_id=...
    """
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["id", "price", "name"]
    ordering = ["-id"]

    def get_queryset(self):
        qs = Product.objects.all().prefetch_related("sizes")
        category_id = self.request.query_params.get("category_id")
        if category_id:
            qs = qs.filter(category_id=category_id)
        return qs

# --- Баннеры ---

class BannerListView(generics.ListAPIView):
    """
    GET /api/banners/
    """
    serializer_class = BannerSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Banner.objects.all().order_by("-id")

# --- Корзина ---

class CartView(generics.ListCreateAPIView):
    """
    GET  /api/cart/?user_id=...
    POST /api/cart/ {user_id, product_id, quantity}
    """
    serializer_class = CartItemSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        user_id = self.request.query_params.get("user_id")
        return CartItem.objects.filter(user_id=user_id).select_related("product")

    def create(self, request, *args, **kwargs):
        user_id = request.data.get("user_id")
        product_id = request.data.get("product_id")
        quantity = int(request.data.get("quantity", 1))
        if not (user_id and product_id):
            return Response({"detail": "user_id и product_id обязательны"}, status=status.HTTP_400_BAD_REQUEST)
        item, _ = CartItem.objects.get_or_create(
            user_id=user_id, product_id=product_id,
            defaults={"quantity": 0}
        )
        item.quantity = (item.quantity or 0) + max(quantity, 1)
        item.save()
        return Response({"ok": True, "id": item.id, "quantity": item.quantity}, status=status.HTTP_201_CREATED)

class CheckoutView(generics.CreateAPIView):
    """
    POST /api/cart/checkout/ {user_id, seller_username?}
    Возвращает содержимое корзины и redirect-ссылку на ЛС продавца.
    """
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        user_id = request.data.get("user_id")
        seller_username = request.data.get("seller_username")
        if not user_id:
            return Response({"detail": "user_id обязателен"}, status=status.HTTP_400_BAD_REQUEST)
        items = CartItem.objects.filter(user_id=user_id).select_related("product")
        payload = CartItemSerializer(items, many=True, context={"request": request}).data
        link = f"https://t.me/{seller_username}" if seller_username else None
        return Response({"cart": payload, "redirect_to": link}, status=status.HTTP_200_OK)

# --- InfoPage на generics (если используешь) ---

class InfoPageListView(generics.ListAPIView):
    """
    GET /api/info/
    """
    queryset = InfoPage.objects.filter(is_active=True).order_by("sort_order", "title")
    serializer_class = InfoPageSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["title", "slug", "external_url"]
    ordering_fields = ["sort_order", "title", "updated_at"]
    ordering = ["sort_order", "title"]

class InfoPageDetailView(generics.RetrieveAPIView):
    """
    GET /api/info/<slug>/
    """
    queryset = InfoPage.objects.filter(is_active=True)
    serializer_class = InfoPageSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"