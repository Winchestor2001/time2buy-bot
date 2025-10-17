from decimal import Decimal

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, filters, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import Prefetch, QuerySet, Count, Q
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from bot.config import BOT_TOKEN
from core.utils import notify_admins, _size_sort_key
from users.models import TelegramUser
from .models import Category, Product, Banner, CartItem, InfoPage, OrderItem, Order, ProductSize, AdminPaymentProfile
from .pagination import DefaultPagination
from .serializers import (
    CategorySerializer, CategoryFlatSerializer,
    ProductSerializer, BannerSerializer, CartItemSerializer,
    InfoPageSerializer, CheckoutResponseSerializer, CheckoutRequestSerializer, CartChangeQuantitySerializer,
    CartDeleteItemSerializer, CartClearSerializer, TelegramWebAppAuthRequestSerializer,
    TelegramWebAppAuthResponseSerializer, OrderSerializer, SizeLabelSerializer, SizeWithCountSerializer,
    MyActiveOrderRequestSerializer,
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
    GET /api/products/?category_id=...&sort=new|cheap|expensive&size=...&sizes=...
    - category_id: может быть id родителя — вернём товары из него и всех подкатегорий
    - sort: new|cheap|expensive
    - size / sizes: фильтр по размерам (S,M,L,XL,XXL,3XL, числа и т.д.)
    """
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "description"]
    pagination_class = DefaultPagination

    def _descendant_ids(self, root_id: int) -> list[int]:
        """Собираем id всех потомков (включая сам root) простым BFS."""
        ids = []
        layer = [root_id]
        while layer:
            ids.extend(layer)
            layer = list(
                Category.objects
                .filter(parent_id__in=layer)
                .values_list("id", flat=True)
            )
        return ids

    def _parse_sizes(self) -> list[str]:
        """
        Собираем список размеров из query params:
        - size=S (может повторяться)
        - sizes=S,M,XL
        Возвращаем нормализованные лейблы без лишних пробелов (регистр не важен).
        """
        qp = self.request.query_params
        values = []

        # повторяющиеся size=...
        values.extend(qp.getlist("size") or [])

        # одно поле sizes=...
        sizes_csv = qp.get("sizes")
        if sizes_csv:
            values.extend(sizes_csv.split(","))

        # нормализация
        cleaned = []
        for v in values:
            s = (v or "").strip()
            if s:
                cleaned.append(s)
        return cleaned

    def get_queryset(self) -> QuerySet:
        qs = Product.objects.all().prefetch_related("sizes")

        # --- фильтр по категории (включая потомков) ---
        category_id = self.request.query_params.get("category_id")
        if category_id:
            try:
                root_id = int(category_id)
            except (TypeError, ValueError):
                root_id = None

            if root_id:
                cat_ids = self._descendant_ids(root_id)
                qs = qs.filter(category_id__in=cat_ids)

        # --- фильтр по размерам (логика OR) ---
        size_labels = self._parse_sizes()
        if size_labels:
            # построим Q c icontains для каждого лейбла
            q = Q()
            for lbl in size_labels:
                q |= Q(sizes__label__iexact=lbl) | Q(sizes__label__icontains=lbl)
                # iexact закроет точные совпадения ("XL"), icontains поможет для "40+" по "40"
            qs = qs.filter(q).distinct()

        # --- сортировка ---
        sort = self.request.query_params.get("sort")
        if sort == "cheap":
            qs = qs.order_by("price", "-id")
        elif sort == "expensive":
            qs = qs.order_by("-price", "-id")
        else:  # new по умолчанию
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
        POST /api/cart/checkout/
        body: {
          user_id: "...",
          full_name: "...",
          phone: "...",
          delivery_type: "cdek|post_ru|meet",
          delivery_address?: "..."   # обязателен для cdek, post_ru
        }
        """
    serializer_class = CheckoutRequestSerializer
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = ser.validated_data["user_id"]

        tg_user, _ = TelegramUser.objects.get_or_create(tg_id=int(user_id))

        # 1) не допускаем второй активный заказ
        existing = (
            Order.objects
            .filter(tg_user=tg_user, status__in=[Order.Status.NEW, Order.Status.IN_PROGRESS])
            .first()
        )
        if existing:
            # Можно вернуть существующий активный заказ
            return Response(OrderSerializer(existing, context={"request": request}).data, status=200)

        # 2) корзина
        items_qs = CartItem.objects.filter(user_id=user_id).select_related("product")
        items = list(items_qs)
        if not items:
            return Response({"detail": "Корзина пуста."}, status=400)

        # 3) выбираем активный платёжный профиль
        pay = (AdminPaymentProfile.objects
               .filter(is_active=True)
               .order_by("sort_order", "id")
               .first())
        if not pay:
            return Response({"detail": "Платёжные реквизиты не настроены."}, status=500)

        # 4) создаём заказ + снэпшот реквизитов
        order = Order.objects.create(
            tg_user=tg_user,
            pay_profile=pay,
            pay_bank=pay.bank_name,
            pay_card=pay.card_number,
            pay_holder=pay.card_holder,
        )

        total = Decimal("0")
        bulk = []
        for ci in items:
            price = ci.product.price or Decimal("0")
            total += price * ci.quantity
            bulk.append(OrderItem(order=order, product=ci.product, quantity=ci.quantity, price=price))
        OrderItem.objects.bulk_create(bulk)
        order.total_amount = total
        order.save(update_fields=["total_amount"])

        # 5) чистим корзину
        items_qs.delete()

        # 6) уведомляем админов (как у тебя было)
        # notify_admins(...)

        return Response(OrderSerializer(order, context={"request": request}).data, status=200)

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


class SizeListView(APIView):
    """
    GET /api/sizes/                -> [{label: "S"}, ...]
    GET /api/sizes/?with_counts=1  -> [{label: "S", count: 12}, ...]
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Список всех уникальных размеров",
        responses={200: SizeLabelSerializer(many=True)},
    )
    def get(self, request):
        with_counts = request.query_params.get("with_counts")

        if with_counts:
            rows = (
                ProductSize.objects
                .exclude(label__isnull=True)
                .exclude(label__exact="")
                .values("label")
                .annotate(count=Count("id"))
            )
            # сортируем по нашему ключу
            data = sorted(
                [{"label": r["label"], "count": r["count"]} for r in rows],
                key=lambda r: _size_sort_key(r["label"])
            )
            ser = SizeWithCountSerializer(data=data, many=True)
            ser.is_valid(raise_exception=True)
            return Response(ser.data)

        # без счётчиков — просто уникальные лейблы
        labels = (
            ProductSize.objects
            .exclude(label__isnull=True)
            .exclude(label__exact="")
            .values_list("label", flat=True)
            .distinct()
        )
        labels = sorted(labels, key=_size_sort_key)
        ser = SizeLabelSerializer(data=[{"label": x} for x in labels], many=True)
        ser.is_valid(raise_exception=True)
        return Response(ser.data)


class MyActiveOrderView(APIView):
    """
        POST /api/orders/active/
        body: {
          user_id: "...",
        }
        """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        ser = MyActiveOrderRequestSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        user_id = ser.validated_data["user_id"]

        try:
            tg_user = TelegramUser.objects.get(tg_id=int(user_id))
        except TelegramUser.DoesNotExist:
            return Response({"detail": "Пользователь не найден."}, status=404)

        order = (
            Order.objects
            .filter(tg_user=tg_user, status__in=[Order.Status.NEW, Order.Status.IN_PROGRESS])
            .prefetch_related("items__product")
            .first()
        )
        if not order:
            return Response({"ok": False, "order": None}, status=200)

        return Response({"ok": True, "order": OrderSerializer(order, context={"request": request}).data}, status=200)
