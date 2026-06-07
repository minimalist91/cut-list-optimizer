# optimizer.py
# Cutting optimization engine - pure logic, no visuals.
# Uses First-Fit Decreasing (FFD) bin-packing algorithm.
# Returns grouped bars so identical patterns are shown once with a count.

def optimize(parts, stock_length, kerf, end_trim):
    """
    parts        = list of (name, length, qty)
    stock_length = full length of one bar        e.g. 3000
    kerf         = blade thickness               e.g. 3
    end_trim     = waste trimmed from bar ends   e.g. 5

    Returns:
        groups = list of dicts:
                 {
                   "bar":     [(name, length), ...],
                   "count":   int,
                   "offcut":  int,
                 }
        stats  = dict with summary numbers
    """

    usable = stock_length - (2 * end_trim)

    # Expand parts into individual pieces
    pieces = []
    for name, length, qty in parts:
        if length <= 0 or qty <= 0:
            continue
        if length > usable:
            continue
        for _ in range(int(qty)):
            pieces.append((name, int(length)))

    if not pieces:
        return [], {}

    # Sort largest first (FFD)
    pieces.sort(key=lambda x: x[1], reverse=True)

    # Bin-packing loop
    bars      = []
    remaining = []

    for name, length in pieces:
        placed = False
        for i in range(len(bars)):
            if remaining[i] >= length + kerf:
                bars[i].append((name, length))
                remaining[i] -= (length + kerf)
                placed = True
                break
        if not placed:
            bars.append([(name, length)])
            remaining.append(usable - length - kerf)

    # Group identical patterns
    pattern_map = {}
    for i, bar in enumerate(bars):
        offcut = remaining[i] + kerf
        key    = tuple(bar)
        if key in pattern_map:
            pattern_map[key]["count"] += 1
        else:
            pattern_map[key] = {
                "bar":    bar,
                "count":  1,
                "offcut": offcut,
            }

    groups = sorted(pattern_map.values(), key=lambda g: g["count"], reverse=True)

    # Statistics
    total_bars      = len(bars)
    total_material  = total_bars * stock_length
    total_used      = sum(length for bar in bars for _, length in bar)
    total_waste     = total_material - total_used
    utilisation     = round(total_used / total_material * 100, 1) if total_material > 0 else 0
    total_pieces    = sum(len(bar) for bar in bars)
    unique_patterns = len(groups)

    stats = {
        "total_bars":      total_bars,
        "total_material":  total_material,
        "total_used":      total_used,
        "total_waste":     total_waste,
        "utilisation":     utilisation,
        "total_pieces":    total_pieces,
        "unique_patterns": unique_patterns,
    }

    return groups, stats
