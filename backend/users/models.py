from django.contrib.auth.models import AbstractUser
from django.db import models
from .model_variables import (ROLES,
                              FIRST_NAME_LEN,
                              LAST_NAME_LEN,
                              USERNAME_LEN,
                              PASSWORD_LEN)


class User(AbstractUser):
    USER_TYPE_CHOICES = ROLES
    user_type = models.PositiveSmallIntegerField(choices=USER_TYPE_CHOICES,
                                                 default=2)
    first_name = models.CharField(max_length=FIRST_NAME_LEN)
    last_name = models.CharField(max_length=LAST_NAME_LEN)
    email = models.EmailField(unique=True)
    username = models.CharField(
        verbose_name=('Логин'),
        max_length=USERNAME_LEN,
        unique=True,
    )
    password = models.CharField(
        verbose_name=('Пароль'),
        max_length=PASSWORD_LEN
    )


class Follow(models.Model):
    subscriber = models.ForeignKey(User, related_name='subscriptions',
                                   on_delete=models.CASCADE)
    author = models.ForeignKey(User, related_name='subscribers',
                               on_delete=models.CASCADE)
    date_subscribed = models.DateTimeField(auto_now_add=True)
