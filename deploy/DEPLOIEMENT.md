# Déployer le bot sur une machine Oracle Cloud (Ubuntu ARM)

Commandes à copier-coller. Remplace `ADRESSE_IP` par l'adresse publique de la machine et
`C:\chemin\ta-cle.key` par ta clé privée SSH. **Ne mets jamais le `.env` dans l'archive.**

## 1. Depuis ton PC (PowerShell)

```text
cd C:\chemin\vers\undercover
scp -i C:\chemin\ta-cle.key deploy\undercover-bot.zip ubuntu@ADRESSE_IP:~
ssh -i C:\chemin\ta-cle.key ubuntu@ADRESSE_IP
```

## 2. Sur la machine : installer Docker et un peu de mémoire de secours

```text
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
exit
```

Reconnecte-toi (même commande `ssh`) pour que le droit Docker soit pris en compte.

## 3. Sur la machine : installer le projet et créer le `.env`

```text
sudo apt-get install -y unzip
mkdir -p ~/undercover && unzip -o ~/undercover-bot.zip -d ~/undercover
cd ~/undercover
cp .env.example .env
nano .env
```

Dans `nano` : remplis `BOT_TOKEN=` et `GROQ_API_KEY=` (sans espaces ni guillemets). Enregistre avec
`Ctrl+O` puis `Entrée`, quitte avec `Ctrl+X`. `GROQ_MODEL`, `SOLO_WAIT_TIMEOUT` et les autres
lignes sont déjà bonnes.

## 4. Arrêter le bot sur ton PC, puis lancer sur le serveur

Un jeton Telegram ne peut servir qu'à un seul bot à la fois.

Sur ton PC :
```text
docker compose down
```

Sur la machine :
```text
cd ~/undercover
docker compose up -d --build
docker compose logs --tail 20
```

Tu dois voir « modèle … disponible » puis « Run polling for bot ». Le bot redémarre seul après un
plantage ou un redémarrage de la machine.

## 5. Vérifier la mémoire (évite la récupération de la machine par Oracle)

```text
free -m
```

Oracle peut récupérer une machine ARM gratuite jugée inactive (CPU, réseau **et** mémoire sous
20 % sur 7 jours). Regarde la colonne `used` par rapport à `total` : au-dessus de 20 %, tu es
tranquille. En dessous, réduis la mémoire de la machine dans la console Oracle.

## 6. Sauvegarde automatique de la base (toutes les 6 heures)

```text
chmod +x ~/undercover/deploy/backup.sh
(crontab -l 2>/dev/null; echo '0 */6 * * * /home/ubuntu/undercover/deploy/backup.sh >> /home/ubuntu/backup.log 2>&1') | crontab -
sh ~/undercover/deploy/backup.sh
```

Les 14 dernières sauvegardes sont dans `~/backups`. Pour en récupérer une sur ton PC :

```text
scp -i C:\chemin\ta-cle.key ubuntu@ADRESSE_IP:~/backups/undercover-DATE.db .
```

## 7. Mettre à jour le bot plus tard

Sur ton PC, reconstruis l'archive, envoie-la, puis sur la machine :

```text
cd ~/undercover && unzip -o ~/undercover-bot.zip -d ~/undercover && docker compose up -d --build
```

Ton `.env` et la base ne sont pas touchés.

## En cas de problème

- `docker compose logs --tail 50` : lit les erreurs.
- Le bot ne se connecte pas : vérifie `BOT_TOKEN` et que le bot ne tourne plus sur ton PC.
- Les IA passent leur tour : regarde les lignes `ERROR` ou `WARNING` des logs (clé ou modèle Groq).
- La machine ne répond plus en SSH : redémarre-la depuis la console Oracle (Instance → Reboot).
