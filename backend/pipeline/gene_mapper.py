import json
import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class GeneMapper:
    def __init__(self):
        self.mapping_file = os.path.join(settings.BASE_DIR, "gene_index_map.json")
        self.gene_map = self.load_mapping()

    def load_mapping(self):
        """
        Load mapping from gene_index_map.json
        """
        if os.path.exists(self.mapping_file):
            try:
                with open(self.mapping_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load gene mapping file: {e}")
                return {}
        return {}

    def save_mapping(self):
        """
        Save mapping to gene_index_map.json
        """
        try:
            with open(self.mapping_file, "w", encoding="utf-8") as f:
                json.dump(self.gene_map, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save gene mapping file: {e}")

    def map_gene(self, gene_name):
        """
        Convert Gene1 -> TP53 etc.
        """
        return self.gene_map.get(gene_name, gene_name)

    def map_genes(self, gene_list):
        """
        Map list of genes
        """
        return [self.map_gene(g) for g in gene_list]

    def add_mapping(self, csv_gene_name, actual_gene_symbol):
        """
        Add/update mapping dynamically
        """
        self.gene_map[csv_gene_name] = actual_gene_symbol
        self.save_mapping()

    def map_xai_results(self, xai_results):
        """
        Update XAI results with actual gene symbols
        """
        updated_results = []

        for item in xai_results:
            mapped_gene = self.map_gene(item["gene"])

            updated_item = item.copy()
            updated_item["gene_symbol"] = mapped_gene

            updated_results.append(updated_item)

        return updated_results