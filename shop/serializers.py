from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.utils import abs_url
from .models import Category, Product, ProductSize, Banner, CartItem, InfoPage, Order, OrderItem, ProductImage


class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "image", "parent", "subcategories")

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_subcategories(self, obj):
        qs = obj.subcategories.all()
        return CategorySerializer(qs, many=True, context=self.context).data

    @extend_schema_field(OpenApiTypes.URI)
    def get_image(self, obj) -> str | None:
        request = self.context.get("request")
        return abs_url(request, obj.image)


class CategoryFlatSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "image", "parent_id")

    @extend_schema_field(OpenApiTypes.URI)
    def get_image(self, obj) -> str | None:
        request = self.context.get("request")
        return abs_url(request, obj.image)

class ProductSizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSize
        fields = ("id", "label")


class ProductImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ("id", "url", "is_main", "sort_order")

    def get_url(self, obj):
        request = self.context.get("request")
        try:
            url = obj.image.url
        except Exception:
            return None
        return request.build_absolute_uri(url) if request else url


class ProductSerializer(serializers.ModelSerializer):
    sizes = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    video = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ("id", "name", "description", "price", "old_price", "images", "video", "category", "sizes")

    def get_sizes(self, obj):
        # сортировка размеров: S, M, L, XL, XXL, 3XL → затем числа → затем остальное
        order = {"S": 1, "M": 2, "L": 3, "XL": 4, "XXL": 5, "3XL": 6}

        def key(s):
            lbl = (s.label or "").upper().strip()
            if lbl in order:
                return (0, order[lbl])
            if lbl.isdigit():
                return (1, int(lbl))
            return (2, lbl)

        items = sorted(obj.sizes.all(), key=key)
        return ProductSizeSerializer(items, many=True).data

    def get_images(self, obj):
        """
        Возвращаем список изображений с абсолютными URL.
        """
        request = self.context.get("request")
        qs = obj.images.all().order_by("sort_order", "id")
        data = []
        for im in qs:
            data.append({
                "id": im.id,
                "url": abs_url(request, im.image),
                "is_main": im.is_main,
                "sort_order": im.sort_order,
            })
        return data

    def get_video(self, obj):
        """
        Возвращает единый блок:
        {
          "url": <внешняя ссылка или None>,
          "file": <абсолютный URL файла или None>,
          "poster": <абсолютный URL постера или None>,
          "has_video": true/false
        }
        """
        request = self.context.get("request")
        url = (obj.video_url or "").strip() or None
        file_url = abs_url(request, obj.video_file) if getattr(obj, "video_file", None) else None
        poster_url = abs_url(request, obj.video_poster) if getattr(obj, "video_poster", None) else None
        has_video = bool(url or file_url)
        return {
            "url": url,
            "file": file_url,
            "poster": poster_url,
            "has_video": has_video,
        }


class BannerSerializer(serializers.ModelSerializer):
    category_id = serializers.IntegerField(source="category.id", read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = ("id", "title", "image", "category_id", "url")

    def get_image(self, obj):
        request = self.context.get("request")
        try:
            url = obj.image.url
        except Exception:
            return None
        return request.build_absolute_uri(url) if request else url


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = CartItem
        fields = ("id", "user_id", "product", "quantity")


class CheckoutRequestSerializer(serializers.Serializer):
    user_id = serializers.CharField(help_text="Telegram user_id из WebApp.initData")
    full_name = serializers.CharField(max_length=160)
    phone = serializers.CharField(max_length=32)
    delivery_type = serializers.ChoiceField(choices=Order.Delivery.choices)
    delivery_address = serializers.CharField(allow_blank=True, required=False)

    def validate(self, attrs):
        d_type = attrs.get("delivery_type")
        addr = (attrs.get("delivery_address") or "").strip()

        # адрес обязателен для СДЭК и Почты РФ
        if d_type in (Order.Delivery.CDEK, Order.Delivery.POST_RU) and not addr:
            raise serializers.ValidationError({"delivery_address": "Адрес обязателен для выбранного типа доставки."})

        # лёгкая нормализация телефона (опционально)
        phone = attrs.get("phone", "").strip()
        if not phone:
            raise serializers.ValidationError({"phone": "Укажите номер телефона."})
        attrs["phone"] = phone

        return attrs

class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ("id", "product", "product_name", "image", "quantity", "price")

    @extend_schema_field(OpenApiTypes.URI)
    def get_image(self, obj) -> str | None:
        """
        Если у продукта мульти-изображения — берём главное/первое.
        Иначе — пробуем старое поле product.image (если ещё есть).
        """
        request = self.context.get("request")

        # 1) сначала main
        main = obj.product.images.filter(is_main=True).order_by("sort_order", "id").first()
        if main:
            return abs_url(request, main.image)

        # 2) потом просто первое
        any_img = obj.product.images.order_by("sort_order", "id").first()
        if any_img:
            return abs_url(request, any_img.image)

        # 3) fallback на product.image (если ещё используешь)
        if hasattr(obj.product, "image"):
            return abs_url(request, obj.product.image)

        return None


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    tg_user_id = serializers.IntegerField(source="tg_user.tg_id", read_only=True)
    tg_username = serializers.CharField(source="tg_user.username", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id", "tg_user_id", "tg_username", "status",
            "total_amount", "created_at", "items", "full_name",
            "phone", "delivery_type", "delivery_address"
        )


class CheckoutResponseSerializer(serializers.Serializer):
    cart = CartItemSerializer(many=True)
    redirect_to = serializers.URLField(allow_null=True, required=False)


# Если используешь InfoPage:
class InfoPageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = InfoPage
        fields = ("id", "slug", "title", "external_url", "content", "image")

    @extend_schema_field(OpenApiTypes.URI)
    def get_image(self, obj) -> str | None:
        request = self.context.get("request")
        # Если у InfoPage будет поле image — раскомментируй:
        return abs_url(request, obj.image)
        # return None  # или удаляй метод/поле если картинки нет


class CartSetQuantitySerializer(serializers.Serializer):
    user_id = serializers.CharField()
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)  # установить точное новое кол-во (>=1)

class CartChangeQuantitySerializer(serializers.Serializer):
    user_id = serializers.CharField()
    product_id = serializers.IntegerField()
    delta = serializers.IntegerField()  # +1 / -1 / +3 / -5 и т.п.

class CartDeleteItemSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    product_id = serializers.IntegerField()

class CartClearSerializer(serializers.Serializer):
    user_id = serializers.CharField()


class TelegramWebAppAuthRequestSerializer(serializers.Serializer):
    initData = serializers.CharField()


class TelegramWebAppAuthUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField(allow_null=True, required=False)
    first_name = serializers.CharField(allow_null=True, required=False)
    last_name = serializers.CharField(allow_null=True, required=False)
    language_code = serializers.CharField(allow_null=True, required=False)
    is_premium = serializers.BooleanField(required=False)


class TelegramWebAppAuthResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    user = TelegramWebAppAuthUserSerializer()


class SizeLabelSerializer(serializers.Serializer):
    label = serializers.CharField()

class SizeWithCountSerializer(serializers.Serializer):
    label = serializers.CharField()
    count = serializers.IntegerField()