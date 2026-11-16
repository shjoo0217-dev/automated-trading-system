"""Conservative, transitive grouping of verified copies/translations/revisions."""

def apply_lineage(reports, relationships=()):
    by_id = {r["report_id"]: dict(r) for r in reports}
    parent = {k: k for k in by_id}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        if by_id[a]["stock_code"] != by_id[b]["stock_code"]:
            raise ValueError("Refusing cross-company lineage")
        parent[max(find(a),find(b))] = min(find(a),find(b))

    hashes = {}
    families = {}
    for r in reports:
        for lookup,key in [(hashes,r["content_version"]),(families,r["family_id"])]:
            if key in lookup: union(r["report_id"],lookup[key])
            else: lookup[key]=r["report_id"]
    for relationship in relationships:
        if relationship.get("status") != "verified" or not relationship.get("evidence"):
            raise ValueError("A verified relationship and evidence are mandatory")
        a,b=relationship["report_id"],relationship["related_report_id"]
        if a not in by_id or b not in by_id: raise ValueError("Unknown lineage report")
        if relationship["kind"] not in {"translation_of","supersedes","copy_of"}: raise ValueError("Unknown relationship kind")
        union(a,b)
        by_id[a][relationship["kind"]]=b
        by_id[a]["relationship_status"]="verified"
    # Retain a deterministic pre-existing family ID for each union component.
    family={}
    for rid,r in by_id.items():
        root=find(rid);family[root]=min(family.get(root,r["family_id"]),r["family_id"])
    for rid,r in by_id.items():r["family_id"]=family[find(rid)]
    return list(by_id.values())
