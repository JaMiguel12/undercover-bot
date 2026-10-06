"""TOUS les textes français du bot (principe VII). Les noms sont échappés pour le mode HTML."""

from html import escape
from typing import Any

from game.models import MAX_PLAYERS, GameState

ROLE_LABELS = {"civilian": "Civil", "undercover": "Undercover"}
AI_PREFIX = "🤖"
AI_PASS_TEXT = "Je passe mon tour 🤐"
MODE_LABELS = {
    "elimination": "☠️ Avec élimination",
    "no_elimination": "🔄 Sans élimination",
}


def esc(value: object) -> str:
    return escape(str(value))


def role_label(role: str) -> str:
    return ROLE_LABELS.get(role, role)


# ---------------------------------------------------------------- aide et règles

RULES = (
    "📜 <b>Règles d'Undercover</b>\n\n"
    "Chaque joueur reçoit un mot en privé. La plupart des joueurs (les <b>Civils</b>) ont le même "
    "mot ; les <b>Undercovers</b> ont un mot différent, mais proche. Personne ne connaît son "
    "rôle : à vous de le deviner !\n\n"
    "🗣️ <b>Description</b> : chacun son tour, dites <b>un seul mot</b> pour décrire le vôtre, sans "
    "le prononcer. On fait <b>3 tours</b> de description.\n"
    "🗳️ <b>Vote</b> : après les 3 tours, tout le monde vote pour désigner un suspect. Égalité : "
    "revote, puis tirage au sort.\n\n"
    "Deux types de partie, au choix du créateur :\n"
    "☠️ <b>Avec élimination</b> : le plus voté est éliminé (son rôle est révélé), et on recommence "
    "3 tours, jusqu'à une victoire.\n"
    "🔄 <b>Sans élimination</b> : un seul vote ; on révèle les rôles, les mots et les points, puis "
    "une nouvelle partie démarre avec les mêmes joueurs.\n\n"
    "🏆 Les Civils gagnent s'ils éliminent (ou accusent) un Undercover. Les Undercovers gagnent "
    "sinon, ou quand il ne reste qu'un Civil.\n"
    "🤖 Zendaya IA, Kendall IA et BFF Diva IA complètent la partie s'il manque des joueurs."
)

HELP_GROUP = (
    "🎮 <b>Commandes du groupe</b>\n"
    "/nouvelle — créer une partie\n"
    "/lancer — lancer la partie (créateur)\n"
    "/annuler — annuler (créateur)\n"
    "/etat — état de la partie\n"
    "/regles — les règles\n"
    "/classement — le classement du groupe"
)

HELP_PRIVATE = (
    "👋 <b>Aide</b>\n"
    "/start — activer le bot pour recevoir ton mot\n"
    "/monmot — revoir ton mot\n"
    "/aide — cette aide\n\n"
    "Les parties se jouent dans un groupe avec /nouvelle."
)

START_OK = "✅ C'est bon, je peux t'écrire en privé ! Retourne dans le groupe pour jouer."
START_DEEP_LINK = "✅ C'est bon, tu es prêt ! Retourne dans le groupe : la partie peut être lancée."
GROUP_ONLY = "Cette commande se joue dans un groupe Telegram."
PRIVATE_ONLY = "Écris-moi en privé pour cette commande."
NO_GAME = "Aucune partie en cours dans ce groupe. Lance-en une avec /nouvelle !"
GAME_EXISTS = "Il y a déjà une partie en cours dans ce groupe."
ALREADY_IN_GAME = "Tu es déjà inscrit dans une autre partie."
LOBBY_STALE = "Ce lobby n'est plus actif."
NO_ACTIVE_GAME_PRIVATE = "Tu n'as pas de partie en cours."
VOTE_ENDED = "Ce vote est terminé."
NOT_CREATOR = "Seul le créateur peut faire ça."
LAUNCHING = "🚀 C'est parti !"


# ---------------------------------------------------------------- lobby


def render_lobby(state: GameState, solo_remaining: int | None = None) -> str:
    creator = state.player(state.creator_id)
    lines = [
        "🕵️ <b>Undercover — nouvelle partie !</b>",
        f"Créateur : {esc(creator.name)}",
        f"Type de partie : <b>{MODE_LABELS[state.mode.value]}</b> (choix du créateur)",
        "",
        f"Joueurs ({len(state.humans)}/{MAX_PLAYERS}) :",
    ]
    for p in state.humans:
        if p.can_dm:
            lines.append(f"✅ {esc(p.name)}")
        else:
            lines.append(f"⚠️ {esc(p.name)} (doit d'abord démarrer le bot)")
    lines.append("")
    lines.append(
        "🤖 Zendaya IA, Kendall IA et BFF Diva IA rejoignent automatiquement "
        "s'il manque des joueurs."
    )
    if state.solo_waiting:
        lines.append("")
        if solo_remaining is not None:
            lines.append(
                f"⏳ <b>Dernier appel !</b> La partie démarre dans {solo_remaining} s. "
                "Rejoins vite, sinon les IA entrent en jeu !"
            )
        else:
            lines.append("⏳ <b>Dernier appel !</b> La partie va bientôt démarrer.")
    return "\n".join(lines)


# ---------------------------------------------------------------- textes de groupe

_CANCEL_REASONS = {
    "creator": "Partie annulée par le créateur.",
    "lobby_expired": "⌛ Le lobby a expiré (10 minutes d'inactivité). Relance avec /nouvelle !",
    "lobby_empty": "Le lobby est vide, il est supprimé.",
    "no_votes": "😴 Personne ne vote depuis 3 tours : la partie est annulée, aucun point attribué.",
}


def _group_lobby_deleted(p: dict[str, Any]) -> str:
    return "Le lobby est vide, il est supprimé."


def _group_creator_transferred(p: dict[str, Any]) -> str:
    return f"👑 {esc(p['name'])} devient le nouveau créateur de la partie."


def _group_player_left(p: dict[str, Any]) -> str:
    return f"👋 {esc(p['name'])} a quitté le lobby."


def _group_launch_blocked(p: dict[str, Any]) -> str:
    names = ", ".join(esc(n) for n in p["names"])
    return (
        "⛔ Lancement impossible : "
        f"{names} doit d'abord démarrer le bot en privé (bouton « Démarrer le bot »)."
    )


def _group_solo_last_call(p: dict[str, Any]) -> str:
    return (
        "📣 <b>Dernier appel !</b> Un seul joueur est inscrit. "
        f"Dans {p['seconds']} secondes, les 3 IA entrent en jeu. "
        "Rejoignez la partie avec le bouton « Rejoindre » !"
    )


def _group_cancelled(p: dict[str, Any]) -> str:
    return _CANCEL_REASONS.get(p.get("reason", ""), "Partie annulée.")


def _group_game_started(p: dict[str, Any]) -> str:
    names = ", ".join(esc(n) for n in p["players"])
    ai = f" dont {p['ai_count']} IA" if p["ai_count"] else ""
    return (
        f"🎬 <b>La partie commence !</b> {MODE_LABELS[p['mode']]} — {p['total']} joueurs{ai} : "
        f"{names}.\n"
        "📩 Chaque joueur a reçu son mot en message privé."
    )


def _group_round_start(p: dict[str, Any]) -> str:
    order = " → ".join(esc(n) for n in p["order"])
    return (
        f"🔔 <b>Manche {p['round']} — tour {p['sub_round']}/{p['sub_total']}</b>\n"
        f"Ordre de passage : {order}"
    )


def _group_turn(p: dict[str, Any]) -> str:
    return f"🗣️ C'est à <b>{esc(p['name'])}</b> : dis <b>un mot</b> pour décrire ton mot !"


def _group_description_too_long(p: dict[str, Any]) -> str:
    return f"✂️ {esc(p['name'])}, un seul mot, s'il te plaît !"


def _group_description_forbidden(p: dict[str, Any]) -> str:
    return (
        f"🚫 {esc(p['name'])}, tu ne peux pas utiliser ton mot (ni un mot qui lui ressemble) ! "
        "Propose une autre description."
    )


def _group_ai_description(p: dict[str, Any]) -> str:
    return f"{AI_PREFIX} {esc(p['name'])} : {esc(p['text'])}"


def _group_turn_passed(p: dict[str, Any]) -> str:
    if p.get("is_ai"):
        return f"{AI_PREFIX} {esc(p['name'])} : {AI_PASS_TEXT}"
    return f"⏱️ {esc(p['name'])} passe son tour."


def _group_recap(p: dict[str, Any]) -> str:
    lines = [f"📝 <b>Récapitulatif de la manche {p['round']}</b>"]
    for name, words in p["items"]:
        said = " → ".join(esc(w) if w else "<i>(passé)</i>" for w in words)
        lines.append(f"• {esc(name)} : {said}")
    return "\n".join(lines)


def _group_vote_open(p: dict[str, Any]) -> str:
    if p["kind"] == "revote":
        return "🗳️ <b>Revote !</b> Départagez les joueurs à égalité avec les boutons ci-dessous."
    if p["mode"] == "no_elimination":
        return "🗳️ <b>Vote final !</b> Qui est l'Undercover ? Votez avec les boutons ci-dessous."
    return "🗳️ <b>Vote !</b> Qui est l'intrus ? Votez avec les boutons ci-dessous."


def _group_no_votes(p: dict[str, Any]) -> str:
    return "🤷 Aucun vote exprimé : personne n'est éliminé, on repart pour un tour !"


def _group_vote_result(p: dict[str, Any]) -> str:
    lines = ["📊 <b>Résultat du vote</b>"]
    for voter, target in p["ballots"]:
        lines.append(f"• {esc(voter)} → {esc(target)}")
    return "\n".join(lines)


def _group_tie_revote(p: dict[str, Any]) -> str:
    names = ", ".join(esc(n) for n in p["names"])
    return f"⚖️ Égalité entre {names} ! Revote entre ces joueurs."


def _group_tie_draw(p: dict[str, Any]) -> str:
    names = ", ".join(esc(n) for n in p["names"])
    return f"🎲 Nouvelle égalité entre {names} : tirage au sort… c'est <b>{esc(p['name'])}</b> !"


def _group_eliminated(p: dict[str, Any]) -> str:
    return f"☠️ <b>{esc(p['name'])}</b> est éliminé(e) ! Son rôle : <b>{role_label(p['role'])}</b>."


_OUTCOME_TITLES = {
    "civilians": "🏆 <b>Victoire des Civils !</b>",
    "infiltrators": "🏆 <b>Victoire des Undercovers !</b>",
}


def _group_accused(p: dict[str, Any]) -> str:
    return f"⚖️ Le plus voté est <b>{esc(p['name'])}</b> : c'est l'accusé !"


def _group_game_end(p: dict[str, Any]) -> str:
    words = p["words"]
    lines = [_OUTCOME_TITLES.get(p["outcome"], "Fin de partie")]
    if p.get("accused"):
        lines.append(f"Accusé : {esc(p['accused'])}")
    lines += [
        "",
        "🔓 <b>Les mots</b>",
        f"• Civils : {esc(words['civilian'])}",
        f"• Undercovers : {esc(words['undercover'])}",
        "",
        "🎭 <b>Les rôles</b>",
    ]
    for name, role, word, is_ai in p["players"]:
        prefix = f"{AI_PREFIX} " if is_ai else ""
        lines.append(f"• {prefix}{esc(name)} — {role_label(role)} ({esc(word)})")
    if p["points"]:
        lines.append("")
        lines.append("⭐ <b>Points de la partie</b>")
        for name, pts in sorted(p["points"], key=lambda x: -x[1]):
            lines.append(f"• {esc(name)} : +{pts}")
    return "\n".join(lines)


_GROUP_RENDERERS = {
    "lobby_deleted": _group_lobby_deleted,
    "creator_transferred": _group_creator_transferred,
    "player_left": _group_player_left,
    "launch_blocked": _group_launch_blocked,
    "solo_last_call": _group_solo_last_call,
    "cancelled": _group_cancelled,
    "game_started": _group_game_started,
    "round_start": _group_round_start,
    "turn": _group_turn,
    "description_too_long": _group_description_too_long,
    "description_forbidden": _group_description_forbidden,
    "ai_description": _group_ai_description,
    "turn_passed": _group_turn_passed,
    "recap": _group_recap,
    "vote_open": _group_vote_open,
    "no_votes": _group_no_votes,
    "vote_result": _group_vote_result,
    "tie_revote": _group_tie_revote,
    "tie_draw": _group_tie_draw,
    "eliminated": _group_eliminated,
    "accused": _group_accused,
    "game_end": _group_game_end,
}


def group_text(key: str, params: dict[str, Any]) -> str:
    """Texte du groupe pour une clé émise par le moteur."""
    return _GROUP_RENDERERS[key](params)


# ---------------------------------------------------------------- privé et retours discrets


def private_text(key: str, params: dict[str, Any]) -> str:
    if key == "your_word":
        return (
            f"🤫 Ton mot : <b>{esc(params['word'])}</b>\n"
            "Ne le dis à personne ! Tu peux le revoir avec /monmot."
        )
    raise KeyError(key)


_NOTIFY_TEXTS = {
    "not_lobby": "La partie a déjà commencé.",
    "already_joined": "Tu es déjà inscrit.",
    "full": "Partie complète (8 joueurs maximum).",
    "not_creator": NOT_CREATOR,
    "vote_closed": VOTE_ENDED,
    "not_alive": "Tu ne peux pas voter : tu es éliminé.",
    "self_vote": "Tu ne peux pas voter pour toi-même !",
    "invalid_target": "Ce joueur ne peut pas être choisi.",
}


def notify_text(key: str, params: dict[str, Any]) -> str:
    if key == "vote_recorded":
        return f"Vote enregistré : {params['target']}"
    return _NOTIFY_TEXTS.get(key, "")


# ---------------------------------------------------------------- état et mot


def state_text(state: GameState) -> str:
    if state.phase.value == "lobby":
        return f"🕵️ Lobby ouvert : {len(state.humans)} joueur(s) inscrit(s)."
    alive = ", ".join(esc(p.name) for p in state.alive)
    mode = MODE_LABELS[state.mode.value]
    lines = [
        f"📋 <b>État de la partie</b> — manche {state.round} ({mode})",
        f"Phase : {state.phase.value}",
    ]
    lines.append(f"Joueurs vivants : {alive}")
    speaker = state.current_speaker
    if speaker:
        lines.append(
            f"Tour de description {state.sub_round} : à <b>{esc(speaker.name)}</b> de parler"
        )
    return "\n".join(lines)


def my_word_text(word: str) -> str:
    return f"🤫 Ton mot : <b>{esc(word)}</b>"


def word_dm_failed(name: str) -> str:
    return (
        f"⚠️ Je n'ai pas pu écrire à {esc(name)} en privé. "
        "Démarre le bot (/start en privé) puis envoie /monmot pour recevoir ton mot."
    )


NO_SCORES = "Aucun score pour le moment : jouez une partie avec /nouvelle !"
_MEDALS = ("🥇", "🥈", "🥉")


def render_leaderboard(rows: list) -> str:
    """Classement cumulé du groupe, IA comprises (FR-040)."""
    lines = ["🏆 <b>Classement du groupe</b>", ""]
    for rank, row in enumerate(rows, start=1):
        medal = _MEDALS[rank - 1] if rank <= len(_MEDALS) else f"{rank}."
        prefix = f"{AI_PREFIX} " if row.player_id.startswith("ai:") else ""
        parties = f"{row.games_played} partie{'s' if row.games_played > 1 else ''}"
        lines.append(f"{medal} {prefix}{esc(row.name)} — {row.points} pts ({parties})")
    return "\n".join(lines)


RESTART_PENDING = (
    "🔄 Une nouvelle partie va démarrer, patiente un instant (ou /annuler pour arrêter)."
)
SERIES_STOPPED = "🛑 Série terminée. Relancez une partie avec /nouvelle quand vous voulez !"


def restart_countdown(seconds: int) -> str:
    return (
        f"🔄 Nouvelle partie dans {seconds} secondes avec les mêmes joueurs "
        "(le créateur peut taper /annuler pour arrêter)."
    )
