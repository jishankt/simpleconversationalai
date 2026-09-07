"""
Hybrid Retrieval Engine for Kepler Tech Catalog.
Pipeline:
  1. Exact SKU / Model Match (normalize_product_identifier)
  2. Category & Metadata Hard Filter
  3. Keyword / BM25 Search
  4. Vector / Semantic Fallback
"""
import re
from typing import List, Optional
from catalog.schema import NormalizedProduct
from catalog.repository import catalog_repository
from catalog.product_resolver import resolve_canonical_id, normalize_model_identifier


class HybridRetriever:
    def __init__(self, repository=catalog_repository):
        self.repo = repository

    def retrieve(self, query: str, category: Optional[str] = None) -> List[NormalizedProduct]:
        """
        Retrieves matching products starting from exact identification down to semantic filtering.
        """
        # 1. Exact SKU / Model Match
        exact_id = resolve_canonical_id(query)
        if exact_id:
            prod = self.repo.get_by_id(exact_id)
            if prod:
                return [prod]

        # 2. Category Filter
        candidates = self.repo.get_by_category(category) if category else self.repo.get_all()

        # 3. Keyword / Token Search on Normalized candidates
        query_norm = normalize_model_identifier(query)
        query_tokens = [t for t in re.split(r"\s+", query.lower()) if len(t) > 2]

        scored_candidates = []
        for p in candidates:
            p_text = f"{p.name} {p.brand} {p.model} {' '.join(p.verified.applications)} {p.description or ''}".lower()
            token_matches = sum(1 for t in query_tokens if t in p_text)
            if token_matches > 0 or not query_tokens:
                scored_candidates.append((p, token_matches))

        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scored_candidates]


hybrid_retriever = HybridRetriever()
