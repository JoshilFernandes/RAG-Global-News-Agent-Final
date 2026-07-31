import os
import faiss
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", os.path.join("data", "faiss.index"))
FAISS_METADATA_PATH = os.getenv("FAISS_METADATA_PATH", os.path.join("data", "faiss_meta.pkl"))


class VectorStore:
    def __init__(self, model_name: str = EMBEDDING_MODEL, index_path: str = FAISS_INDEX_PATH, meta_path: str = FAISS_METADATA_PATH):
        os.makedirs(os.path.dirname(index_path) or ".", exist_ok=True)
        os.makedirs(os.path.dirname(meta_path) or ".", exist_ok=True)
        self.model = SentenceTransformer(model_name)
        self.index_path = index_path
        self.meta_path = meta_path

        # build or load index
        self.dimension = self.model.get_sentence_embedding_dimension()
        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
            try:
                with open(self.meta_path, "rb") as f:
                    self.meta = pickle.load(f)
            except Exception:
                self.meta = {}
        else:
            # Inner product on normalized vectors => cosine similarity
            self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.dimension))
            self.meta = {}

    def _embed(self, texts):
        embs = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        # normalize for cosine similarity using IP
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        embs = embs / norms
        return embs.astype('float32')

    def add(self, doc_id: int, text: str, metadata: dict | None = None):
        emb = self._embed([text])
        ids = np.array([doc_id], dtype='int64')
        self.index.add_with_ids(emb, ids)
        if metadata:
            self.meta[int(doc_id)] = metadata

    def bulk_add(self, id_text_pairs: list[tuple[int, str]], metadatas: dict | None = None, batch_size: int = 512):
        # id_text_pairs: list of (int_id, text)
        for i in range(0, len(id_text_pairs), batch_size):
            batch = id_text_pairs[i:i+batch_size]
            ids = np.array([p[0] for p in batch], dtype='int64')
            texts = [p[1] for p in batch]
            embs = self._embed(texts)
            self.index.add_with_ids(embs, ids)
            if metadatas:
                for pid, md in metadatas.items():
                    self.meta[int(pid)] = md

    def search(self, query: str, top_k: int = 5):
        q_emb = self._embed([query])
        D, I = self.index.search(q_emb, top_k)
        # Flatten and return list of (id, score)
        results = []
        for idx, score in zip(I[0], D[0]):
            if idx == -1:
                continue
            results.append((int(idx), float(score)))
        return results

    def save(self):
        faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, "wb") as f:
            pickle.dump(self.meta, f)
