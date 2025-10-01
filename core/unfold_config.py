from core.utils import get_reverse_link

UNFOLD = {
    "SITE_TITLE": "time2buy Admin",
    "SITE_HEADER": "time2buy — админка",
    "SITE_URL": "/admin/",
    "SITE_SYMBOL": "shopping_bag",
    "COLORS": {
        "primary": {
            "50": "#e8edfb",
            "100": "#c7d3f7",
            "200": "#a4b9f3",
            "300": "#7a96e8",
            "400": "#4f72de",
            "500": "#1d4acc",
            "600": "#173ca4",
            "700": "#122d7d",
            "800": "#0c1f55",
            "900": "#07112f",
            "950": "#030617",
        }
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,

        "navigation": [
            {
                "title": "Пользователи",
                "separator": True,  # Top border
                "collapsible": True,  # Collapsible group of links
                "items": [
                    {
                        "title": "TG Пользователи",
                        "icon": "group",
                        "link": get_reverse_link(app_name="users", model_name="telegramuser"),
                        "permission": lambda request: request.user.is_staff or request.user.is_superuser,
                    },
                    {
                        "title": "Каналы/группы для подписки",
                        "icon": "subscriptions",
                        "link": get_reverse_link(app_name="users", model_name="subscriptionchannel"),
                        "permission": lambda request: request.user.is_staff or request.user.is_superuser,
                    },
                    {
                        "title": "Супер Админы",
                        "icon": "shield_person",
                        "link": get_reverse_link(app_name="auth", model_name="user"),
                        "permission": lambda request: request.user.is_staff or request.user.is_superuser,
                    },
                    {
                        "title": "TG Админы",
                        "icon": "manage_accounts",
                        "link": get_reverse_link(app_name="users", model_name="telegramadmin"),
                        "permission": lambda request: request.user.is_staff or request.user.is_superuser,
                    },
                ],
            },
            {
                "title": "Каталог",
                "separator": True,  # Top border
                "collapsible": True,  # Collapsible group of links
                "items": [
                    {
                        "title": "Категории",
                        "icon": "category",
                        "link": get_reverse_link(app_name="shop", model_name="category"),
                        "permission": lambda request: request.user.is_staff or request.user.is_superuser,
                    },
                    {
                        "title": "Товары",
                        "icon": "shopping_bag",
                        "link": get_reverse_link(app_name="shop", model_name="product"),
                        "permission": lambda request: request.user.is_staff or request.user.is_superuser,
                    },
                    {
                        "title": "Заказы",
                        "icon": "list_alt",
                        "link": get_reverse_link(app_name="shop", model_name="order"),
                        "permission": lambda request: request.user.is_staff or request.user.is_superuser,
                    },
                    {
                        "title": "Баннеры",
                        "icon": "image",
                        "link": get_reverse_link(app_name="shop", model_name="banner"),
                        "permission": lambda request: request.user.is_staff or request.user.is_superuser,
                    },
                    {
                        "title": "Инфо-страницы",
                        "icon": "info",
                        "link": get_reverse_link(app_name="shop", model_name="infopage"),
                        "permission": lambda request: request.user.is_staff or request.user.is_superuser,
                    },
                ],
            },
        ]
    }
}