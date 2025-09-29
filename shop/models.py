from django.db import models
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
    description = models.TextField("Описание", blank=True, null=True)
    price = models.DecimalField("Цена", max_digits=12, decimal_places=2)
    old_price = models.DecimalField("Старая цена", max_digits=12, decimal_places=2, blank=True, null=True)
    image = models.ImageField("Изображение", upload_to="products/", blank=True, null=True)
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
    title = models.CharField("Заголовок", max_length=160)
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
        return self.title


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

    user_id = models.CharField("TG user_id", max_length=64, db_index=True)
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.NEW)

    total_amount = models.DecimalField("Сумма, ₽", max_digits=12, decimal_places=2, default=0)
    note = models.TextField("Комментарий клиента", blank=True, null=True)

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        ordering = ("-id",)
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

    def __str__(self):
        return f"Заказ #{self.id} (user {self.user_id})"


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
