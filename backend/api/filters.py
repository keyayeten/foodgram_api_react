from django_filters.rest_framework import filters, FilterSet
from django.db.models import Exists, OuterRef
from rest_framework.filters import SearchFilter
from recipes.models import (Ingredient, Recipe, Tag,
                            RecipeShoppingList, FavoriteRecipe)


class IngredientFilter(SearchFilter):
    search_param = 'name'

    class Meta:
        model = Ingredient
        fields = ('name',)


class RecipeFilter(FilterSet):
    tags = filters.ModelMultipleChoiceFilter(
        field_name='tags__slug',
        to_field_name='slug',
        queryset=Tag.objects.all(),
    )

    author = filters.CharFilter(field_name='author_id')

    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart',
        label='Is in shopping cart'
    )

    is_favorited = filters.BooleanFilter(
        method='filter_is_favorited',
        label='Is favorited'
    )

    class Meta:
        model = Recipe
        fields = ['tags', 'author',
                  'is_in_shopping_cart', 'is_favorited']

    def filter_is_in_shopping_cart(self, queryset, name, value):
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()

        subquery = RecipeShoppingList.objects.filter(
            recipe=OuterRef('pk'),
            user=user
        )
        annotated_queryset = queryset.annotate(
            in_shopping_cart=Exists(subquery)
        )

        if value:
            return annotated_queryset.filter(in_shopping_cart=True)
        else:
            return annotated_queryset.exclude(in_shopping_cart=True)

    def filter_is_favorited(self, queryset, name, value):
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()

        subquery = FavoriteRecipe.objects.filter(
            recipe=OuterRef('pk'),
            user=user
        )
        annotated_queryset = queryset.annotate(
            is_favorited=Exists(subquery)
        )

        if value:
            return annotated_queryset.filter(is_favorited=True)
        else:
            return annotated_queryset.exclude(is_favorited=True)
