# ============================================
# br18_data.py
# Indeholder forkortet tekst og mapping for BR18
# ============================================

BR18_TEXT = {
    1: {
        "title": "Anvendelseskategori 1",
        "description": "Bygningsafsnit uden overnatning, hvor personer kender flugtvejene og kan evakuere på egen hånd.",
        "examples": [
            "Kontorer", "Industri- og lagerbygninger", "Garager", "Teknikrum"
        ]
    },
    2: {
        "title": "Anvendelseskategori 2",
        "description": "Bygningsafsnit uden overnatning, hvor personer ikke kender flugtvejene, men kan evakuere selv. Højst 50 personer.",
        "examples": [
            "Undervisningslokaler", "Mindre butikker", "Dagcentre for selvhjulpne"
        ]
    },
    3: {
        "title": "Anvendelseskategori 3",
        "description": "Bygningsafsnit uden overnatning, hvor personer ikke kender flugtvejene og hvor der kan være mere end 50 personer.",
        "examples": [
            "Forsamlingslokaler", "Biografer", "Restauranter", "Kirker"
        ]
    },
    4: {
        "title": "Anvendelseskategori 4",
        "description": "Bygningsafsnit med overnatning, hvor personer er selvhjulpne og kender flugtvejene.",
        "examples": [
            "Boliger", "Rækkehuse", "Sommerhuse", "Kollegier"
        ]
    },
    5: {
        "title": "Anvendelseskategori 5",
        "description": "Bygningsafsnit med overnatning, hvor personer er selvhjulpne, men ikke nødvendigvis kender flugtvejene.",
        "examples": [
            "Hoteller", "Vandrehjem", "Pensionater", "Efterskoler"
        ]
    },
    6: {
        "title": "Anvendelseskategori 6",
        "description": "Bygningsafsnit hvor personer ikke er selvhjulpne og har brug for assistance ved evakuering.",
        "examples": [
            "Hospitaler", "Plejehjem", "Fængsler", "Institutioner"
        ]
    }
}


def get_category_info(cat_num: int):
    """Returnerer titel, beskrivelse og eksempler for en given kategori"""
    return BR18_TEXT.get(cat_num, {
        "title": "Ukendt kategori",
        "description": "Der findes ingen beskrivelse.",
        "examples": []
    })
