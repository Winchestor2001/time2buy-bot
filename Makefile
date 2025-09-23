SHELL := /bin/bash
PROJECT_NAME = time2buy
DJANGO_SERVICE = $(PROJECT_NAME)-django
BOT_SERVICE = $(PROJECT_NAME)-bot

.PHONY: help migrate makemigrations collectstatic restart-django restart-bot restart-all logs-django logs-bot

help:
	@echo "Команды:"
	@echo "  make migrate          - применить миграции"
	@echo "  make makemigrations   - создать новые миграции"
	@echo "  make collectstatic    - собрать статику"
	@echo "  make restart-django   - перезапустить Django (gunicorn)"
	@echo "  make restart-bot      - перезапустить Telegram-бота"
	@echo "  make restart-all      - перезапустить всё (django + bot)"
	@echo "  make logs-django      - показать логи Django"
	@echo "  make logs-bot         - показать логи бота"
	@echo "  make r-install        - установить зависимости из requirements.txt"

migrate:
	. .venv/bin/activate && python manage.py migrate

makemigrations:
	. .venv/bin/activate && python manage.py makemigrations

collectstatic:
	. .venv/bin/activate && python manage.py collectstatic --noinput

restart-django:
	sudo systemctl restart $(DJANGO_SERVICE)

restart-bot:
	sudo systemctl restart $(BOT_SERVICE)

restart-all: restart-django restart-bot

logs-django:
	sudo journalctl -u $(DJANGO_SERVICE) -f

logs-bot:
	sudo journalctl -u $(BOT_SERVICE) -f

r-install:
	. .venv/bin/activate && pip install -r requirements.txt