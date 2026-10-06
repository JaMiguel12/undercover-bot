FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite+aiosqlite:////app/storage/undercover.db

WORKDIR /app

# Dépendances d'abord (couche mise en cache tant que pyproject.toml ne change pas)
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY bot ./bot
COPY game ./game
COPY ai ./ai
COPY db ./db
COPY data ./data

# Utilisateur non root ; le dossier storage reçoit le fichier SQLite (volume)
RUN useradd --create-home --uid 1000 undercover \
    && mkdir -p /app/storage \
    && chown -R undercover:undercover /app
USER undercover

VOLUME ["/app/storage"]

# Aucun secret dans l'image : BOT_TOKEN et GROQ_API_KEY viennent de l'environnement (.env)
CMD ["python", "-m", "bot.main"]
