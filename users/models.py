from django.db import models


class TelegramUser(models.Model):
    tg_id = models.BigIntegerField(
        "Telegram ID",
        unique=True,
        db_index=True,
        help_text="Уникальный идентификатор пользователя в Telegram",
    )
    username = models.CharField(
        "Username",
        max_length=150,
        null=True,
        blank=True,
        help_text="@username, если установлен",
    )
    first_name = models.CharField(
        "Имя",
        max_length=150,
        null=True,
        blank=True,
    )
    last_name = models.CharField(
        "Фамилия",
        max_length=150,
        null=True,
        blank=True,
    )
    language_code = models.CharField(
        "Язык интерфейса",
        max_length=12,
        null=True,
        blank=True,
        help_text="Код языка, который передаёт Telegram (например, ru, en)",
    )
    is_premium = models.BooleanField(
        "Премиум",
        default=False,
        help_text="Есть ли у пользователя Telegram Premium",
    )
    is_blocked = models.BooleanField(
        "Заблокирован",
        default=False,
        help_text="Заблокировал ли пользователь бота",
    )
    created_at = models.DateTimeField(
        "Дата регистрации",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "Дата обновления",
        auto_now=True,
    )

    class Meta:
        verbose_name = "TG пользователь"
        verbose_name_plural = "TG пользователи"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.username or self.tg_id}"


class SubscriptionChannel(models.Model):
    title = models.CharField("Название", max_length=150)
    chat_id = models.BigIntegerField(
        "Chat ID", db_index=True,
        help_text="ID канала/группы (например, -1001234567890)."
    )
    username = models.CharField(
        "Username без @", max_length=150,
        null=True, blank=True, help_text="Напр.: my_channel (без @)"
    )
    invite_link = models.URLField(
        "Пригласительная ссылка", null=True, blank=True,
        help_text="Если приватный канал/чат."
    )
    is_group = models.BooleanField("Это группа/чат", default=False)
    is_required = models.BooleanField("Обязательная подписка", default=True)
    is_active = models.BooleanField("Активен", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Канал/группа для подписки"
        verbose_name_plural = "Каналы/группы для подписки"
        ordering = ("sort_order", "title")

    def __str__(self):
        return f"{self.title} ({self.chat_id})"

    @property
    def public_link(self) -> str | None:
        if self.username:
            return f"https://t.me/{self.username}"
        return self.invite_link