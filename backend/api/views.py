from django.contrib.auth.hashers import make_password, check_password
from django.http.response import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet
from rest_framework import permissions, status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import (CustomUserSerializer,
                          FavoriteRecipeSerializer,
                          IngredientSerializer,
                          RecipeCreateUpdateSerializer,
                          RecipeSerializer,
                          RecipeShoppingListSerializer,
                          SubscriptionsSerializer,
                          TagSerializer)
from .filters import IngredientFilter, RecipeFilter
from recipes.models import (Ingredient, Recipe, Tag,
                            RecipeIngredient, RecipeShoppingList,
                            FavoriteRecipe)
from users.models import Follow, User
from rest_framework.pagination import PageNumberPagination
from .permissions import AuthorOnly
from django.db.models import F, Sum


class CustomPagination(PageNumberPagination):
    page_size_query_param = 'limit'
    max_page_size = 100


class CustomUserViewSet(UserViewSet):
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    pagination_class = CustomPagination

    def retrieve(self, request, *args, **kwargs):
        if request.user.is_anonymous and request.path.endswith('/me/'):
            return Response({'Ошибка': 'Неавторизован'},
                            status=status.HTTP_401_UNAUTHORIZED)
        return super().retrieve(request, *args, **kwargs)

    @action(methods=['POST'],
            detail=False,
            permission_classes=[permissions.IsAuthenticated])
    def set_password(self, request):
        user = self.request.user
        if user.is_authenticated:
            new_password = request.data.get('new_password')
            current_password = request.data.get('current_password')
            if not current_password:
                return Response(
                    {'Ошибка': 'Поле "текущий пароль" обязательно'},
                    status=status.HTTP_400_BAD_REQUEST)
            if not new_password:
                return Response(
                    {'Ошибка': 'Поле "новый пароль" обязательно'},
                    status=status.HTTP_400_BAD_REQUEST)
            if not check_password(current_password, user.password):
                return Response(
                    {'Ошибка': 'Текущий пароль некорректен'},
                    status=status.HTTP_400_BAD_REQUEST)
            user.password = make_password(new_password)
            user.save()
            return Response({'Статус': 'пароль установлен'},
                            status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({'Ошибка': 'Неавторизован'},
                            status=status.HTTP_401_UNAUTHORIZED)

    @action(methods=['POST', 'DELETE'], detail=True,
            permission_classes=[permissions.IsAuthenticated])
    def subscribe(self, request, id):
        user = request.user
        author = get_object_or_404(User, id=id)
        subscription = Follow.objects.filter(subscriber=user, author=author)
        if request.method == 'POST':
            if subscription.exists():
                return Response({'Ошибка': f'Вы уже подписаны '
                                 f'на {author}'},
                                status=status.HTTP_400_BAD_REQUEST)
            if user == author:
                return Response({'Ошибка':
                                 'нельзя подписаться на самого себя'},
                                status=status.HTTP_400_BAD_REQUEST)
            serializer = SubscriptionsSerializer(
                author,
                context={'request': request}
            )
            Follow.objects.create(subscriber=user, author=author)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        if subscription.exists():
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({'error': f'Вы не подписаны на {author}'},
                        status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['GET'],
            detail=False,
            permission_classes=[permissions.IsAuthenticated])
    def subscriptions(self, request):
        if request.user.is_anonymous or not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        subscriptions = Follow.objects.filter(subscriber=request.user)
        page = self.paginate_queryset(subscriptions)
        serializer = SubscriptionsSerializer(
            page, many=True,
            context={'request': request})
        return self.get_paginated_response(serializer.data)


class RecipeViewSet(mixins.CreateModelMixin,
                    mixins.ListModelMixin,
                    mixins.RetrieveModelMixin,
                    mixins.UpdateModelMixin,
                    mixins.DestroyModelMixin,
                    viewsets.GenericViewSet):
    queryset = Recipe.objects.all()
    permission_classes = (permissions.IsAuthenticated, )
    serializer_class = RecipeCreateUpdateSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    pagination_class = CustomPagination

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return (permissions.AllowAny(),)
        elif self.action == 'destroy':
            return (AuthorOnly(), )
        return super().get_permissions()

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return RecipeSerializer
        return RecipeCreateUpdateSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_ingredients(self, user_name):
        ingredients = RecipeIngredient.objects.filter(
            recipe__in=RecipeShoppingList.objects.filter(
                user__username=user_name
            ).values_list('recipe')
        ).values(
            name=F('ingredient__name'),
            unit=F('ingredient__measurement_unit')
        ).annotate(amount=Sum('amount')).values_list(
            'ingredient__name', 'ingredient__measurement_unit', 'amount')
        return ingredients

    @action(detail=True, methods=['POST', 'DELETE'])
    def favorite(self, request, pk=None):
        if request.method == 'POST':
            return self._add_to_favorite(request, pk)
        elif request.method == 'DELETE':
            return self._remove_from_favorite(request, pk)

    def _add_to_favorite(self, request, pk):
        user = request.user
        recipes = Recipe.objects.filter(pk=pk)
        if recipes.exists():
            recipe = recipes.first()
        else:
            return Response("Несуществующий рецепт",
                            status=status.HTTP_400_BAD_REQUEST)

        if FavoriteRecipe.objects.filter(user=user, recipe=recipe).exists():
            return Response("Рецепт уже добавлен в избранное",
                            status=status.HTTP_400_BAD_REQUEST)

        data = {'user': user.id, 'recipe': recipe.id}
        context = {'request': request}
        serializer = FavoriteRecipeSerializer(data=data, context=context)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

    def _remove_from_favorite(self, request, pk):
        user = request.user
        recipe = get_object_or_404(Recipe, pk=pk)

        try:
            favorite_item = FavoriteRecipe.objects.get(user=user,
                                                       recipe=recipe)
            favorite_item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except FavoriteRecipe.DoesNotExist:
            return Response("Рецепта нет в избранном",
                            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['POST', 'DELETE'])
    def shopping_cart(self, request, pk=None):
        if request.method == 'POST':
            return self._add_to_shopping_cart(request, pk)
        elif request.method == 'DELETE':
            return self._remove_from_shopping_cart(request, pk)

    def _add_to_shopping_cart(self, request, pk):
        user = request.user
        recipes = Recipe.objects.filter(pk=pk)
        if recipes.exists():
            recipe = recipes.first()
        else:
            return Response("Несуществующий рецепт",
                            status=status.HTTP_400_BAD_REQUEST)

        if RecipeShoppingList.objects.filter(user=user,
                                             recipe=recipe).exists():
            return Response("Рецепт уже в корзине",
                            status=status.HTTP_400_BAD_REQUEST)

        data = {'user': user.id, 'recipe': recipe.id}
        context = {'request': request}
        serializer = RecipeShoppingListSerializer(data=data, context=context)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

    def _remove_from_shopping_cart(self, request, pk):
        user = request.user
        recipe = get_object_or_404(Recipe, pk=pk)

        try:
            shopping_list_item = RecipeShoppingList.objects.get(user=user,
                                                                recipe=recipe)
            shopping_list_item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except RecipeShoppingList.DoesNotExist:
            return Response("Рецепта нет в корзине",
                            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, permission_classes=[AuthorOnly])
    def download_shopping_cart(self, request):
        ingredients = self.get_ingredients(request.user)
        shopping_list = 'Список покупок:'
        for ingredient in ingredients:
            shopping_list += (
                f"\n- {ingredient[0]} "
                f"({ingredient[1]}) - "
                f"{ingredient[2]}")
        file = 'shopping_list.txt'
        response = HttpResponse(shopping_list, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{file}.txt"'
        return response


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None
    permission_classes = (permissions.AllowAny,)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None
    permission_classes = (permissions.AllowAny,)
    filter_backends = (IngredientFilter,)
    search_fields = ('^name', )
