from django.contrib import admin
from django.utils.safestring import mark_safe
from tinymce.models import HTMLField
from tinymce.widgets import TinyMCE
from unfold.admin import ModelAdmin, TabularInline  # классы из django-unfold

from shop.models import Category, Product, ProductSize, Banner, CartItem, InfoPage, Order, OrderItem, ProductImage, \
    AdminPaymentProfile
from import_export.admin import ImportExportModelAdmin
from unfold.contrib.import_export.forms import ExportForm, ImportForm


# ---------- helpers ----------

def _file_link(field):
    try:
        url = field.url
    except Exception:
        return "—"
    return mark_safe(f'<a href="{url}" target="_blank">Открыть</a>')


def _img_thumb_field(field, h=60):
    try:
        url = field.url
    except Exception:
        return "—"
    return mark_safe(f'<img src="{url}" style="height:{h}px;border-radius:6px;object-fit:cover" />')


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
    list_display_links = list_display
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


class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 0
    fields = ("preview", "image", "is_main", "sort_order")
    readonly_fields = ("preview",)

    def preview(self, obj):
        return _img_thumb(obj.image, h=60)
    preview.short_description = "Превью"


@admin.register(Product)
class ProductAdmin(ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = ExportForm
    list_display = ("id", "name", "category", "price", "old_price", "image_thumb", "has_video")
    list_display_links = list_display
    search_fields = ("name", "description")
    list_filter = ("category",)
    ordering = ("-id",)
    list_per_page = 25

    inlines = (ProductSizeInline, ProductImageInline)

    # удобные группы полей (Unfold делает их аккуратными)
    fieldsets = (
        ("Основное", {
            "fields": ("name", "description", "category"),
        }),
        ("Цены", {
            "fields": ("price", "old_price"),
        }),
        ("Видеобзор", {
            "fields": (
                "video_url",
                "video_file", "video_file_link",
                "video_poster", "video_poster_preview",
            ),
        }),
    )
    readonly_fields = ("image_thumb_large", "video_file_link", "video_poster_preview")

    # автодополнение по категории (ускоряет формы)
    autocomplete_fields = ("category",)

    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'cols': 80, 'rows': 30})},
    }

    def image_thumb(self, obj):
        return _img_thumb(obj, "image", h=32)
    image_thumb.short_description = "Превью"

    def image_thumb_large(self, obj):
        return _img_thumb(obj, "image", h=120)
    def video_file_link(self, obj):
        return _file_link(obj.video_file) if obj and obj.video_file else "—"
    video_file_link.short_description = "Файл (ссылка)"

    def video_poster_preview(self, obj):
        return _img_thumb_field(obj.video_poster, h=80) if obj and obj.video_poster else "—"
    video_poster_preview.short_description = "Постер (превью)"

    def has_video(self, obj):
        return bool((obj.video_url or "").strip() or obj.video_file)
    has_video.boolean = True
    has_video.short_description = "Видео"
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
    list_display = ("id", "slug", "title", "is_active", "sort_order", "updated_at")
    list_display_links = ("slug", "title")
    list_editable = ("is_active", "sort_order")
    list_filter = ("is_active", "slug")
    search_fields = ("title", "external_url", "content")
    ordering = ("sort_order", "title")
    fieldsets = (
        ("Основное", {"fields": ("slug", "title", "external_url", "is_active", "sort_order", "image")}),
        ("Контент", {"fields": ("content",)}),
    )

    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'cols': 80, 'rows': 30})},
    }


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "price")
    can_delete = False


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ("id", "tg_user", "status", "pay_bank", "total_amount", "created_at")
    list_filter = ("status",)
    list_display_links = list_display
    search_fields = ("tg_user__tg_id", "id")
    ordering = ("-id",)
    inlines = (OrderItemInline,)
    readonly_fields = ("created_at", "updated_at", "total_amount", "pay_bank", "pay_card", "pay_holder")


@admin.register(AdminPaymentProfile)
class AdminPaymentProfileAdmin(ModelAdmin):
    list_display = ("id", "title", "bank_name", "card_masked", "card_holder", "is_active", "sort_order")
    list_display_links = list_display
    list_editable = ("is_active", "sort_order")
    search_fields = ("title", "bank_name", "card_number", "card_holder")
    ordering = ("-is_active", "sort_order", "id")

    def card_masked(self, obj):
        n = obj.card_number.replace(" ", "")
        tail = n[-4:] if len(n) >= 4 else n
        return f"•••• {tail}"
    card_masked.short_description = "Карта"
