import asyncio
from app.connectors.registry import connector_registry

async def main():
    conns = connector_registry.get_all_connectors()
    print(f"Total connectors registered: {len(conns)}")
    await connector_registry.run_all_health_checks()
    manifests = connector_registry.get_manifests()
    by_health = {}
    for m in manifests:
        by_health[m.health.value] = by_health.get(m.health.value, 0) + 1
    print("Health distribution:")
    for h, cnt in sorted(by_health.items()):
        print(f"  {h}: {cnt}")

    # Verify that the 24 candidate connectors are present
    candidate_names = [
        "whatsmyname", "blackbird", "holehe", "urlscan", "crtsh",
        "securitytrails", "greynoise", "abuseipdb", "misp", "yeti",
        "opencti", "opensanctions", "graphistry", "networkx", "gephi",
        "apache_tika", "qgis", "openstreetmap_overpass", "gdelt", "openaleph",
        "followthemoney", "datasette", "intelowl", "openosint"
    ]
    missing = [c for c in candidate_names if not connector_registry.get_connector(c)]
    if missing:
        print(f"ERROR: Missing candidates: {missing}")
    else:
        print("SUCCESS: All 24 candidate connectors are registered.")

if __name__ == "__main__":
    asyncio.run(main())
