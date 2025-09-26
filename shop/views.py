from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, filters, status
from rest_framework.response import Response
from django.db.models import Prefetch, QuerySet
from rest_framework.views import APIView

from bot.config import BOT_TOKEN
from users.models import TelegramUser
from .models import Category, Product, Banner, CartItem, InfoPage
from .pagination import DefaultPagination
from .serializers import (
    CategorySerializer, CategoryFlatSerializer,
    ProductSerializer, BannerSerializer, CartItemSerializer,
    InfoPageSerializer, CheckoutResponseSerializer, CheckoutRequestSerializer, CartChangeQuantitySerializer,
    CartDeleteItemSerializer, CartClearSerializer, TelegramWebAppAuthRequestSerializer,
    TelegramWebAppAuthResponseSerializer,
)
from .telegram_auth import verify_telegram_init_data


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
    GET /api/products/?category_id=...&sort=new|cheap|expensive
    """
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter]   # оставляем только поиск
    search_fields = ["name", "description"]
    pagination_class = DefaultPagination

    def get_queryset(self) -> QuerySet:
        qs = Product.objects.all().prefetch_related("sizes")

        # --- фильтр по категории ---
        category_id = self.request.query_params.get("category_id")
        if category_id:
            qs = qs.filter(category_id=category_id)

        # --- сортировка ---
        sort = self.request.query_params.get("sort")
        if sort == "cheap":
            qs = qs.order_by("price")
        elif sort == "expensive":
            qs = qs.order_by("-price")
        else:  # new (по умолчанию)
            qs = qs.order_by("-id")

        return qs


class ProductDetailView(generics.RetrieveAPIView):
    """
    GET /api/products/<id>/
    """
    queryset = Product.objects.all().prefetch_related("sizes")
    serializer_class = ProductSerializer   # или ProductSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "pk"

    @extend_schema(summary="Получить продукт по ID")
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

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
    GET  /api/cart/?user_id=123
    POST /api/cart/ {user_id, product_id, quantity}  -> инкремент (добавить к текущему)
    PATCH /api/cart/ {user_id, product_id, delta}     -> изменить на ∆ (может быть отрицательным)
    PUT   /api/cart/ {user_id, product_id, quantity}  -> установить новое кол-во (>=1)
    DELETE /api/cart/ {user_id, product_id}           -> удалить позицию
    """
    serializer_class = CartItemSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        user_id = self.request.query_params.get("user_id")
        return CartItem.objects.filter(user_id=user_id).select_related("product")

    @extend_schema(
        request=CartItemSerializer,  # по факту body: user_id, product_id, quantity
        responses={201: CartItemSerializer},
        examples=None,
        description="Добавить товар в корзину (инкрементирует количество)."
    )
    def create(self, request, *args, **kwargs):
        user_id = request.data.get("user_id")
        product_id = request.data.get("product_id")
        quantity = int(request.data.get("quantity", 1) or 1)
        if not (user_id and product_id):
            return Response({"detail": "user_id и product_id обязательны"}, status=status.HTTP_400_BAD_REQUEST)
        item, _ = CartItem.objects.get_or_create(
            user_id=user_id, product_id=product_id, defaults={"quantity": 0}
        )
        item.quantity = (item.quantity or 0) + max(quantity, 1)
        item.save()
        return Response({"ok": True, "id": item.id, "quantity": item.quantity}, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=CartChangeQuantitySerializer,
        responses={200: CartItemSerializer},
        description="Изменить количество на дельту (delta может быть отрицательным). Если после изменения количество <1 — позиция удаляется."
    )
    def patch(self, request, *args, **kwargs):
        ser = CartChangeQuantitySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = ser.validated_data["user_id"]
        product_id = ser.validated_data["product_id"]
        delta = ser.validated_data["delta"]

        try:
            item = CartItem.objects.get(user_id=user_id, product_id=product_id)
        except CartItem.DoesNotExist:
            return Response({"detail": "Позиция не найдена"}, status=status.HTTP_404_NOT_FOUND)

        new_qty = (item.quantity or 0) + delta
        if new_qty < 1:
            item.delete()
            return Response({"ok": True, "deleted": True}, status=status.HTTP_200_OK)

        item.quantity = new_qty
        item.save()
        return Response({"ok": True, "id": item.id, "quantity": item.quantity}, status=status.HTTP_200_OK)

    @extend_schema(
        request=CartDeleteItemSerializer,
        responses={200: dict},
        description="Удалить конкретную позицию из корзины."
    )
    def delete(self, request, *args, **kwargs):
        ser = CartDeleteItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = ser.validated_data["user_id"]
        product_id = ser.validated_data["product_id"]

        deleted, _ = CartItem.objects.filter(user_id=user_id, product_id=product_id).delete()
        return Response({"ok": True, "deleted": bool(deleted)}, status=status.HTTP_200_OK)


class CartClearView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=CartClearSerializer, responses={200: dict})
    def delete(self, request):
        ser = CartClearSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = ser.validated_data["user_id"]
        deleted, _ = CartItem.objects.filter(user_id=user_id).delete()
        return Response({"ok": True, "deleted_count": deleted}, status=status.HTTP_200_OK)


class CheckoutView(generics.CreateAPIView):
    """
    POST /api/cart/checkout/ {user_id, seller_username?}
    """
    serializer_class = CheckoutRequestSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=CheckoutRequestSerializer,
        responses={200: CheckoutResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        seller_username = serializer.validated_data.get("seller_username")

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


class TelegramWebAppAuthView(APIView):
    """
    POST /api/auth/telegram/  { "initData": "<window.Telegram.WebApp.initData>" }
    Возвращает верифицированные данные юзера.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=TelegramWebAppAuthRequestSerializer,
        responses={200: TelegramWebAppAuthResponseSerializer, 400: dict},
        description="Верификация подписи Telegram WebApp и возврат user-данных"
    )
    def post(self, request):
        ser = TelegramWebAppAuthRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        init_data = ser.validated_data["initData"]

        bot_token = BOT_TOKEN
        if not bot_token:
            return Response({"detail": "BOT_TOKEN не настроен"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        ok, payload, err = verify_telegram_init_data(init_data, bot_token, max_age=24 * 3600)
        if not ok:
            return Response({"ok": False, "detail": err}, status=status.HTTP_400_BAD_REQUEST)

        user_data = payload.get("user") or {}
        # нормализуем поля
        tg_id = int(user_data.get("id"))
        username = user_data.get("username")
        first_name = user_data.get("first_name")
        last_name = user_data.get("last_name")
        language_code = user_data.get("language_code")
        is_premium = bool(user_data.get("is_premium", False))

        # создадим/обновим пользователя в БД (необязательно, но удобно)
        TelegramUser.objects.update_or_create(
            tg_id=tg_id,
            defaults=dict(
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
                is_premium=is_premium,
            ),
        )

        resp = {
            "ok": True,
            "user": {
                "id": tg_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "language_code": language_code,
                "is_premium": is_premium,
            },
        }
        return Response(resp, status=status.HTTP_200_OK)