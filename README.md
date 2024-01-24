# praktikum_new_diplom
Проект foodgram для возможности делиться своими рецептами.

## Где посмотреть
Проект размещен по ссылке: https://foodgramremix.ddns.net/
(DNS пока прикурил, меняю)
Доступ к админке:
login: vlad
password: 123123123


## Запуск локально через докер:

```
cd /infra
sudo docker compose -f docker-compose.production.yml pull
sudo docker compose -f docker-compose.production.yml down --volumes --rmi all
sudo docker compose -f docker-compose.production.yml up -d
sudo docker compose -f docker-compose.production.yml exec backend python manage.py migrate
sudo docker compose -f docker-compose.production.yml exec backend python manage.py import_data
sudo docker compose -f docker-compose.production.yml exec backend python manage.py collectstatic
sudo docker compose -f docker-compose.production.yml exec backend python .\manage.py create_custom_superuser <username> <email> <first_name> <last_name>
```
(Выполнить миграции, наполнить бд тестовыми данными, собрать статику, создать суперпользователя)

Перед этим необходимо создать файл с переменными окружения .env и прописать POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, DB_HOST, DB_PORT

