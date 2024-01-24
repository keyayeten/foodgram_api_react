import csv
from typing import Any
from django.core.management import BaseCommand
from django.conf import settings
from recipes.models import Ingredient


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any):
        with open(f"{settings.BASE_DIR}/data/ingredients.csv",
                  encoding="utf-8") as source:
            reader = csv.reader(source)
            ingredients = [Ingredient(id, *data)
                           for id, data in enumerate(reader, start=1)]
            Ingredient.objects.bulk_create(ingredients, ignore_conflicts=True)
