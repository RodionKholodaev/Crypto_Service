# Crypto_Service

docker-compose up -d --build

docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
