from django.urls import path
from .views import (
    CategoryTreeView, CategoryFlatView, ProductListView,
    BannerListView, CartView, CheckoutView,
    InfoPageListView, InfoPageDetailView,
)

urlpatterns = [
    path("categories/", CategoryTreeView.as_view(), name="categories-tree"),
    path("categories/flat/", CategoryFlatView.as_view(), name="categories-flat"),
    path("products/", ProductListView.as_view(), name="products-list"),
    path("banners/", BannerListView.as_view(), name="banners-list"),
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/checkout/", CheckoutView.as_view(), name="cart-checkout"),

    # если используешь инфо-разделы:
    path("info/", InfoPageListView.as_view(), name="info-list"),
    path("info/<slug:slug>/", InfoPageDetailView.as_view(), name="info-detail"),
]