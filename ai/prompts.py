"""Prompts des agents IA, en français et centralisés (section 4 du brief).

Ces fonctions ne reçoivent qu'une `PublicView` : elles ne peuvent donc jamais exposer le rôle de
l'IA ni les mots ou rôles des autres joueurs (principe IV).
"""

from game.models import PublicView

# Personnalité de chaque agent : appliquée au style des indices uniquement (section 4.1)
PERSONAS: dict[str, str] = {
    "ai:zendaya": "Posée et analytique : tes mots sont subtils et bien réfléchis.",
    "ai:kendall": "Joueuse et un peu taquine : tes mots sont imagés et pleins d'esprit.",
    "ai:diva": (
        "Expressive et spontanée : tes mots sont tirés de la vie quotidienne "
        "(situations, objets, habitudes de tous les jours)."
    ),
}
DEFAULT_PERSONA = "Naturelle et discrète."

MAX_WORDS = 1  # un seul mot par description

SYSTEM_TEMPLATE = """Tu joues à Undercover, un jeu de déduction entre amis francophones \
(Cameroun), sur Telegram. Tu es {name}.

RÈGLES : chaque joueur reçoit un mot en secret. La plupart des joueurs (les Civils) ont le même \
mot. Un ou deux joueurs (les Undercovers) ont un mot proche mais différent. Personne ne connaît \
son propre rôle : on le déduit en écoutant les mots des autres. Chaque joueur dit UN SEUL MOT à \
son tour pour décrire son mot, sans jamais prononcer son mot ni un mot de la même famille. On \
fait 3 tours de description (chacun dit donc 3 mots différents), puis tout le monde vote pour \
désigner un suspect.

TA PERSONNALITÉ (style de tes mots uniquement) : {persona}

STRATÉGIE :
- Compare ton mot avec les mots dits par les autres joueurs. Si leurs mots ne collent pas au tien, \
tu es probablement Undercover : reste alors vague et fonds-toi dans la majorité, sans te trahir.
- Si tu penses être Civil, dis des mots assez précis pour être reconnu par les autres Civils, sans \
rendre ton mot trop facile à deviner.
- Pour voter, vise le joueur dont les mots collent le moins au mot que tu estimes être celui de \
la majorité.

FORMAT : réponds UNIQUEMENT avec un objet JSON strict, sans texte autour, en français."""


def system_prompt(persona_id: str, name: str) -> str:
    return SYSTEM_TEMPLATE.format(name=name, persona=PERSONAS.get(persona_id, DEFAULT_PERSONA))


def _history(view: PublicView) -> str:
    lines = [f"Ton mot secret : « {view.own_word} »", ""]
    lines.append("Joueurs encore en jeu : " + ", ".join(name for _, name in view.alive_players))
    if view.descriptions:
        lines.append("")
        lines.append("Mots dits jusqu'ici :")
        for rnd, sub, name, text in view.descriptions:
            lines.append(f"- Manche {rnd}, tour {sub}, {name} : {text}")
    if view.votes:
        lines.append("")
        lines.append("Votes précédents :")
        for rnd, voter, target in view.votes:
            lines.append(f"- Manche {rnd} : {voter} a voté contre {target}")
    if view.eliminations:
        lines.append("")
        lines.append("Éliminés (rôle révélé) :")
        for rnd, name, role in view.eliminations:
            lines.append(f"- Manche {rnd} : {name} ({_role_fr(role)})")
    return "\n".join(lines)


def _role_fr(role: str) -> str:
    return {"civilian": "Civil", "undercover": "Undercover"}.get(role, role)


def describe_prompt(view: PublicView, hint: str | None = None) -> str:
    text = _history(view)
    text += (
        "\n\nÀ TOI : dis UN SEUL MOT (pas une phrase) qui décrit ton mot, sans utiliser ton mot ni "
        "un mot de la même famille, et sans répéter un mot déjà dit dans la partie."
        '\nRéponds en JSON : {"description": "..."}'
    )
    if hint:
        text += f"\n\nATTENTION : ta proposition précédente a été refusée ({hint}). Change-la."
    return text


def vote_prompt(view: PublicView) -> str:
    others = [name for pid, name in view.alive_players if pid != view.viewer_id]
    return (
        _history(view)
        + "\n\nÀ TOI DE VOTER : choisis le joueur à éliminer parmi : "
        + ", ".join(others)
        + ".\nRéponds en JSON avec le nom EXACT du joueur : "
        + '{"vote": "<nom exact>"}'
    )
