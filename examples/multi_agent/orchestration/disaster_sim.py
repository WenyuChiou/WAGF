
def depth_to_qualitative_description(depth_ft: float) -> str:
    """Converts flood depth in feet to a qualitative description."""
    if depth_ft <= 0:
        return "no flooding"
    if depth_ft < 0.5:
        return "minor flooding (ankle-deep)"
    if depth_ft < 2.0:
        return "significant flooding (knee-deep)"
    if depth_ft < 5.0:
        return "severe flooding (first-floor inundation)"
    return "catastrophic flooding"
