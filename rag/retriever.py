"""
RAG Retriever Module for Kepler Tech Product Corpus.
Utilizes TF-IDF vector embeddings combined with NLP entity boosting.
"""

import json
import os
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CORPUS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "kepler_product_corpus.json")


class RagRetriever:
    def __init__(self, corpus_path: str = CORPUS_PATH):
        self.corpus_path = corpus_path
        self.products = []
        self.doc_texts = []
        self.vectorizer = None
        self.tfidf_matrix = None
        self._load_and_index()

    def _load_and_index(self):
        """Loads corpus JSON and builds the TF-IDF search index."""
        if not os.path.exists(self.corpus_path):
            return

        with open(self.corpus_path, "r", encoding="utf-8") as f:
            self.products = json.load(f)

        self.doc_texts = []
        for p in self.products:
            # Flatten product attributes into a rich searchable document string
            parts = [
                f"Name: {p.get('name', '')}",
                f"Brand: {p.get('brand', '')}",
                f"Series: {p.get('series', '')}",
                f"Category: {p.get('category', '')}",
                f"Width/Size: {p.get('width', '')} {p.get('print_sizes', '')}",
                f"Resolution: {p.get('max_resolution', '')}",
                f"Speed: {p.get('speed', '')} {p.get('print_speed', '')}",
                f"Ink/Tech: {p.get('ink_technology', '')} {p.get('technology', '')}",
                f"Capacities: {p.get('cartridge_capacities', '')} {p.get('capacity', '')}",
                f"Media: {p.get('media_handling', '')} {p.get('surface', '')}",
                f"Connectivity/Features: {p.get('connectivity', '')} {p.get('features', '')}",
                f"Intended Use: {p.get('intended_usage', '')}",
                f"Comparison: {p.get('comparison_highlights', '')}"
            ]
            doc_str = " | ".join([part for part in parts if part.strip() and not part.endswith(":")])
            self.doc_texts.append(doc_str)

        if self.doc_texts:
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
            self.tfidf_matrix = self.vectorizer.fit_transform(self.doc_texts)

    def retrieve(self, query: str, nlp_context: dict = None, top_k: int = 3) -> list:
        """
        Retrieves top-k relevant verified product documents using vector similarity
        and entity keyword re-ranking.
        """
        if not self.vectorizer or not self.products:
            return []

        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.tfidf_matrix)[0]

        # Entity boosting: give an extra boost to documents matching detected entities
        if nlp_context:
            for idx, p in enumerate(self.products):
                # Category match
                if any(cat in p.get("category", "") for cat in nlp_context.get("categories", [])):
                    scores[idx] += 0.25
                # Brand match
                if any(b.lower() in p.get("brand", "").lower() for b in nlp_context.get("brands", [])):
                    scores[idx] += 0.15
                # Model match
                for m in nlp_context.get("models", []):
                    if m.lower() in p.get("name", "").lower():
                        scores[idx] += 0.40
                # Size match
                for s in nlp_context.get("sizes", []):
                    if "24" in s and "24" in p.get("width", ""):
                        scores[idx] += 0.30
                    elif "36" in s and "36" in p.get("width", ""):
                        scores[idx] += 0.30

        # Sort results by score
        ranked_indices = np.argsort(scores)[::-1]

        results = []
        for rank in range(min(top_k, len(self.products))):
            idx = ranked_indices[rank]
            score = float(scores[idx])
            prod = dict(self.products[idx])
            prod["similarity_score"] = round(score, 3)
            prod["doc_summary"] = self.doc_texts[idx]
            results.append(prod)

        return results

    def format_prompt_context(self, retrieved_items: list) -> str:
        """Formats retrieved product cards into a structured prompt block."""
        if not retrieved_items:
            return ""

        lines = ["--- VERIFIED SCRAPED PRODUCT SPECIFICATIONS (RAG CONTEXT) ---"]
        for idx, item in enumerate(retrieved_items, start=1):
            lines.append(f"[{idx}] {item['name']} (Relevance Score: {item['similarity_score']})")
            if item.get("category"):
                lines.append(f"    Category: {item['category']}")
            if item.get("width"):
                lines.append(f"    Width/Size: {item['width']}")
            if item.get("speed"):
                lines.append(f"    Speed: {item['speed']}")
            if item.get("ink_technology"):
                lines.append(f"    Ink: {item['ink_technology']}")
            if item.get("intended_usage"):
                lines.append(f"    Intended Use: {item['intended_usage']}")
            if item.get("comparison_highlights"):
                lines.append(f"    Practical Differentiation: {item['comparison_highlights']}")
            lines.append(f"    Source: {item.get('source_url', 'https://www.keplertechllc.com/')}")

        return "\n".join(lines)


# Global singleton instance
rag_retriever = RagRetriever()
