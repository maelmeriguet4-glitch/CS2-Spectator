#!/usr/bin/env python3
"""
Auto-vérification du pipeline d'entraînement CS2CD sur un mini-dataset synthétique.

Ce script ne remplace pas le dataset réel : il vérifie que l'extraction des
caractéristiques, l'étanchéité des splits, l'optimisation du seuil et la
création du bundle fonctionnent de bout en bout, sans artefact de build.

Usage :
    python scripts/selfcheck_train_pipeline.py
"""

import json
import os
import sys
import tempfile
import traceback

import numpy as np
import pandas as pd

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts.index_cs2cd import index_dataset  # noqa: E402
from scripts.train_cs2cd import train_cs2cd_pipeline  # noqa: E402
from src.ml.classifier import NOMS_FEATURES  # noqa: E402


def _make_ticks(match_idx: int, cheater: bool) -> pd.DataFrame:
    n_ticks = 400
    rows = []
    for player_idx in range(2):
        sid = f"Player_{match_idx}_{player_idx}"
        team = 2 if player_idx == 0 else 3
        rng = np.random.default_rng(match_idx * 10 + player_idx)

        if cheater and player_idx == 0:
            yaw = (np.arange(n_ticks) * 120.0) % 360.0 - 180.0  # spin continu
            pitch = rng.normal(10.0, 40.0, n_ticks)  # jitter anti-aim
            airborne = (np.arange(n_ticks) % 2 == 1)  # bhop parfait 1-tick
            speed = rng.normal(280.0, 8.0, n_ticks)
        else:
            yaw = np.cumsum(rng.normal(0.0, 1.5, n_ticks))
            pitch = rng.normal(0.0, 1.5, n_ticks)
            airborne = rng.random(n_ticks) < 0.15
            speed = rng.normal(170.0, 30.0, n_ticks)

        yaw = np.mod(yaw + 180.0, 360.0) - 180.0
        for i in range(n_ticks):
            rows.append({
                "tick": i,
                "steamid": sid,
                "team_num": team,
                "health": 100,
                "X": float(i * 2.0 + player_idx * 50.0),
                "Y": float(i * 0.5),
                "Z": 64.0 + float(i % 3),
                "pitch": float(pitch[i]),
                "yaw": float(yaw[i]),
                "spotted": bool(i % 5 == 0),
                "velocity_X": float(speed[i]),
                "velocity_Y": float(10.0 * np.sin(i / 10.0)),
                "velocity_Z": 0.0,
                "is_airborne": bool(airborne[i]),
                "active_weapon_name": "weapon_ak47",
            })
    return pd.DataFrame(rows)


def _make_events(match_idx: int, cheater: bool) -> dict:
    return {
        "CSstats_info": [{"map": "de_dust2", "server": f"selfcheck_{match_idx}"}],
        "cheaters": [{"steamid": f"Player_{match_idx}_0"}] if cheater else [],
        "weapon_fire": [
            {"tick": t, "user_steamid": f"Player_{match_idx}_0", "weapon": "weapon_ak47"}
            for t in range(20, 380, 5)
        ],
        "player_hurt": [],
        "player_death": [],
    }


def build_dataset(root: str, n_matches: int = 12) -> None:
    for label in ("with_cheater_present", "no_cheater_present"):
        os.makedirs(os.path.join(root, label), exist_ok=True)

    for idx in range(n_matches):
        cheater = idx % 2 == 0
        label = "with_cheater_present" if cheater else "no_cheater_present"
        base = os.path.join(root, label, f"{idx}")
        _make_ticks(idx, cheater).to_parquet(base + ".parquet")
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump(_make_events(idx, cheater), f)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cs2cd_selfcheck_") as tmp:
        dataset_root = os.path.join(tmp, "CS2CD")
        manifest = os.path.join(tmp, "manifest.csv")
        cache = os.path.join(tmp, "features_cache.csv")
        model_out = os.path.join(tmp, "cerveau_vac_cs2cd_selfcheck.pkl")

        build_dataset(dataset_root)
        # example_output_csv=None : ne jamais écrire dans les données du dépôt
        df = index_dataset(
            dataset_root=dataset_root,
            output_csv=manifest,
            random_state=42,
            example_output_csv=None,
        )
        if df is None or df.empty:
            print("[SELFCHECK] Échec : manifeste vide.", file=sys.stderr)
            return 1
        print(f"[SELFCHECK] Manifeste : {len(df)} matchs, splits={df['split'].value_counts().to_dict()}")

        try:
            _run(manifest, model_out, cache)
        except Exception:  # noqa: BLE001 - outil d'auto-vérification : on rapporte tout
            traceback.print_exc()
            return 1
        return 0


def _run(manifest, model_out, cache) -> None:
    """Entraîne le pipeline sur le mini-dataset et contrôle le bundle produit."""
    bundle = train_cs2cd_pipeline(
        manifest_path=manifest,
        output_model=model_out,
        cache_path=cache,
        force_extract=True,
        compare_synthetic=False,
    )

    assert os.path.exists(model_out), "Bundle non écrit sur disque"
    assert list(bundle["noms_features"]) == list(NOMS_FEATURES), "Schéma de features incohérent dans le bundle"
    assert float(bundle["threshold_suspect"]) < float(bundle["threshold_high"]), "Seuils incohérents"

    print("[SELFCHECK] OK : extraction, étanchéité, seuil et bundle validés.")


if __name__ == "__main__":
    sys.exit(main())
