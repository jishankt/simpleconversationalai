"""
RAG Retriever Module for Kepler Tech Product Corpus.
Dynamically indexes all 792 verified products in data/products.json without hardcoding.
Combines exact SKU / lexical token matching with TF-IDF semantic similarity and NLP entity boosting.
"""

import json
import os
import re
from typing import List, Dict, Optional, Any
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

PRODUCTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "products.json")
CORPUS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "kepler_product_corpus.json")


class RagRetriever:
    def __init__(self, products_path: str = PRODUCTS_PATH, corpus_path: str = CORPUS_PATH):
        self.products_path = products_path
        self.corpus_path = corpus_path
        self.products: List[Dict[str, Any]] = []
        self.sku_index: Dict[str, Dict[str, Any]] = {}
        self.doc_texts: List[str] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self._load_and_index()

    def _load_and_index(self):
        """Loads products.json and builds lexical and TF-IDF search index."""
        raw_products = []
        if os.path.exists(self.products_path):
            with open(self.products_path, "r", encoding="utf-8") as f:
                raw_products = json.load(f)

        # Merge additional rich specification fields from kepler_product_corpus if available
        corpus_lookup = {}
        if os.path.exists(self.corpus_path):
            try:
                with open(self.corpus_path, "r", encoding="utf-8") as cf:
                    for cp in json.load(cf):
                        norm_k = re.sub(r"[^a-z0-9]", "", cp.get("name", "").lower())
                        corpus_lookup[norm_k] = cp
            except Exception:
                pass

        self.products = []
        self.sku_index = {}
        self.doc_texts = []

        for p in raw_products:
            prod = dict(p)
            norm_name = re.sub(r"[^a-z0-9]", "", prod.get("name", "").lower())
            if norm_name in corpus_lookup:
                extra = corpus_lookup[norm_name]
                for k in ["width", "speed", "ink_technology", "intended_usage", "comparison_highlights"]:
                    if k in extra and not prod.get(k):
                        prod[k] = extra[k]

            sku = str(prod.get("sku", "")).strip()
            if sku:
                self.sku_index[sku.upper()] = prod

            # Build rich document string for indexing
            name = prod.get("name", "")
            cat = prod.get("category", "")
            desc = prod.get("description", "")
            tags = " ".join(prod.get("tags", [])) if isinstance(prod.get("tags"), list) else str(prod.get("tags", ""))
            intended = prod.get("intended_usage", "")
            highlights = prod.get("comparison_highlights", "")
            width = prod.get("width", "")
            speed = prod.get("speed", "")
            ink = prod.get("ink_technology", "")

            doc_parts = [
                f"Name: {name}",
                f"SKU: {sku}",
                f"Category: {cat}",
                f"Description: {desc}",
                f"Tags: {tags}",
                f"Width: {width}",
                f"Speed: {speed}",
                f"Ink: {ink}",
                f"Intended: {intended}",
                f"Highlights: {highlights}"
            ]
            doc_str = " | ".join([part for part in doc_parts if not part.endswith(":")])
            self.products.append(prod)
            self.doc_texts.append(doc_str)

        if self.doc_texts:
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", max_features=8000)
            self.tfidf_matrix = self.vectorizer.fit_transform(self.doc_texts)

    def search(self, query: str, category: Optional[str] = None, limit: int = 4) -> List[Dict[str, Any]]:
        """
        Dynamically searches the full 792 catalog items using hybrid lexical + semantic search.
        """
        if not self.products:
            return []

        q_clean = query.strip()
        q_upper = q_clean.upper()
        q_lower = q_clean.lower()

        # 1. Exact SKU match
        if q_upper in self.sku_index:
            target = dict(self.sku_index[q_upper])
            target["similarity_score"] = 1.0
            return [target]

        # 2. Model token exact / prefix match ONLY for dedicated short model queries (e.g. 'P700', 'DS-900WN', 'T3100')
        tokens = [t for t in re.findall(r"[A-Za-z0-9\-]+", q_lower) if len(t) >= 3]
        if 1 <= len(tokens) <= 2 and not any(w in q_lower for w in ["recommend", "printer", "scanner", "need", "best", "speed", "flatbed"]):
            exact_model_matches = []
            for p in self.products:
                p_name = p.get("name", "").lower()
                p_sku = str(p.get("sku", "")).lower()
                for t in tokens:
                    pattern = r'(?:\b|_|-)' + re.escape(t) + r'(?:\b|_|-|\s|$)'
                    if re.search(pattern, p_name) or re.search(pattern, p_sku):
                        exact_model_matches.append(p)
                        break

            if exact_model_matches:
                if category:
                    cat_filtered = [p for p in exact_model_matches if category.lower() in p.get("category", "").lower()]
                    if cat_filtered:
                        exact_model_matches = cat_filtered
                res = []
                seen_exact = set()
                for item in exact_model_matches:
                    norm = re.sub(r"[^a-z0-9]", "", item.get("name", "").lower())
                    if norm not in seen_exact:
                        seen_exact.add(norm)
                        d = dict(item)
                        d["similarity_score"] = 0.95
                        res.append(d)
                        if len(res) >= limit:
                            break
                if res:
                    return res

        # 3. TF-IDF Semantic Vector Similarity
        if not self.vectorizer or self.tfidf_matrix is None:
            return []

        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.tfidf_matrix)[0]

        # Category and keyword boosting
        for idx, p in enumerate(self.products):
            p_cat = p.get("category", "").lower()
            p_name = p.get("name", "").lower()
            p_desc = p.get("description", "").lower()

            if category and category.lower() in p_cat:
                scores[idx] += 0.35

            # Boost if query keywords appear in product title
            for w in q_lower.split():
                if len(w) >= 3 and w in p_name:
                    scores[idx] += 0.20
                elif len(w) >= 3 and w in p_desc:
                    scores[idx] += 0.05

        ranked_indices = np.argsort(scores)[::-1]
        results = []
        seen_names = set()

        for idx in ranked_indices:
            if scores[idx] <= 0:
                continue
            prod = dict(self.products[idx])
            norm = re.sub(r"[^a-z0-9]", "", prod.get("name", "").lower())
            if norm in seen_names:
                continue
            seen_names.add(norm)
            prod["similarity_score"] = round(float(scores[idx]), 3)
            results.append(prod)
            if len(results) >= limit:
                break

        return results

    def retrieve(self, query: str, nlp_context: dict = None, top_k: int = 3) -> list:
        """Backward-compatible RAG retriever method with NLP entity boosting."""
        cat = None
        if nlp_context and nlp_context.get("categories"):
            cat = nlp_context["categories"][0]
        return self.search(query=query, category=cat, limit=top_k)

    def get_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """Finds a product directly by SKU."""
        return self.sku_index.get(sku.strip().upper())

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Finds a product by name match."""
        name_clean = name.strip().lower()
        for p in self.products:
            if name_clean in p.get("name", "").lower():
                return p
        return None

    def format_prompt_context(self, retrieved_items: list) -> str:
        """Formats retrieved product cards into a structured prompt block for LLM."""
        if not retrieved_items:
            return ""

        lines = ["--- VERIFIED CATALOG RETRIEVAL (LIVE CATALOG CONTEXT) ---"]
        for idx, item in enumerate(retrieved_items, start=1):
            name = item.get("name", "")
            sku = item.get("sku", "")
            score = item.get("similarity_score", 0)
            url = item.get("website_url") or item.get("web_url") or item.get("source_url", "")
            img = item.get("image_url") or item.get("image", "")
            lines.append(f"[{idx}] {name} (SKU: {sku} | Score: {score})")
            if item.get("category"):
                lines.append(f"    Category: {item['category']}")
            if item.get("description"):
                lines.append(f"    Description: {item['description']}")
            if item.get("width"):
                lines.append(f"    Print Width/Size: {item['width']}")
            if item.get("speed"):
                lines.append(f"    Speed: {item['speed']}")
            if item.get("ink_technology"):
                lines.append(f"    Technology: {item['ink_technology']}")
            if item.get("intended_usage"):
                lines.append(f"    Intended Use: {item['intended_usage']}")
            if url:
                lines.append(f"    Product URL: {url}")
            if img:
                lines.append(f"    Image: {img}")

        return "\n".join(lines)


# Global singleton instance
rag_retriever = RagRetriever()
