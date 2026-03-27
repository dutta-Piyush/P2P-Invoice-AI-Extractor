"""
Commodity catalog: centralizes all commodity categories, groups, and helper functions.
"""

from typing import Dict, List, Tuple

# (Category, Group Name) -> Group ID
_COMMODITY_IDS: Dict[Tuple[str, str], str] = {
    ("Facility Management", "Electrical Engineering"): "011",
    ("Facility Management", "Facility Management Services"): "012",
    ("Facility Management", "Security"): "013",
    ("Facility Management", "Renovations"): "014",
    ("Facility Management", "Office Equipment"): "015",
    ("Facility Management", "Energy Management"): "016",
    ("Facility Management", "Maintenance"): "017",
    ("Facility Management", "Cafeteria and Kitchenettes"): "018",
    ("Facility Management", "Cleaning"): "019",
    ("Publishing Production", "Audio and Visual Production"): "020",
    ("Publishing Production", "Books/Videos/CDs"): "021",
    ("Publishing Production", "Printing Costs"): "022",
    ("Publishing Production", "Software Development for Publishing"): "023",
    ("Publishing Production", "Material Costs"): "024",
    ("Publishing Production", "Shipping for Production"): "025",
    ("Publishing Production", "Digital Product Development"): "026",
    ("Publishing Production", "Pre-production"): "027",
    ("Publishing Production", "Post-production Costs"): "028",
    ("Information Technology", "Hardware"): "029",
    ("Information Technology", "IT Services"): "030",
    ("Information Technology", "Software"): "031",
    ("Logistics", "Courier, Express, and Postal Services"): "032",
    ("Logistics", "Warehousing and Material Handling"): "033",
    ("Logistics", "Transportation Logistics"): "034",
    ("Logistics", "Delivery Services"): "035",
    ("Marketing & Advertising", "Advertising"): "036",
    ("Marketing & Advertising", "Outdoor Advertising"): "037",
    ("Marketing & Advertising", "Marketing Agencies"): "038",
    ("Marketing & Advertising", "Direct Mail"): "039",
    ("Marketing & Advertising", "Customer Communication"): "040",
    ("Marketing & Advertising", "Online Marketing"): "041",
    ("Marketing & Advertising", "Events"): "042",
    ("Marketing & Advertising", "Promotional Materials"): "043",
    ("Production", "Warehouse and Operational Equipment"): "044",
    ("Production", "Production Machinery"): "045",
    ("Production", "Spare Parts"): "046",
    ("Production", "Internal Transportation"): "047",
    ("Production", "Production Materials"): "048",
    ("Production", "Consumables"): "049",
    ("Production", "Maintenance and Repairs"): "050",
    ("General Services", "Accommodation Rentals"): "001",
    ("General Services", "Membership Fees"): "002",
    ("General Services", "Workplace Safety"): "003",
    ("General Services", "Consulting"): "004",
    ("General Services", "Financial Services"): "005",
    ("General Services", "Fleet Management"): "006",
    ("General Services", "Recruitment Services"): "007",
    ("General Services", "Professional Development"): "008",
    ("General Services", "Miscellaneous Services"): "009",
    ("General Services", "Insurance"): "010"
}


def build_category_ids() -> Dict[str, List[str]]:
    """Get all valid group IDs for a given category.
    Return a mapping: category -> list of group IDs.
    Eg. "Facility Management" -> ["011", "012", ...]"""
    result: Dict[str, List[str]] = {}
    for (cat, _), cid in _COMMODITY_IDS.items():
        result.setdefault(cat, []).append(cid)
    return result


def build_commodity_groups_text() -> str:
    """Used in LLM prompts (Rules) to show the full set of valid options
    Return a human-readable string of all categories and their groups.
    Eg. Facility Management:  011=Electrical Engineering, 012=Facility Management Services, ..."""
    from collections import defaultdict
    groups: Dict[str, List[str]] = defaultdict(list)
    for (cat, name), cid in _COMMODITY_IDS.items():
        groups[cat].append(f"{cid}={name}")
    lines = ["\nCategories and their commodity groups:\n"]
    for cat, items in groups.items():
        lines.append(f"{cat}:")
        lines.append("  " + ", ".join(items))
        lines.append("")
    return "\n".join(lines)


def build_valid_categories_str(category_ids: Dict[str, List[str]]) -> str:
    """Used in fetching the specific category.
    Return a comma-separated string of all valid category names, quoted.
    Eg. '"Facility Management", "Publishing Production", ..."'"""
    return ", ".join(f'"{c}"' for c in category_ids)


def build_id_to_name() -> Dict[str, str]:
    """Return a mapping: group ID -> group name.
    Eg. "011" -> "Electrical Engineering", "012" -> "Facility Management Services", ..."""
    return {cid: name for (_, name), cid in _COMMODITY_IDS.items()}


def category_groups_text(category: str, category_ids: Dict[str, List[str]], id_to_name: Dict[str, str]) -> str:
    """Used to show the LLM only the valid groups for the selected category in the second LLM call
    Return a short ID=Name list for only the groups in the given category.
    Eg. for "Facility Management": "011=Electrical Engineering, 012=Facility Management Services, ..."
    """
    ids = category_ids.get(category, [])
    return ", ".join(f"{cid}={id_to_name[cid]}" for cid in ids)


# Export the raw data for use elsewhere
COMMODITY_IDS = _COMMODITY_IDS
