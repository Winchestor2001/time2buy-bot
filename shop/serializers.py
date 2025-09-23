from rest_framework import serializers
from .models import Category, Product, ProductSize, Banner, CartItem, InfoPage

class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()
    class Meta:
        model = Category
        fields = ("id", "name", "image", "parent", "subcategories")

    def get_subcategories(self, obj):
        return CategorySerializer(obj.subcategories.all(), many=True, context=self.context).data

class CategoryFlatSerializer(serializers.ModelSerializer):
    parent_id = serializers.IntegerField(source="parent.id", read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "image", "parent_id")

    def get_image(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if (request and obj.image) else None

class ProductSizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSize
        fields = ("id", "label", "price_delta")

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

# Если используешь InfoPage:
class InfoPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = InfoPage
        fields = ("id", "slug", "title", "external_url", "content")