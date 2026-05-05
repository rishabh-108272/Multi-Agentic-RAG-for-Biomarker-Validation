import requests
import json
import logging

logger = logging.getLogger(__name__)

DGIDB_GRAPHQL_URL = "https://dgidb.org/api/graphql"

DGIDB_GRAPHQL_QUERY = """
query DrugInteractions($genes: [String!]) {
  genes(names: $genes) {
    nodes {
      interactions {
        drug {
          name
          conceptId
        }
        interactionScore
        interactionTypes {
          type
          directionality
        }
        interactionAttributes {
          name
          value
        }
        publications {
          pmid
        }
        sources {
          sourceDbName
        }
      }
    }
  }
}
"""


class DrugRepurposingEngine:
    def __init__(self):
        pass

    def fetch_dgidb_drugs_via_graphql(self, genes):
        """
        Query DGIdb GraphQL API for drug-gene interactions.
        Returns:
        {
            "EGFR": [
                {
                    "drug_name": "...",
                    "concept_id": "...",
                    "score": ...,
                    "types": [...],
                    "publications": [...],
                    "sources": [...]
                }
            ]
        }
        """

        if not genes:
            return {}

        unique_genes = sorted({str(g).strip().upper() for g in genes if str(g).strip()})

        payload = {
            "query": DGIDB_GRAPHQL_QUERY,
            "variables": {"genes": unique_genes}
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            resp = requests.post(
                DGIDB_GRAPHQL_URL,
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
        except Exception as e:
            logger.error(f"DGIdb GraphQL network error: {e}")
            return {}

        if resp.status_code != 200:
            logger.warning(f"DGIdb returned {resp.status_code}: {resp.text[:200]}")
            return {}

        try:
            data = resp.json()
        except ValueError:
            logger.warning(f"DGIdb returned non-JSON response: {resp.text[:200]}")
            return {}

        if "errors" in data:
            logger.warning(f"DGIdb GraphQL errors: {data['errors']}")
            return {}

        root = data.get("data", {}).get("genes", {})
        nodes = root.get("nodes", []) or []

        gene_to_drugs = {}

        for gene_index, gene_node in enumerate(nodes):
            if gene_index >= len(unique_genes):
                continue

            gene_name = unique_genes[gene_index]
            interactions = gene_node.get("interactions", []) or []

            gene_to_drugs[gene_name] = []

            for inter in interactions:
                drug = inter.get("drug") or {}
                drug_name = drug.get("name")
                concept_id = drug.get("conceptId")

                if not drug_name:
                    continue

                gene_to_drugs[gene_name].append({
                    "drug_name": drug_name,
                    "concept_id": concept_id,
                    "score": inter.get("interactionScore"),
                    "types": [t.get("type") for t in inter.get("interactionTypes", [])],
                    "publications": [p.get("pmid") for p in inter.get("publications", [])],
                    "sources": [s.get("sourceDbName") for s in inter.get("sources", [])],
                })

        return gene_to_drugs

    def get_top_drug_candidates(self, genes, max_drugs_per_gene=5):
        """
        Returns filtered top drug candidates
        """
        raw_results = self.fetch_dgidb_drugs_via_graphql(genes)

        filtered_results = {}

        for gene, drugs in raw_results.items():
            sorted_drugs = sorted(
                drugs,
                key=lambda x: x.get("score") or 0,
                reverse=True
            )

            filtered_results[gene] = sorted_drugs[:max_drugs_per_gene]

        return filtered_results