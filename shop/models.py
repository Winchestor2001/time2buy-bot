from django.db import models
from django.utils.html import format_html
from tinymce.models import HTMLField

from users.models import TelegramUser


class Category(models.Model):
    name = models.CharField("Название", max_length=120)
    image = models.ImageField("Изображение", upload_to="categories/", blank=True, null=True)
    parent = models.ForeignKey(
        "self",
        verbose_name="Родительская категория",
        null=True, blank=True,
        related_name="subcategories",
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField("Название", max_length=160)
    description = HTMLField("Описание", blank=True, null=True)
    price = models.DecimalField("Цена", max_digits=12, decimal_places=2)
    old_price = models.DecimalField("Старая цена", max_digits=12, decimal_places=2, blank=True, null=True)
    # image = models.ImageField("Главное изображение", upload_to="products/", blank=True, null=True)
    category = models.ForeignKey(
        Category,
        verbose_name="Категория",
        null=True, blank=True,
        related_name="products",
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "Продукт"
        verbose_name_plural = "Продукты"

    def __str__(self):
        return self.name

    # def main_image_url(self):
    #     """
    #     URL главного изображения: сначала gallery (is_main / sort_order), иначе legacy image.
    #     """
    #     pic = self.images.order_by("-is_main", "sort_order", "id").first()
    #     try:
    #         return pic.image.url if pic else (self.image.url if self.image else None)
    #     except Exception:
    #         return None


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        related_name="images",
        on_delete=models.CASCADE,
        verbose_name="Товар",
    )
    image = models.ImageField("Изображение", upload_to="products/")
    is_main = models.BooleanField("Главное", default=False)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Фото товара"
        verbose_name_plural = "Фото товара"
        ordering = ("-is_main", "sort_order", "id")

    def __str__(self):
        return f"{self.product.name} [{self.image.name}]"


class ProductSize(models.Model):
    product = models.ForeignKey(
        Product,
        verbose_name="Продукт",
        related_name="sizes",
        on_delete=models.CASCADE,
    )
    label = models.CharField("Размер", max_length=40)  # 39, 40, 41...

    class Meta:
        verbose_name = "Размер"
        verbose_name_plural = "Размеры"
        unique_together = ("product", "label")

    def __str__(self):
        return f"{self.product.name} — {self.label}"


class Banner(models.Model):
    title = models.CharField("Заголовок", max_length=160, blank=True, null=True)
    image = models.ImageField("Изображение", upload_to="banners/")
    category = models.ForeignKey(
        "shop.Category",
        verbose_name="Категория",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="banners",
        help_text="Категория, на которую ведёт баннер",
    )
    url = models.URLField("Внешняя ссылка", blank=True, null=True)

    class Meta:
        verbose_name = "Баннер"
        verbose_name_plural = "Баннеры"

    def __str__(self):
        return self.title or "-"


class CartItem(models.Model):
    tg_user = models.ForeignKey(
        TelegramUser,
        verbose_name="Telegram пользователь",
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    user_id = models.CharField("Telegram ID", max_length=64)  # Telegram user id (str)
    product = models.ForeignKey(
        Product,
        verbose_name="Продукт",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField("Количество", default=1)

    class Meta:
        verbose_name = "Элемент корзины"
        verbose_name_plural = "Корзина"
        unique_together = ("user_id", "product")

    def __str__(self):
        return f"{self.user_id} — {self.product} x{self.quantity}"


class InfoPage(models.Model):
    class Slug(models.TextChoices):
        ABOUT = "about", "О нас"
        REVIEWS = "reviews", "Отзывы клиентов"
        WARRANTY = "warranty", "Гарантия"
        DELIVERY = "delivery", "Доставка"

    slug = models.CharField(
        "Ключ раздела",
        max_length=50,
        choices=Slug.choices,
        unique=True,
        db_index=True,
        help_text="Системный ключ раздела",
    )
    title = models.CharField("Заголовок", max_length=120)
    external_url = models.URLField("Внешняя ссылка", help_text="Внешняя ссылка на страницу", blank=True, null=True)
    image = models.ImageField("Изображение", upload_to="info_pages/", blank=True, null=True)
    content = HTMLField("Контент", blank=True, null=True)

    is_active = models.BooleanField("Активен", default=True)
    sort_order = models.PositiveIntegerField("Порядок сортировки", default=0)

    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    class Meta:
        verbose_name = "Инфо-страница"
        verbose_name_plural = "Инфо-страницы"
        ordering = ("sort_order", "title")

    def __str__(self):
        return f"{self.get_slug_display()} — {self.title}"


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новый"
        IN_PROGRESS = "in_progress", "В работе"
        DONE = "done", "Выполнен"
        CANCELED = "canceled", "Отменён"

    tg_user = models.ForeignKey(
        TelegramUser,
        verbose_name="TG пользователь",
        on_delete=models.PROTECT,   # заказ не должен терять привязку к покупателю
        related_name="orders",
        db_index=True,
    )
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.NEW)
    total_amount = models.DecimalField("Сумма, ₽", max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        ordering = ("-id",)
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

    def __str__(self):
        return f"Заказ #{self.id} (tg_id={self.tg_user.tg_id})"

    # Удобная ссылка «написать в ЛС»:
    def dm_link(self):
        """
        Возвращает HTML-ссылку для перехода в ЛС:
        - если есть username -> https://t.me/<username>
        - иначе deep link по id -> tg://user?id=<tg_id>
        """
        if self.tg_user and self.tg_user.username:
            url = f"https://t.me/{self.tg_user.username.lstrip('@')}"
            text = f"@{self.tg_user.username.lstrip('@')}"
        else:
            url = f"tg://user?id={self.tg_user.tg_id}"
            text = f"id:{self.tg_user.tg_id}"
        return format_html('<a href="{}" target="_blank">Написать {}</a>', url, text)
    dm_link.short_description = "ЛС покупателя"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey("shop.Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField("Цена на момент заказа", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def __str__(self):
        return f"{self.product} x{self.quantity}"
