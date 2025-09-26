from django.contrib import admin
from django.utils.safestring import mark_safe
from tinymce.models import HTMLField
from tinymce.widgets import TinyMCE
from unfold.admin import ModelAdmin, TabularInline  # классы из django-unfold

from shop.models import Category, Product, ProductSize, Banner, CartItem, InfoPage


# ---------- helpers ----------

def _img_thumb(obj, field="image", h=40):
    """Безопасный <img> для превью в списке/формах."""
    f = getattr(obj, field, None)
    if not f:
        return "—"
    try:
        url = f.url
    except Exception:
        return "—"
    return mark_safe(f'<img src="{url}" style="height:{h}px;border-radius:6px;object-fit:cover" />')


# ---------- inlines ----------

class ProductSizeInline(TabularInline):
    model = ProductSize
    extra = 0
    fields = ("label",)
    classes = ("collapse",)       # компактнее с Unfold
    show_change_link = True


# ---------- admins ----------

@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("id", "name", "parent", "image_thumb")
    list_display_links = ("name",)
    search_fields = ("name",)
    list_filter = ("parent",)
    ordering = ("name",)
    list_per_page = 25

    # Unfold красиво рендерит readonly поля
    readonly_fields = ("image_thumb_large",)
    fields = ("name", "parent", "image", "image_thumb_large")

    def image_thumb(self, obj):
        return _img_thumb(obj, "image", h=32)
    image_thumb.short_description = "Превью"

    def image_thumb_large(self, obj):
        return _img_thumb(obj, "image", h=120)
    image_thumb_large.short_description = "Превью"


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ("id", "name", "category", "price", "old_price", "image_thumb")
    list_display_links = ("name",)
    search_fields = ("name", "description")
    list_filter = ("category",)
    ordering = ("-id",)
    list_per_page = 25

    inlines = (ProductSizeInline,)

    # удобные группы полей (Unfold делает их аккуратными)
    fieldsets = (
        ("Основное", {
            "fields": ("name", "description", "category"),
        }),
        ("Цены", {
            "fields": ("price", "old_price"),
        }),
        ("Медиа", {
            "fields": ("image", "image_thumb_large"),
        }),
    )
    readonly_fields = ("image_thumb_large",)

    # автодополнение по категории (ускоряет формы)
    autocomplete_fields = ("category",)

    def image_thumb(self, obj):
        return _img_thumb(obj, "image", h=32)
    image_thumb.short_description = "Превью"

    def image_thumb_large(self, obj):
        return _img_thumb(obj, "image", h=120)
    image_thumb_large.short_description = "Превью"


@admin.register(ProductSize)
class ProductSizeAdmin(ModelAdmin):
    list_display = ("id", "product", "label",)
    list_display_links = ("product", "label")
    list_filter = ("product",)
    search_fields = ("product__name", "label")
    autocomplete_fields = ("product",)
    ordering = ("product__name", "label")


@admin.register(Banner)
class BannerAdmin(ModelAdmin):
    list_display = ("id", "title", "category", "image_thumb")
    list_display_links = ("title", "category", "image_thumb")
    search_fields = ("title",)
    autocomplete_fields = ("category",)
    ordering = ("-id",)
    readonly_fields = ("image_thumb_large",)
    fields = ("title", "category", "image", "image_thumb_large")

    def image_thumb(self, obj):
        return _img_thumb(obj, "image", h=32)
    image_thumb.short_description = "Превью"

    def image_thumb_large(self, obj):
        return _img_thumb(obj, "image", h=140)
    image_thumb_large.short_description = "Превью"


@admin.register(CartItem)
class CartItemAdmin(ModelAdmin):
    list_display = ("id", "user_id", "product", "quantity")
    list_display_links = ("user_id", "product")
    list_filter = ("product__category",)
    search_fields = ("user_id", "product__name")
    autocomplete_fields = ("product",)
    ordering = ("-id",)



@admin.register(InfoPage)
class InfoPageAdmin(ModelAdmin):
    list_display = ("id", "slug", "title", "content", "is_active", "sort_order", "updated_at")
    list_display_links = ("slug", "title")
    list_editable = ("is_active", "sort_order")
    list_filter = ("is_active", "slug")
    search_fields = ("title", "external_url", "content")
    ordering = ("sort_order", "title")
    fieldsets = (
        ("Основное", {"fields": ("slug", "title", "external_url", "is_active", "sort_order")}),
        ("Контент", {"fields": ("content",)}),
    )

    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'cols': 80, 'rows': 30})},
    }