import re
from drf_base64.fields import Base64ImageField
from djoser.serializers import UserCreateSerializer, UserSerializer
from rest_framework import serializers, status
from rest_framework.validators import UniqueTogetherValidator, ValidationError
from recipes.models import (
    FavoriteRecipe,
    Ingredient,
    Recipe,
    RecipeIngredient,
    RecipeShoppingList,
    Tag
)
from users.models import Follow, User
from django.core.exceptions import PermissionDenied


class CustomUserCreateSerializer(UserCreateSerializer):
    class Meta:
        model = User
        fields = ['email', 'id', 'username', 'first_name',
                  'last_name', 'password']

    @staticmethod
    def invalid_character(value):
        match = re.search(r'[^a-zA-Z0-9.@+\-_]', value)
        if match:
            return match.group()
        return None

    def validate_username(self, value):
        if value.lower() == 'me':
            raise serializers.ValidationError("Имя 'me' недопустимо",
                                              code=status.HTTP_400_BAD_REQUEST)
        if not re.match(r'^[\w.@+-]+$', value):
            raise serializers.ValidationError(
                (f"Имя пользователя не соответствует требуемому формату. "
                 f"Содержится лишний символ {self.invalid_character(value)}"),
                code='invalid_username')
        return value


class CustomUserSerializer(UserSerializer):
    is_subscribed = serializers.SerializerMethodField(read_only=True)

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        return Follow.objects.filter(
            subscriber=request.user,
            author=obj
        ).exists() if request and not request.user.is_anonymous else False

    class Meta:
        model = User
        fields = [
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
        ]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color', 'slug']


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'measurement_unit']


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    unit = serializers.ReadOnlyField(
        source='ingredient.unit'
    )
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit',
        read_only=True
    )

    class Meta:
        model = RecipeIngredient
        fields = [
            'id',
            'name',
            'unit',
            'amount', 'measurement_unit'
        ]


class RecipeShortSerializer(serializers.ModelSerializer):
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ['id', 'name', 'image', 'cooking_time']


class RecipeSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    author = CustomUserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        read_only=True,
        many=True,
        source='recipeingredient_set'
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ['id', 'tags', 'author', 'ingredients',
                  'is_favorited', 'is_in_shopping_cart',
                  'name', 'image', 'text', 'cooking_time']

    def get_is_favorited(self, obj):
        request = self.context.get('request')

        return (FavoriteRecipe.objects.filter(
            recipe=obj, user=request.user).exists()
            if request and not request.user.is_anonymous else False)

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')

        return (RecipeShoppingList.objects.filter(
            recipe=obj, user=request.user).exists()
            if request and not request.user.is_anonymous else False)


class IngredientAddRecipeSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        source='ingredient')
    amount = serializers.IntegerField()

    class Meta:
        model = RecipeIngredient
        fields = ['id', 'amount']


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    ingredients = IngredientAddRecipeSerializer(
        many=True,
    )
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True
    )
    image = Base64ImageField()
    author = CustomUserSerializer(read_only=True)

    class Meta:
        model = Recipe
        fields = ['id', 'ingredients', 'tags',
                  'image', 'name', 'text',
                  'cooking_time', 'author']

    def _validate_recipe_creation(self, tags, ingredients, cooking_time):
        if not tags:
            raise ValidationError("Нельзя добавить рецепт без тегов")
        elif not ingredients:
            raise ValidationError("Нельзя добавить рецепт без ингридиентов")
        elif len(set(tags)) != len(tags):
            raise ValidationError("Теги не должны повторяться")
        elif cooking_time < 1:
            raise ValidationError("Время не может быть меньше 1 минуты")
        ing_set = set()
        for ingredient in ingredients:
            amount = ingredient['amount']
            ingredient_in = ingredient['ingredient']
            if not amount:
                raise ValidationError("Добавьте количество для ингридиента")
            elif amount < 1:
                raise ValidationError(f"Количество ингридиента"
                                      f" '{ingredient_in.name}' "
                                      f" не может быть меньше 1 штуки")
            if ingredient_in in ing_set:
                raise ValidationError(f"Ингридиенты не должны дублироваться"
                                      f" '{ingredient_in.name}' повторяется")
            ing_set.add(ingredient_in)

    def _add_ingredients(self, recipe, ingredients):
        RecipeIngredient.objects.bulk_create(
            RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient['ingredient'],
                amount=ingredient['amount']
            ) for ingredient in ingredients
        )

    def create(self, validated_data):
        author = self.context.get('request').user
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('ingredients')
        image = validated_data.pop('image')
        self._validate_recipe_creation(
            tags, ingredients, validated_data["cooking_time"])
        validated_data.pop('user')
        recipe = Recipe.objects.create(image=image, author=author,
                                       **validated_data)
        recipe.tags.set(tags)
        self._add_ingredients(recipe, ingredients)
        return recipe

    def update(self, recipe, validated_data):
        if recipe.author != self.context.get('request').user:
            raise PermissionDenied
        try:
            tags = validated_data.pop('tags')
            ingredients = validated_data.pop('ingredients')
        except KeyError:
            raise ValidationError("Тэги не были добавлены")
        try:
            ingredients = validated_data.pop('ingredients')
        except KeyError:
            raise ValidationError("Ингридиенты не были добавлены")
        RecipeIngredient.objects.filter(recipe=recipe).delete()
        recipe.tags.set(tags)
        self._validate_recipe_creation(
            tags, ingredients, validated_data["cooking_time"])
        self._add_ingredients(recipe, ingredients)
        return super().update(recipe, validated_data)

    def to_representation(self, recipe):
        context = {'request': self.context.get('request')}
        return RecipeSerializer(recipe, context=context).data


class SubscriptionsSerializer(serializers.ModelSerializer):
    recipes = serializers.SerializerMethodField(read_only=True)
    recipes_count = serializers.SerializerMethodField(read_only=True)
    is_subscribed = serializers.SerializerMethodField(read_only=True)
    email = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()

    class Meta(CustomUserSerializer.Meta):
        fields = [
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'recipes_count',
            'recipes'
        ]
        read_only_fields = (
            'email',
            'username',
            'first_name',
            'last_name'
        )

    def get_email(self, obj):
        if hasattr(obj, 'author'):
            return obj.author.email
        else:
            return obj.email

    def get_username(self, obj):
        if hasattr(obj, 'author'):
            return obj.author.username
        else:
            return obj.username

    def get_first_name(self, obj):
        if hasattr(obj, 'author'):
            return obj.author.first_name
        else:
            return obj.first_name

    def get_last_name(self, obj):
        if hasattr(obj, 'author'):
            return obj.author.last_name
        else:
            return obj.last_name

    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.query_params.get('recipes_limit')
        context = {'request': request}
        author = obj if isinstance(obj, User) else obj.author
        recipes = Recipe.objects.filter(author=author)
        if limit:
            recipes = recipes[:int(limit)]

        serializer = RecipeShortSerializer(recipes, many=True, context=context)
        return serializer.data

    def get_recipes_count(self, obj):
        author = obj if isinstance(obj, User) else obj.author
        return Recipe.objects.filter(author=author).count()

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        user = request.user if request else None

        author = obj if isinstance(obj, User) else obj.author

        if user and not user.is_anonymous:
            return Follow.objects.filter(subscriber=user,
                                         author=author).exists()
        else:
            return False


class FollowSerializer(serializers.ModelSerializer):
    subscriber = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        default=serializers.CurrentUserDefault()
    )
    author = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    def validate(self, data):
        if data['subscriber'] == data['author']:
            raise ValidationError("Нельзя подписаться на себя")
        return data

    class Meta:
        model = Follow
        fields = ['id', 'subscriber', 'author', 'date_subscribed']
        validators = [
            UniqueTogetherValidator(
                queryset=Follow.objects.all(),
                fields=['subscriber', 'author']
            )
        ]


class FavoriteRecipeSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True,
        default=serializers.CurrentUserDefault()
    )
    recipe = serializers.PrimaryKeyRelatedField(
        queryset=Recipe.objects.all(),
        write_only=True
    )
    recipe_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = FavoriteRecipe
        fields = ['user', 'recipe', 'recipe_details']
        validators = [
            UniqueTogetherValidator(
                queryset=FavoriteRecipe.objects.all(),
                fields=['user', 'recipe']
            )
        ]

    def get_recipe_details(self, obj):
        return RecipeShortSerializer(obj.recipe).data

    def to_representation(self, instance):
        result = RecipeShortSerializer(instance.recipe).data
        return result


class RecipeShoppingListSerializer(serializers.ModelSerializer):
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())
    user = serializers.PrimaryKeyRelatedField(
        read_only=True,
        default=serializers.CurrentUserDefault())

    def create(self, validated_data):
        recipe_shopping_list = RecipeShoppingList(
            user=self.context['request'].user,
            recipe=validated_data['recipe']
        )
        recipe_shopping_list.save()
        return recipe_shopping_list

    def validate(self, data):
        recipe = data['recipe']
        user = self.context.get('request').user
        if RecipeShoppingList.objects.filter(user=user,
                                             recipe=recipe).exists():
            raise ValidationError("Рецепт уже в корзине")
        return data

    class Meta:
        model = RecipeShoppingList
        fields = ['id', 'user', 'recipe', 'date_added']
        validators = [
            UniqueTogetherValidator(
                queryset=RecipeShoppingList.objects.all(),
                fields=['user', 'recipe']
            )
        ]

    def to_representation(self, instance):
        result = RecipeShortSerializer(instance.recipe).data
        return result
