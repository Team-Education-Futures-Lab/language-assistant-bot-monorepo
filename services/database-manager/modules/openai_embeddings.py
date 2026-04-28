import os
from typing import List

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class OpenAIEmbeddings:
    """Minimal OpenAI embeddings wrapper using openai>=1.0.0 client.

    Uses `OpenAI().embeddings.create(...)` to obtain vectors.
    """

    def __init__(self, model_name: str | None = None):
        self.model = model_name or os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise RuntimeError('OPENAI_API_KEY not set in environment')
        if OpenAI is None:
            raise RuntimeError('openai>=1.0.0 is required; please install or upgrade the openai package')
        self.client = OpenAI(api_key=api_key)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        resp = self.client.embeddings.create(model=self.model, input=texts)
        embeddings = []
        for item in getattr(resp, 'data', []) or []:
            if hasattr(item, 'embedding'):
                embeddings.append(item.embedding)
            else:
                embeddings.append(item['embedding'])
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        resp = self.client.embeddings.create(model=self.model, input=[text])
        first = (getattr(resp, 'data', []) or [])[0]
        if hasattr(first, 'embedding'):
            return first.embedding
        return first['embedding']
