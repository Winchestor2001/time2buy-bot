from django import forms

BUTTONS_HELP = (
    "Инлайн-кнопки в формате: каждая кнопка с новой строки, «Текст | URL». Пример:\n"
    "Каталог | https://example.com\n"
    "Написать | https://t.me/username"
)

class BroadcastForm(forms.Form):
    MEDIA_CHOICES = [
        ("text", "Только текст"),
        ("photo", "Фото"),
        ("video", "Видео"),
        ("animation", "GIF/Анимация"),
    ]

    media_type = forms.ChoiceField(label="Тип сообщения", choices=MEDIA_CHOICES, initial="text",
                                   widget=forms.Select(attrs={"class": "w-full"}))
    text = forms.CharField(label="Текст", required=False,
                           widget=forms.Textarea(attrs={"rows": 6, "class": "w-full"}))
    file = forms.FileField(label="Медиа-файл", required=False,
                           help_text="Фото/видео/гиф в зависимости от типа",
                           widget=forms.ClearableFileInput(attrs={"class": "w-full"}))
    buttons = forms.CharField(
        label="Кнопки", required=False,
        widget=forms.Textarea(attrs={"rows": 4, "class": "w-full"}),
        help_text=BUTTONS_HELP,
    )

    def clean(self):
        cleaned = super().clean()
        mtype = cleaned.get("media_type")
        text = cleaned.get("text")
        file = cleaned.get("file")
        if mtype == "text" and not text:
            self.add_error("text", "Нужен текст для текстового сообщения.")
        if mtype != "text" and not file:
            self.add_error("file", "Для этого типа нужен загруженный файл.")
        return cleaned