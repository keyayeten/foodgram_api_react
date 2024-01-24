import random
from django.core.management import BaseCommand
from django.utils.text import slugify
from recipes.models import Tag


class Command(BaseCommand):
    def handle(self, *args, **options):
        tags_data = [
            {"name": "хрючево",
             "color": self.generate_random_color(),
             "slug": self.generate_slug("hryuchevo")},
            {"name": "помои",
             "color": self.generate_random_color(),
             "slug": self.generate_slug("pomoyi")},
            {"name": "баланда",
             "color": self.generate_random_color(),
             "slug": self.generate_slug("balanda")},
        ]
        tags = [Tag(**data) for data in tags_data]
        Tag.objects.bulk_create(tags, ignore_conflicts=True)

    @staticmethod
    def generate_random_color():
        return "#{:06x}".format(random.randint(0, 0xFFFFFF))

    @staticmethod
    def generate_slug(name):
        return slugify(name)
