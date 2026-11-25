"""Exact formation assignment at the engine's ten-decimal score precision."""

SCALE = 10**10


def assignment_frontier(options, current=None, *, count_changes=False):
    """Best maximum-coverage assignment for each change count, or the single best lineup."""
    n = len(options)
    current = current or [None] * n
    by_identity = {}
    for slot, entries in enumerate(options):
        # Retain N different identities per change class. At most N-1 can be
        # occupied elsewhere. Order within each class preserves score and UUID ties.
        seen = {}
        for row in sorted(entries, key=lambda r: (-round(r["score"] * SCALE),
                                                   r["entity_id"] != current[slot], r["entity_id"])):
            item = row["entity_id"]
            identity = row.get("identity_group", item)
            changed = int(current[slot] != item)
            groups = seen.setdefault(changed if count_changes else 0, set())
            if identity in groups or len(groups) >= n:
                continue
            groups.add(identity)
            by_identity.setdefault(identity, []).append((slot, item, round(row["score"] * SCALE), changed))

    # Identities confined to one slot never compete elsewhere. One best option per
    # slot and edit class suffices, including the UUID tie-break inside that class.
    independent = {}
    shared = []
    for choices in by_identity.values():
        if len({edge[0] for edge in choices}) > 1:
            shared.append(choices)
            continue
        for edge in choices:
            slot, item, value, change = edge
            key = slot, change if count_changes else 0
            order = -value, change, item
            if key not in independent or order < independent[key][0]:
                independent[key] = order, edge
    groups = shared + [[edge] for _, edge in independent.values()]
    states = {(0, 0): (0, 0, ("",) * n)}
    for choices in groups:
        for (mask, _), (score, changes, assigned) in list(states.items()):
            for slot, item, value, change in choices:
                bit = 1 << slot
                if mask & bit:
                    continue
                total = score + value
                edits = changes + change
                key = (mask | bit, edits if count_changes else 0)
                prior = states.get(key)
                if prior and (total, -edits) < (prior[0], -prior[1]):
                    continue
                path = assigned[:slot] + (item,) + assigned[slot+1:]
                if prior is None or (total, -edits) > (prior[0], -prior[1]) or path < prior[2]:
                    states[key] = total, edits, path

    best = {}
    for (mask, bucket), (total, edits, path) in states.items():
        order = (-mask.bit_count(), -total, edits, path)
        if bucket not in best or order < best[bucket]:
            best[bucket] = order
    lookup = [{r["entity_id"]: r for r in entries} for entries in options]
    return {bucket: [entries.get(item) for entries, item in zip(lookup, order[-1])]
            for bucket, order in best.items()}


def optimal_assignments(options, current=None):
    return assignment_frontier(options, current)[0]
