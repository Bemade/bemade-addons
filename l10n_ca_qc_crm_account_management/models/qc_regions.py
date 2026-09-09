# Quebec administrative regions + postal-FSA → region derivation.
#
# This is a CURATED SUBSET, not an authoritative table. A complete, official
# FSA→administrative-region map is ~1,600 forward-sortation areas and is not
# bundled with Odoo. The dict below covers the common Montréal / Montérégie /
# Laurentides / Lanaudière / Laval / Québec-City / Outaouais belt (where most
# Pneumac customers sit); any FSA not explicitly mapped falls back to a coarse
# first-letter heuristic (Canada Post: H = Montréal island region, J = western
# QC suburbs, G = eastern QC). It is correct for mapped FSAs and best-effort
# elsewhere — extend FSA_TO_QC_REGION to improve accuracy.

# The 17 official Quebec administrative regions, codes 01–17.
# Used directly as the Selection definition for the field.
QC_REGIONS = [
    ("01", "Bas-Saint-Laurent"),
    ("02", "Saguenay–Lac-Saint-Jean"),
    ("03", "Capitale-Nationale"),
    ("04", "Mauricie"),
    ("05", "Estrie"),
    ("06", "Montréal"),
    ("07", "Outaouais"),
    ("08", "Abitibi-Témiscamingue"),
    ("09", "Côte-Nord"),
    ("10", "Nord-du-Québec"),
    ("11", "Gaspésie–Îles-de-la-Madeleine"),
    ("12", "Chaudière-Appalaches"),
    ("13", "Laval"),
    ("14", "Lanaudière"),
    ("15", "Laurentides"),
    ("16", "Montérégie"),
    ("17", "Centre-du-Québec"),
]

# Curated FSA → region-code map (subset; improvable).
FSA_TO_QC_REGION = {
    # --- 06 Montréal (island, H1–H4, H8–H9 prefixes) ---
    "H1A": "06", "H1B": "06", "H1C": "06", "H1E": "06", "H1G": "06",
    "H1H": "06", "H1J": "06", "H1K": "06", "H1L": "06", "H1M": "06",
    "H1N": "06", "H1P": "06", "H1R": "06", "H1S": "06", "H1T": "06",
    "H1V": "06", "H1W": "06", "H1X": "06", "H1Y": "06", "H1Z": "06",
    "H2A": "06", "H2B": "06", "H2C": "06", "H2E": "06", "H2G": "06",
    "H2H": "06", "H2J": "06", "H2K": "06", "H2L": "06", "H2M": "06",
    "H2N": "06", "H2P": "06", "H2R": "06", "H2S": "06", "H2T": "06",
    "H2V": "06", "H2W": "06", "H2X": "06", "H2Y": "06", "H2Z": "06",
    "H3A": "06", "H3B": "06", "H3C": "06", "H3E": "06", "H3G": "06",
    "H3H": "06", "H3J": "06", "H3K": "06", "H3L": "06", "H3M": "06",
    "H3N": "06", "H3P": "06", "H3R": "06", "H3S": "06", "H3T": "06",
    "H3V": "06", "H3W": "06", "H3X": "06", "H3Y": "06", "H3Z": "06",
    "H4A": "06", "H4B": "06", "H4C": "06", "H4E": "06", "H4G": "06",
    "H4H": "06", "H4J": "06", "H4K": "06", "H4L": "06", "H4M": "06",
    "H4N": "06", "H4P": "06", "H4R": "06", "H4S": "06", "H4T": "06",
    "H4V": "06", "H4W": "06", "H4X": "06", "H4Y": "06", "H4Z": "06",
    "H8N": "06", "H8P": "06", "H8R": "06", "H8S": "06", "H8T": "06",
    "H8Y": "06", "H8Z": "06", "H9A": "06", "H9B": "06", "H9C": "06",
    "H9E": "06", "H9G": "06", "H9H": "06", "H9J": "06", "H9K": "06",
    "H9P": "06", "H9R": "06", "H9S": "06", "H9W": "06", "H9X": "06",
    # --- 13 Laval (H7 prefix) ---
    "H7A": "13", "H7B": "13", "H7C": "13", "H7E": "13", "H7G": "13",
    "H7H": "13", "H7J": "13", "H7K": "13", "H7L": "13", "H7M": "13",
    "H7N": "13", "H7P": "13", "H7R": "13", "H7S": "13", "H7T": "13",
    "H7V": "13", "H7W": "13", "H7X": "13", "H7Y": "13",
    # --- 16 Montérégie (J3, J4, J5, parts of J0) ---
    "J3A": "16", "J3B": "16", "J3E": "16", "J3G": "16", "J3H": "16",
    "J3L": "16", "J3M": "16", "J3N": "16", "J3P": "16", "J3R": "16",
    "J3T": "16", "J3V": "16", "J3X": "16", "J3Y": "16", "J3Z": "16",
    "J4B": "16", "J4G": "16", "J4H": "16", "J4J": "16", "J4K": "16",
    "J4L": "16", "J4M": "16", "J4N": "16", "J4P": "16", "J4R": "16",
    "J4S": "16", "J4T": "16", "J4V": "16", "J4W": "16", "J4X": "16",
    "J4Y": "16", "J4Z": "16", "J5A": "16", "J5B": "16", "J5C": "16",
    "J5R": "16", "J5V": "16", "J5W": "16", "J5X": "16", "J5Y": "16",
    "J5Z": "16",
    # --- 15 Laurentides (J7, J8 belt north-west) ---
    "J7A": "15", "J7B": "15", "J7C": "15", "J7E": "15", "J7G": "15",
    "J7H": "15", "J7J": "15", "J7N": "15", "J7P": "15", "J7R": "15",
    "J7T": "15", "J7V": "15", "J7W": "15", "J7X": "15", "J7Y": "15",
    "J7Z": "15", "J8A": "15", "J8B": "15", "J8C": "15", "J8E": "15",
    "J8H": "15",
    # --- 14 Lanaudière (J5K–J5T, J6 belt) ---
    "J5K": "14", "J5L": "14", "J5M": "14", "J5T": "14", "J6A": "14",
    "J6E": "14", "J6K": "14", "J6S": "14", "J6T": "14", "J6V": "14",
    "J6W": "14", "J6X": "14", "J6Y": "14", "J6Z": "14", "J7K": "14",
    "J7L": "14",
    # --- 07 Outaouais (J8L–J9, Gatineau) ---
    "J8L": "07", "J8M": "07", "J8N": "07", "J8P": "07", "J8R": "07",
    "J8T": "07", "J8V": "07", "J8X": "07", "J8Y": "07", "J8Z": "07",
    "J9A": "07", "J9B": "07", "J9H": "07", "J9J": "07",
    # --- 03 Capitale-Nationale (Québec City, G1–G3) ---
    "G1A": "03", "G1B": "03", "G1C": "03", "G1E": "03", "G1G": "03",
    "G1H": "03", "G1J": "03", "G1K": "03", "G1L": "03", "G1M": "03",
    "G1N": "03", "G1P": "03", "G1R": "03", "G1S": "03", "G1T": "03",
    "G1V": "03", "G1W": "03", "G1X": "03", "G1Y": "03", "G2A": "03",
    "G2B": "03", "G2C": "03", "G2E": "03", "G2G": "03", "G2J": "03",
    "G2K": "03", "G2L": "03", "G2M": "03", "G2N": "03", "G3A": "03",
    "G3B": "03", "G3C": "03", "G3E": "03", "G3G": "03", "G3H": "03",
    "G3J": "03", "G3K": "03",
    # --- 12 Chaudière-Appalaches (G5R, G6, parts of Lévis) ---
    "G6V": "12", "G6W": "12", "G6X": "12", "G6Y": "12", "G6Z": "12",
    "G6C": "12", "G6E": "12", "G6G": "12", "G6H": "12", "G6J": "12",
    "G6K": "12",
    # --- 04 Mauricie (G8, G9 — Trois-Rivières / Shawinigan) ---
    "G8P": "04", "G8T": "04", "G8V": "04", "G8W": "04", "G8Y": "04",
    "G8Z": "04", "G9A": "04", "G9B": "04", "G9C": "04", "G9N": "04",
    "G9P": "04", "G9R": "04", "G9T": "04",
    # --- 05 Estrie (J1 — Sherbrooke) ---
    "J1A": "05", "J1C": "05", "J1E": "05", "J1G": "05", "J1H": "05",
    "J1J": "05", "J1K": "05", "J1L": "05", "J1M": "05", "J1N": "05",
    "J1R": "05", "J1S": "05", "J1T": "05", "J1X": "05", "J1Z": "05",
    "J2A": "05",
    # --- 01 Bas-Saint-Laurent (G5L Rimouski) ---
    "G5L": "01", "G5M": "01", "G5N": "01",
    # --- 02 Saguenay–Lac-Saint-Jean (G7) ---
    "G7A": "02", "G7B": "02", "G7G": "02", "G7H": "02", "G7J": "02",
    "G7K": "02", "G7N": "02", "G7P": "02", "G7S": "02", "G7T": "02",
    "G7X": "02", "G7Y": "02",
}

# Coarse fallback by first letter of the FSA when the exact FSA isn't mapped.
# Canada Post broadly allocates: H = Montréal island region, J = western QC
# suburbs (Montérégie/Laurentides belt), G = eastern QC (Québec-City region).
_FIRST_LETTER_FALLBACK = {
    "H": "06",  # Montréal island (H7/Laval is covered explicitly above)
    "J": "16",  # western QC default → Montérégie
    "G": "03",  # eastern QC default → Capitale-Nationale
}

# Valid Quebec postal-code first letters (G, H, J). Codes outside these are
# not in Quebec and must not be assigned a QC region.
_QC_FIRST_LETTERS = frozenset(_FIRST_LETTER_FALLBACK)


def fsa_to_region(zip_str):
    """Derive a QC administrative-region code (01–17) from a postal code.

    Pure helper (no ORM) so it is directly unit-testable.

    The first three characters of a Canadian postal code form the FSA
    (forward sortation area), e.g. ``"J7K 3C5"`` → ``"J7K"``. We normalise
    (strip, upper, drop internal spaces), look the FSA up in the curated
    ``FSA_TO_QC_REGION`` map, and fall back to a coarse first-letter heuristic
    for unmapped QC FSAs. Non-QC or unrecognised input returns ``False``.

    :param zip_str: a postal code string (any casing/spacing) or falsy value.
    :return: a region code string ("01".."17") or ``False``.
    """
    if not zip_str:
        return False
    normalised = "".join(zip_str.split()).upper()
    fsa = normalised[:3]
    if len(fsa) < 3:
        return False
    region = FSA_TO_QC_REGION.get(fsa)
    if region:
        return region
    # Fall back to the coarse first-letter heuristic for QC postal codes only.
    first_letter = fsa[0]
    if first_letter in _QC_FIRST_LETTERS:
        return _FIRST_LETTER_FALLBACK[first_letter]
    return False
