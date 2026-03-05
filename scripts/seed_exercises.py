"""Seed script — Bibliothèque d'exercices standard FitProgress.

Usage :
    # Avec Docker Compose (recommandé)
    docker compose exec app python scripts/seed_exercises.py

    # En local (venv activé, depuis la racine du projet)
    python scripts/seed_exercises.py

Idempotent : vérifie si des exercices standard existent déjà avant d'insérer.
Résultat   : 58 exercices couvrant les 11 catégories du modèle ExerciseCategory.
"""
from __future__ import annotations

import asyncio
import os
import sys

# ── Résolution du path racine ──────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
# Import ALL models so SQLAlchemy can resolve all cross-model relationships
import app.users.models  # noqa: F401
import app.exercises.models  # noqa: F401
import app.programs.models  # noqa: F401
import app.workouts.models  # noqa: F401
import app.gamification.models  # noqa: F401
import app.progression.models  # noqa: F401
import app.notifications.models  # noqa: F401
from app.exercises.models import Exercise, ExerciseCategory

settings = get_settings()

# ===========================================================================
# Bibliothèque d'exercices standard — 58 exercices / 11 catégories
# ===========================================================================
STANDARD_EXERCISES: list[dict] = [

    # ── COMPOUND_CHEST (5) ─────────────────────────────────────────────────
    {
        "name": "Développé couché barre",
        "category": ExerciseCategory.COMPOUND_CHEST,
        "muscle_group": "Pectoraux",
        "description": (
            "Exercice de base pour les pectoraux. Allongé sur banc plat, "
            "prise légèrement plus large que les épaules. Descendre la barre "
            "jusqu'à effleurer le sternum, pousser en contractant les pectoraux."
        ),
    },
    {
        "name": "Développé incliné haltères",
        "category": ExerciseCategory.COMPOUND_CHEST,
        "muscle_group": "Pectoraux supérieurs",
        "description": (
            "Développé sur banc incliné à 30-45°. Cible le chef claviculaire "
            "des pectoraux. Amplitude complète, coudes à 45° du corps."
        ),
    },
    {
        "name": "Développé couché haltères",
        "category": ExerciseCategory.COMPOUND_CHEST,
        "muscle_group": "Pectoraux",
        "description": (
            "Version haltères du développé couché. Amplitude supérieure à la barre, "
            "recrutement accru des stabilisateurs. Descendre jusqu'à étirement maximal."
        ),
    },
    {
        "name": "Pompes (Push-ups)",
        "category": ExerciseCategory.COMPOUND_CHEST,
        "muscle_group": "Pectoraux / Triceps",
        "description": (
            "Exercice au poids du corps fondamental. Mains légèrement plus larges "
            "que les épaules. Nombreuses variantes : déclinées, surélevées, archer."
        ),
    },
    {
        "name": "Dips (Pectoraux)",
        "category": ExerciseCategory.COMPOUND_CHEST,
        "muscle_group": "Pectoraux",
        "description": (
            "Pompes aux barres parallèles, torse incliné vers l'avant pour maximiser "
            "le recrutement pectoral. Descendre jusqu'à 90° de flexion du coude."
        ),
    },

    # ── ISOLATION_CHEST (4) ────────────────────────────────────────────────
    {
        "name": "Écarté haltères à plat",
        "category": ExerciseCategory.ISOLATION_CHEST,
        "muscle_group": "Pectoraux",
        "description": (
            "Mouvement d'isolation en adduction horizontale. Coudes légèrement "
            "fléchis, descente jusqu'à l'étirement maximal des pectoraux."
        ),
    },
    {
        "name": "Écarté incliné haltères",
        "category": ExerciseCategory.ISOLATION_CHEST,
        "muscle_group": "Pectoraux supérieurs",
        "description": (
            "Écarté sur banc incliné à 30°. Cible le chef supérieur des pectoraux. "
            "Contracter au sommet sans bloquer les coudes."
        ),
    },
    {
        "name": "Câble croisé (Cable Crossover)",
        "category": ExerciseCategory.ISOLATION_CHEST,
        "muscle_group": "Pectoraux",
        "description": (
            "Croisé câble depuis poulies hautes ou basses. Tension constante "
            "tout au long du mouvement. Excellent pour le finisher de séance."
        ),
    },
    {
        "name": "Pec Deck (Machine Butterfly)",
        "category": ExerciseCategory.ISOLATION_CHEST,
        "muscle_group": "Pectoraux",
        "description": (
            "Machine à papillon. Isolation complète des pectoraux sans sollicitation "
            "des stabilisateurs. Idéal pour débutants et séries d'isolation."
        ),
    },

    # ── SHOULDERS (6) ──────────────────────────────────────────────────────
    {
        "name": "Développé militaire barre",
        "category": ExerciseCategory.SHOULDERS,
        "muscle_group": "Épaules",
        "description": (
            "Exercice de force de base pour les épaules. Debout ou assis, "
            "barre poussée verticalement au-dessus de la tête, bras tendus."
        ),
    },
    {
        "name": "Développé militaire haltères",
        "category": ExerciseCategory.SHOULDERS,
        "muscle_group": "Épaules",
        "description": (
            "Développé vertical aux haltères assis. Amplitude légèrement supérieure "
            "à la barre, travail unilatéral équilibrant les deux côtés."
        ),
    },
    {
        "name": "Arnold Press",
        "category": ExerciseCategory.SHOULDERS,
        "muscle_group": "Épaules",
        "description": (
            "Développé avec rotation des haltères de supination vers pronation. "
            "Travaille les 3 chefs du deltoïde (antérieur, moyen, postérieur)."
        ),
    },
    {
        "name": "Élévation latérale haltères",
        "category": ExerciseCategory.SHOULDERS,
        "muscle_group": "Deltoïde moyen",
        "description": (
            "Isolation du faisceau moyen du deltoïde. Abduction à hauteur des "
            "épaules, légère flexion du coude, mouvement lent et contrôlé."
        ),
    },
    {
        "name": "Élévation frontale haltères",
        "category": ExerciseCategory.SHOULDERS,
        "muscle_group": "Deltoïde antérieur",
        "description": (
            "Cible le faisceau antérieur du deltoïde. Alternée ou simultanée, "
            "montée à hauteur des yeux, descente contrôlée."
        ),
    },
    {
        "name": "Face Pull",
        "category": ExerciseCategory.SHOULDERS,
        "muscle_group": "Épaules / Trapèzes",
        "description": (
            "Tirage visage à la poulie haute avec corde. Essentiel pour la santé "
            "des rotateurs et le développement des trapèzes inférieurs et rhomboïdes."
        ),
    },

    # ── TRICEPS (4) ────────────────────────────────────────────────────────
    {
        "name": "Extension triceps câble (Pushdown)",
        "category": ExerciseCategory.TRICEPS,
        "muscle_group": "Triceps",
        "description": (
            "Isolation des triceps à la poulie haute avec barre droite ou corde. "
            "Coudes fixes et collés au corps, extension complète à chaque répétition."
        ),
    },
    {
        "name": "Barre front (Skull Crusher)",
        "category": ExerciseCategory.TRICEPS,
        "muscle_group": "Triceps",
        "description": (
            "Extension couché avec EZ-bar ou haltères. Excellent pour le chef long "
            "des triceps. Descendre la barre vers le front, coudes stables."
        ),
    },
    {
        "name": "Extension triceps au-dessus de la tête",
        "category": ExerciseCategory.TRICEPS,
        "muscle_group": "Triceps",
        "description": (
            "Haltère ou câble derrière la tête, bras tendus vers le haut. "
            "Étirement maximal du chef long. Coudes pointés vers le plafond."
        ),
    },
    {
        "name": "Développé couché prise serrée",
        "category": ExerciseCategory.TRICEPS,
        "muscle_group": "Triceps",
        "description": (
            "Variante du développé couché, prise à largeur d'épaules. "
            "Coudes restent proches du corps, focus maximum sur les triceps."
        ),
    },

    # ── COMPOUND_BACK (7) ──────────────────────────────────────────────────
    {
        "name": "Soulevé de terre (Deadlift)",
        "category": ExerciseCategory.COMPOUND_BACK,
        "muscle_group": "Dos / Ischios / Fessiers",
        "description": (
            "Le roi des exercices de force. Travaille l'ensemble de la chaîne "
            "postérieure. Dos droit, barre près du corps, poussée par les jambes."
        ),
    },
    {
        "name": "Rowing barre (Barbell Row)",
        "category": ExerciseCategory.COMPOUND_BACK,
        "muscle_group": "Dos",
        "description": (
            "Tirage horizontal barre pour la masse et l'épaisseur du dos. "
            "Torse incliné à 45°, tirer vers le bas du sternum, squeeze en haut."
        ),
    },
    {
        "name": "Tractions (Pull-ups)",
        "category": ExerciseCategory.COMPOUND_BACK,
        "muscle_group": "Dos / Biceps",
        "description": (
            "Exercice au poids du corps par excellence pour la largeur du dos. "
            "Prise pronation plus large que les épaules, menton au-dessus de la barre."
        ),
    },
    {
        "name": "Traction prise supinée (Chin-ups)",
        "category": ExerciseCategory.COMPOUND_BACK,
        "muscle_group": "Dos / Biceps",
        "description": (
            "Traction prise supination, largeur d'épaules. Plus de participation "
            "des biceps que les pull-ups. Plus accessible pour les débutants."
        ),
    },
    {
        "name": "Tirage vertical (Lat Pulldown)",
        "category": ExerciseCategory.COMPOUND_BACK,
        "muscle_group": "Grand dorsal",
        "description": (
            "Poulie haute, barre tirée vers le haut de la poitrine. Alternative "
            "aux tractions, permet la progression de charge. Prise large."
        ),
    },
    {
        "name": "Rowing assis poulie (Seated Cable Row)",
        "category": ExerciseCategory.COMPOUND_BACK,
        "muscle_group": "Dos",
        "description": (
            "Tirage horizontal à la poulie basse avec poignée neutre. "
            "Épaisseur du dos, rhomboïdes et trapèzes moyens. Garder le dos droit."
        ),
    },
    {
        "name": "Rowing T-bar",
        "category": ExerciseCategory.COMPOUND_BACK,
        "muscle_group": "Dos",
        "description": (
            "Rowing avec barre en T ou landmine. Permet une charge lourde "
            "pour le développement de la masse du dos. Torse horizontal."
        ),
    },

    # ── BICEPS (5) ─────────────────────────────────────────────────────────
    {
        "name": "Curl barre (Barbell Curl)",
        "category": ExerciseCategory.BICEPS,
        "muscle_group": "Biceps",
        "description": (
            "Exercice de base pour les biceps. Barre droite ou EZ, "
            "flexion complète du coude, descente complète sans balancer le dos."
        ),
    },
    {
        "name": "Curl haltères alternés",
        "category": ExerciseCategory.BICEPS,
        "muscle_group": "Biceps",
        "description": (
            "Curl unilatéral avec supination complète en montant. Maximise "
            "le pic bicipital. Alterner les bras ou travailler simultanément."
        ),
    },
    {
        "name": "Curl marteau (Hammer Curl)",
        "category": ExerciseCategory.BICEPS,
        "muscle_group": "Biceps / Brachial",
        "description": (
            "Prise neutre (pouce vers le haut), cible le brachial et le long "
            "supinateur. Excellent pour l'épaisseur du bras et l'avant-bras."
        ),
    },
    {
        "name": "Curl concentré",
        "category": ExerciseCategory.BICEPS,
        "muscle_group": "Biceps",
        "description": (
            "Isolation maximale du biceps assis, coude appuyé contre la cuisse intérieure. "
            "Mouvement strict, supination complète en haut."
        ),
    },
    {
        "name": "Curl incliné haltères",
        "category": ExerciseCategory.BICEPS,
        "muscle_group": "Biceps",
        "description": (
            "Sur banc incliné à 45-60°, étirement maximal du chef long à chaque répétition. "
            "Très efficace pour le développement du pic bicipital."
        ),
    },

    # ── ISOLATION_BACK (3) ─────────────────────────────────────────────────
    {
        "name": "Tirage bras tendus (Straight-Arm Pulldown)",
        "category": ExerciseCategory.ISOLATION_BACK,
        "muscle_group": "Grand dorsal",
        "description": (
            "Poulie haute, bras tendus tirés vers les hanches. Isolation du grand "
            "dorsal sans implication des biceps. Excellent pour la connexion neuromusculaire."
        ),
    },
    {
        "name": "Rowing unilatéral haltère",
        "category": ExerciseCategory.ISOLATION_BACK,
        "muscle_group": "Dos",
        "description": (
            "Tirage unilatéral haltère appuyé sur banc, une main et un genou. "
            "Grande amplitude de mouvement, focus musculaire précis sur chaque côté."
        ),
    },
    {
        "name": "Pull-over haltère",
        "category": ExerciseCategory.ISOLATION_BACK,
        "muscle_group": "Grand dorsal / Pectoraux",
        "description": (
            "Allongé transversalement sur banc, haltère tenu à bout de bras au-dessus "
            "de la poitrine. Arc vers l'arrière, étirement maximal du grand dorsal."
        ),
    },

    # ── COMPOUND_LEGS (6) ──────────────────────────────────────────────────
    {
        "name": "Squat barre (Barbell Squat)",
        "category": ExerciseCategory.COMPOUND_LEGS,
        "muscle_group": "Jambes",
        "description": (
            "Le roi des exercices pour le bas du corps. Barre sur les trapèzes, "
            "descente jusqu'en bas, quadriceps, ischios et fessiers sollicités."
        ),
    },
    {
        "name": "Presse à cuisses (Leg Press)",
        "category": ExerciseCategory.COMPOUND_LEGS,
        "muscle_group": "Jambes",
        "description": (
            "Machine multiaxiale, alternative sécurisée au squat. Permet de charger "
            "lourd sans contrainte lombaire. Placement des pieds variable."
        ),
    },
    {
        "name": "Soulevé de terre roumain (RDL)",
        "category": ExerciseCategory.COMPOUND_LEGS,
        "muscle_group": "Ischios / Fessiers",
        "description": (
            "Jambes quasi tendues, descente contrôlée de la barre le long des tibias. "
            "Étirement maximal des ischios. Essentiel pour les fessiers."
        ),
    },
    {
        "name": "Fente bulgare (Bulgarian Split Squat)",
        "category": ExerciseCategory.COMPOUND_LEGS,
        "muscle_group": "Quadriceps / Fessiers",
        "description": (
            "Exercice unilatéral, pied arrière surélevé sur banc. Excellent pour "
            "les quadriceps et corriger les déséquilibres gauche/droite."
        ),
    },
    {
        "name": "Hack Squat",
        "category": ExerciseCategory.COMPOUND_LEGS,
        "muscle_group": "Quadriceps",
        "description": (
            "Machine hack squat, position fixe guidée. Isole les quadriceps sans "
            "stress lombaire. Pieds bas sur la plateforme = plus de quadriceps."
        ),
    },
    {
        "name": "Hip Thrust barre",
        "category": ExerciseCategory.COMPOUND_LEGS,
        "muscle_group": "Fessiers",
        "description": (
            "Dos appuyé sur banc, barre sur les hanches. Poussée verticale des hanches. "
            "Le meilleur exercice pour l'activation et le développement des fessiers."
        ),
    },

    # ── ISOLATION_LEGS (5) ─────────────────────────────────────────────────
    {
        "name": "Extension de jambes (Leg Extension)",
        "category": ExerciseCategory.ISOLATION_LEGS,
        "muscle_group": "Quadriceps",
        "description": (
            "Machine d'isolation des quadriceps. Extension complète du genou "
            "avec contraction isométrique au sommet. Éviter en cas de douleur au genou."
        ),
    },
    {
        "name": "Curl couché (Lying Leg Curl)",
        "category": ExerciseCategory.ISOLATION_LEGS,
        "muscle_group": "Ischios",
        "description": (
            "Machine de curl en décubitus ventral. Isolation des ischios-jambiers. "
            "Contraction maximale en haut, descente lente et contrôlée."
        ),
    },
    {
        "name": "Curl assis (Seated Leg Curl)",
        "category": ExerciseCategory.ISOLATION_LEGS,
        "muscle_group": "Ischios",
        "description": (
            "Variante assise du curl jambes. Active davantage le chef court "
            "du biceps fémoral. Pied en dorsiflexion pour plus d'activation."
        ),
    },
    {
        "name": "Mollets debout (Standing Calf Raise)",
        "category": ExerciseCategory.ISOLATION_LEGS,
        "muscle_group": "Gastrocnémien",
        "description": (
            "Jambe tendue, isolation du gastrocnémien. Montée complète sur pointe, "
            "descente complète pour l'étirement. Amplitude maximale indispensable."
        ),
    },
    {
        "name": "Mollets assis (Seated Calf Raise)",
        "category": ExerciseCategory.ISOLATION_LEGS,
        "muscle_group": "Soléaire",
        "description": (
            "Jambe fléchie à 90°, isole le soléaire (muscle profond). "
            "Complémentaire aux mollets debout pour un développement complet."
        ),
    },

    # ── CORE (6) ───────────────────────────────────────────────────────────
    {
        "name": "Planche (Plank)",
        "category": ExerciseCategory.CORE,
        "muscle_group": "Abdominaux",
        "description": (
            "Exercice isométrique fondamental pour la stabilité du core. "
            "Appui sur avant-bras, corps aligné, hanches ni trop hautes ni trop basses."
        ),
    },
    {
        "name": "Crunch",
        "category": ExerciseCategory.CORE,
        "muscle_group": "Abdominaux",
        "description": (
            "Flexion du tronc, isolation du droit abdominal. Mouvement court, "
            "mains derrière la tête sans tirer sur la nuque."
        ),
    },
    {
        "name": "Russian Twist",
        "category": ExerciseCategory.CORE,
        "muscle_group": "Obliques",
        "description": (
            "Rotation du tronc assis, pieds levés. Cible les obliques. "
            "Avec médecine-ball ou haltère pour progresser en charge."
        ),
    },
    {
        "name": "Relevé de jambes suspendu",
        "category": ExerciseCategory.CORE,
        "muscle_group": "Abdominaux inférieurs",
        "description": (
            "Pendu à une barre, montée des jambes tendues ou fléchies. "
            "Très efficace pour les abdominaux inférieurs et le psoas."
        ),
    },
    {
        "name": "Crunch poulie haute (Cable Crunch)",
        "category": ExerciseCategory.CORE,
        "muscle_group": "Abdominaux",
        "description": (
            "Agenouillé devant poulie haute avec corde. Flexion du tronc vers "
            "les genoux. Permet une progression de charge contrairement aux crunchs."
        ),
    },
    {
        "name": "Roue abdominale (Ab Wheel Rollout)",
        "category": ExerciseCategory.CORE,
        "muscle_group": "Abdominaux",
        "description": (
            "Roulement vers l'avant avec roue abdominale, extension maximale du corps. "
            "Un des exercices les plus exigeants pour le core. Commencer à genoux."
        ),
    },

    # ── CARDIO (5) ─────────────────────────────────────────────────────────
    {
        "name": "Course sur tapis roulant",
        "category": ExerciseCategory.CARDIO,
        "muscle_group": "Cardio",
        "description": (
            "Cardio à intensité variable : marche (3-5 km/h), jogging (8-12 km/h), "
            "sprint HIIT (15+ km/h). Contrôle de vitesse et d'inclinaison."
        ),
    },
    {
        "name": "Vélo stationnaire",
        "category": ExerciseCategory.CARDIO,
        "muscle_group": "Cardio",
        "description": (
            "Cardio à faible impact articulaire. Idéal en récupération active "
            "ou HIIT. Résistance variable pour simuler côtes et sprints."
        ),
    },
    {
        "name": "Rameur (Rowing Machine)",
        "category": ExerciseCategory.CARDIO,
        "muscle_group": "Cardio / Full Body",
        "description": (
            "Cardio full-body à faible impact. Sollicite dos, jambes, bras "
            "simultanément. Technique : 60% jambes, 20% dos, 20% bras."
        ),
    },
    {
        "name": "Corde à sauter (Jump Rope)",
        "category": ExerciseCategory.CARDIO,
        "muscle_group": "Cardio",
        "description": (
            "Cardio haute intensité. Développe la coordination, la vitesse des pieds "
            "et l'endurance cardiovasculaire. Brûle environ 10-15 kcal/min."
        ),
    },
    {
        "name": "Elliptique",
        "category": ExerciseCategory.CARDIO,
        "muscle_group": "Cardio",
        "description": (
            "Cardio sans impact articulaire. Mouvement fluide qui protège genoux "
            "et hanches. Idéal en phase de récupération ou post-blessure."
        ),
    },
]

# ===========================================================================
# Seed
# ===========================================================================

async def seed() -> None:
    print("🔌  Connexion à la base de données...")
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        # ── Vérification idempotente ──────────────────────────────────────
        result = await db.execute(
            select(func.count(Exercise.id)).where(
                Exercise.is_custom.is_(False),
                Exercise.is_deleted.is_(False),
            )
        )
        existing_count = result.scalar_one()

        if existing_count > 0:
            print(
                f"✅  Bibliothèque déjà seedée — {existing_count} exercices standard "
                f"présents. Rien à faire."
            )
            await engine.dispose()
            return

        # ── Insertion ────────────────────────────────────────────────────
        print(f"🌱  Insertion de {len(STANDARD_EXERCISES)} exercices...")

        exercises = [
            Exercise(
                name=ex["name"],
                category=ex["category"],
                muscle_group=ex["muscle_group"],
                description=ex["description"],
                is_custom=False,
                created_by_user_id=None,
            )
            for ex in STANDARD_EXERCISES
        ]
        db.add_all(exercises)
        await db.commit()

        # ── Vérification ──────────────────────────────────────────────────
        result = await db.execute(
            select(func.count(Exercise.id)).where(
                Exercise.is_custom.is_(False),
                Exercise.is_deleted.is_(False),
            )
        )
        inserted = result.scalar_one()

    await engine.dispose()

    categories = {ex["category"].value for ex in STANDARD_EXERCISES}
    print(f"\n✅  {inserted} exercices insérés avec succès.")
    print(f"📋  Catégories couvertes ({len(categories)}) :")
    for cat in sorted(categories):
        count = sum(1 for ex in STANDARD_EXERCISES if ex["category"].value == cat)
        print(f"    • {cat:<25} {count} exercices")
    print("\n🚀  La bibliothèque est prête. L'application mobile peut afficher les exercices.")


if __name__ == "__main__":
    asyncio.run(seed())
