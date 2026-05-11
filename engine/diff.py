def diff_rows(current: dict, proposed: dict) -> dict:
    added, removed, updated = [], [], []
    current_keys = set(current.keys())
    proposed_keys = set(proposed.keys())
    for k in sorted(proposed_keys - current_keys):
        added.append(proposed[k])
    for k in sorted(current_keys - proposed_keys):
        removed.append(current[k])
    for k in sorted(current_keys & proposed_keys):
        before = {kk: str(vv) for kk, vv in current[k].items() if not kk.startswith('_')}
        after = {kk: str(vv) for kk, vv in proposed[k].items() if not kk.startswith('_')}
        if before != after:
            updated.append({"key": k, "before": before, "after": after})
    return {"added": added, "updated": updated, "removed": removed, "counts": {"added": len(added), "updated": len(updated), "removed": len(removed)}}

def flatten_nodes(network: dict) -> dict:
    result = {}
    def visit(name, node, parent=None):
        if not isinstance(node, dict):
            return
        record = dict(node)
        children = record.pop("children", {})
        record["parent"] = parent
        result[name] = record
        if isinstance(children, dict):
            for cname, cnode in children.items():
                visit(cname, cnode, name)
    for name, node in (network or {}).items():
        visit(name, node, None)
    return result

def diff_network(current: dict, proposed: dict) -> dict:
    c = flatten_nodes(current)
    p = flatten_nodes(proposed)
    added, removed, updated = [], [], []
    for k in sorted(set(p) - set(c)):
        added.append({"name": k, **p[k]})
    for k in sorted(set(c) - set(p)):
        removed.append({"name": k, **c[k]})
    for k in sorted(set(c) & set(p)):
        if c[k] != p[k]:
            updated.append({"name": k, "before": c[k], "after": p[k]})
    return {"added": added, "updated": updated, "removed": removed, "counts": {"added": len(added), "updated": len(updated), "removed": len(removed)}}
