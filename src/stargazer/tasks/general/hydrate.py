"""
General hydration task for Stargazer types.

Routes IpFiles from IPFS queries to appropriate type instances based on
the `type` and `component` keyvalues.
"""

from stargazer.config import gatk_env
from stargazer.types import Reference, Alignment, Variants, Reads
from stargazer.utils.pinata import default_client, IpFile
from stargazer.utils.query import generate_query_combinations


# Type registry maps (type, component) -> (TypeClass, field_name, is_list)
# This enables routing IpFiles to the correct type field based on keyvalues
# is_list=True means the field is a list and files should be appended
TYPE_REGISTRY: dict[tuple[str, str], tuple[type, str, bool]] = {
    # Reference components
    ("reference", "fasta"): (Reference, "fasta", False),
    ("reference", "faidx"): (Reference, "faidx", False),
    ("reference", "sequence_dictionary"): (Reference, "sequence_dictionary", False),
    ("reference", "aligner_index"): (Reference, "aligner_index", True),
    # Alignment components
    ("alignment", "alignment"): (Alignment, "alignment", False),
    ("alignment", "index"): (Alignment, "index", False),
    # Variants components
    ("variants", "vcf"): (Variants, "vcf", False),
    ("variants", "index"): (Variants, "index", False),
    # Reads components
    ("reads", "r1"): (Reads, "r1", False),
    ("reads", "r2"): (Reads, "r2", False),
}

# Identity fields for each type (used to group files into instances)
# When hydrating, files are grouped by their identity field value
TYPE_IDENTITY: dict[str, str] = {
    "reference": "build",
    "alignment": "sample_id",
    "variants": "sample_id",
    "reads": "sample_id",
}


@gatk_env.task
async def hydrate(
    filters: dict[str, str | list[str]],
) -> list[Reference | Alignment | Variants | Reads]:
    """
    Hydrate types from IPFS based on keyvalue filters.

    Uses cartesian product for list-valued filters. Routes each returned
    IpFile to the appropriate type based on its `type` and `component`
    keyvalues.

    Args:
        filters: Keyvalue filters (e.g., {"type": "alignment", "sample_id": ["S1", "S2"]})

    Returns:
        List of hydrated type instances

    Example:
        # Hydrate all alignments for a sample
        alignments = await hydrate({"type": "alignment", "sample_id": "NA12878"})

        # Hydrate reference with specific build
        refs = await hydrate({"type": "reference", "build": "GRCh38"})

        # Hydrate multiple samples (cartesian product)
        alignments = await hydrate({
            "type": "alignment",
            "sample_id": ["S1", "S2", "S3"],
        })

        # Hydrate specific components only
        refs = await hydrate({
            "type": "reference",
            "build": "GRCh38",
            "component": ["fasta", "faidx"],
        })
    """
    # Generate cartesian product of queries
    query_combinations = generate_query_combinations(base_query={}, filters=filters)

    # Execute all queries and collect unique files
    all_files: dict[str, IpFile] = {}
    for query in query_combinations:
        ipfiles = await default_client.query_files(query)
        for ipfile in ipfiles:
            all_files[ipfile.cid] = ipfile

    # Group files by (type, identity_value)
    # e.g., ("alignment", "S123") -> [IpFile, IpFile]
    grouped: dict[tuple[str, str], list[IpFile]] = {}
    for ipfile in all_files.values():
        file_type = ipfile.keyvalues.get("type")
        if not file_type:
            continue

        identity_key = TYPE_IDENTITY.get(file_type)
        if not identity_key:
            continue

        identity_value = ipfile.keyvalues.get(identity_key)
        if not identity_value:
            continue

        key = (file_type, identity_value)
        grouped.setdefault(key, []).append(ipfile)

    # Build type instances from grouped files
    results: list[Reference | Alignment | Variants | Reads] = []
    for (file_type, identity_value), ipfiles in grouped.items():
        # Create instance with identity field
        identity_key = TYPE_IDENTITY[file_type]
        if file_type == "reference":
            instance = Reference(**{identity_key: identity_value})
        elif file_type == "alignment":
            instance = Alignment(**{identity_key: identity_value})
        elif file_type == "variants":
            instance = Variants(**{identity_key: identity_value})
        elif file_type == "reads":
            instance = Reads(**{identity_key: identity_value})
        else:
            continue

        # Assign files to component fields
        for ipfile in ipfiles:
            component = ipfile.keyvalues.get("component")
            registry_key = (file_type, component)

            if registry_key in TYPE_REGISTRY:
                _, field_name, is_list = TYPE_REGISTRY[registry_key]
                if is_list:
                    getattr(instance, field_name).append(ipfile)
                else:
                    setattr(instance, field_name, ipfile)

        results.append(instance)

    return results
