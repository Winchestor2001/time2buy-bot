from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .models import Category, Product, ProductSize, Banner, CartItem, InfoPage, Order, OrderItem


class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "image", "parent", "subcategories")

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))  # или ссылку на этот же сериализатор
    def get_subcategories(self, obj):
        # верни сериализатор подкатегорий (если делаешь дерево)
        qs = obj.subcategories.all()
        return CategorySerializer(qs, many=True, context=self.context).data

    @extend_schema_field(OpenApiTypes.URI)  # подсказка схеме, что это URL/None
    def get_image(self, obj) -> str | None:
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class CategoryFlatSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "image", "parent_id")

    @extend_schema_field(OpenApiTypes.URI)  # подсказываем, что это URL (может быть null)
    def get_image(self, obj) -> str | None:
        request = self.context.get("request")
        if not obj.image:
            return None
        try:
            url = obj.image.url
        except ValueError:
            # файл отсутствует/битый storage — безопасно вернём None
            return None
        return request.build_absolute_uri(url) if request else url

class ProductSizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSize
        fields = ("id", "label")

class ProductSerializer(serializers.ModelSerializer):
    sizes = ProductSizeSerializer(many=True, read_only=True)
    class Meta:
        model = Product
        fields = ("id", "name", "description", "price", "old_price", "image", "category", "sizes")

class BannerSerializer(serializers.ModelSerializer):
    category_id = serializers.IntegerField(source="category.id", read_only=True)

    class Meta:
        model = Banner
        fields = ("id", "title", "image", "category_id", "url")

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    class Meta:
        model = CartItem
        fields = ("id", "user_id", "product", "quantity")


class CheckoutRequestSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    cart_item_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True,
        help_text="Если передать — оформим заказ только по этим позициям корзины. Иначе возьмём всю корзину пользователя.",
    )
    note = serializers.CharField(required=False, allow_blank=True)

class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    image = serializers.ImageField(source="product.image", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product", "product_name", "image", "quantity", "price")

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ("id", "user_id", "status", "total_amount", "note", "created_at", "items")


class CheckoutResponseSerializer(serializers.Serializer):
    cart = CartItemSerializer(many=True)
    redirect_to = serializers.URLField(allow_null=True, required=False)


# Если используешь InfoPage:
class InfoPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = InfoPage
        fields = ("id", "slug", "title", "external_url", "content")


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