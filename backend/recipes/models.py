from django.contrib.auth import get_user_model
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from .model_variables import (TAG_NAME_LENGTH,
                              COLOR_LEN_STR,
                              INGREDIENT_NAME_LEN,
                              MEASURE_NAME_LEN,
                              MEASURE_UNITS,
                              RECIPE_MAX_LEN)


User = get_user_model()


class Tag(models.Model):
    name = models.CharField(max_length=TAG_NAME_LENGTH, unique=True)
    color = models.CharField(max_length=COLOR_LEN_STR, unique=True)
    slug = models.SlugField(unique=True)


class Ingredient(models.Model):
    name = models.CharField(max_length=INGREDIENT_NAME_LEN, unique=True)
    measurement_unit = models.CharField(max_length=MEASURE_NAME_LEN)


class Recipe(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL,
                               on_delete=models.CASCADE,
                               related_name='recipes')
    name = models.CharField(max_length=RECIPE_MAX_LEN,)
    image = models.ImageField(upload_to='recipes/images/')
    text = models.TextField(blank=False)
    measurement_unit_choices = MEASURE_UNITS
    ingredients = models.ManyToManyField(
        'Ingredient',
        through='RecipeIngredient',
        blank=False
    )
    tags = models.ManyToManyField('Tag', blank=False)
    cooking_time = models.PositiveIntegerField(
        validators=[
            MinValueValidator(
                1,
                message="Время не может быть менее 1 минуты"),
            MaxValueValidator(
                480,
                message="Время не может быть более 8 часов")])


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    amount = models.PositiveSmallIntegerField()


class RecipeTag(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)


class RecipeShoppingList(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'recipe']


class FavoriteRecipe(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['user', 'recipe']
