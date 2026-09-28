"""
Correspondence tables between landcover and damage functions classifications.
"""

from typing import TypedDict

from seiche.utils_enum import Landcover


class _Map(TypedDict, total=False):
    """
    Per-landcover mapping tables.
    """

    map_jrc: dict[int, list[float]]
    map_floodam: dict[int, str]
    column_for_jrc: str


MAPS: dict[Landcover, _Map] = {
    Landcover.oso23: {
        # key: landcover code, value: (h, c, i, t, r, a)
        "map_jrc": {
            # 1. Urbain dense
            1: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 2. Urbain diffus
            2: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 3. Zone industrielle & commerciale
            3: [0.0, 0.5, 0.5, 0.0, 0.0, 0.0],
            # 4. Routes
            4: [0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            # 5. Oléagineux d'hiver
            5: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 6. Céréales à paille
            6: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 7. Protéagineux de printemps
            7: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 8. Soja
            8: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 9. Tournesol
            9: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 10. Mais
            10: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 11. Riz
            11: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 12. Tubercules/racines
            12: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 13. Prairies (voir p88 rapport jrc)
            13: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 14. Vergers
            14: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 15. Vignes
            15: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 16. Forêts de feuillus
            16: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 17. Fôrets de conifères
            17: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 18. Pelouses
            18: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 19. Landes
            19: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 20. Surfaces minérales
            20: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 21. Plages et dunes
            21: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 22. Glaciers et neiges éternelles
            22: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 23. Eau
            23: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        },
    },
    Landcover.esawc: {
        # key: landcover code, value: (h, c, i, t, r, a)
        "map_jrc": {
            # 10. Tree Cover
            10: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 20. Shrubland
            20: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 30. Grassland
            30: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 40. Cropland
            40: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 50. Built-up
            50: [0.8, 0.1, 0.1, 0.0, 0.0, 0.0],
            # 60. Bare / sparse vegetation
            60: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 70. Snow and ice
            70: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 80. Permanenet water bodies
            80: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 90. Herbaceous wetland
            90: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 95. Mangroves
            95: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 100. Moss and lichen
            100: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        },
    },
    Landcover.rpg: {
        # key: landcover code, value: (h, c, i, t, r, a)
        # BASED ON CODE_GROUPE (!= CODE_CULTURE)
        "map_jrc": {
            # 1. Blé tendre
            1: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 2. Maïs grain et ensilage
            2: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 3. Orge
            3: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 4. Autres céréales
            4: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 5. Colza
            5: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 6. Tournesol
            6: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 7. Autres oléagineux
            7: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 8. Protéagineux
            8: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 9. Plates à fibre
            9: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 10. ???
            10: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 11. Gel
            11: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 12. ???
            12: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 13. ???
            13: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 14. Riz
            14: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 15. Légumineuses à grain
            15: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 16. Fourrage
            16: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 17. Estives et landes
            17: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 18. Prairies permanentes
            18: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 19. Prairies temporaires
            19: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 20. Vergers
            20: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 21. Vignes
            21: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 22. Fruits à coques
            22: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 23. Oliviers
            23: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 24. Autres cultures industrielles
            24: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 25. Légumes ou fleurs
            25: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 26. Canne à sucre
            26: [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            # 27. ???
            27: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            # 28. Divers
            28: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        },
        # Floodam agricultural damage function classes, keyed by RPG CODE_GROUPE
        # (!= CODE_CULTURE).
        # RPG : https://geoservices.ign.fr/sites/default/files/2021-11/REF_CULTURES_GROUPES_CULTURES_2020.csv
        "map_floodam": {
            1: "wheat",
            2: "corn",
            3: "barley",
            4: "otherCereals",
            5: "colza",
            6: "sunflower",
            7: "otherOleaginous",
            24: "otherIndustrial",
            20: "orchard",
            21: "grapevine",
            25: "flowerVegetables",
            16: "fodder",
            18: "permanentGrasslands",
            19: "temporaryGrasslands",
        },
        "column_for_jrc": "CODE_GROUP",
    },
}
