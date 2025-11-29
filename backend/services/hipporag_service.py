"""
HippoRAG 2 Service para MineDash AI
Reemplaza LightRAG con memoria de largo plazo mejorada
"""
from pathlib import Path
from typing import List, Dict, Optional
import os

class MineDashMemory:
    """
    Servicio de memoria de largo plazo usando HippoRAG 2.
    Permite al agente aprender y recordar informacion entre sesiones.
    """

    def __init__(
        self,
        save_dir: str = "data/hipporag",
        llm_model: str = "gpt-4o-mini",
        embedding_model: str = "text-embedding-3-small"
    ):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.llm_model = llm_model
        self.embedding_model = embedding_model
        self.hipporag = None
        self.is_indexed = False
        self._initialized = False

    def _lazy_init(self):
        """Inicializacion perezosa para evitar cargar HippoRAG si no se usa"""
        if self._initialized:
            return

        try:
            from hipporag import HippoRAG

            # Configurar API key
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY no configurada")

            self.hipporag = HippoRAG(
                save_dir=str(self.save_dir),
                llm_model_name=self.llm_model,
                embedding_model_name=self.embedding_model
            )
            self._initialized = True
            print(f"[HippoRAG] Inicializado en {self.save_dir}")

        except ImportError as e:
            print(f"[HippoRAG] No disponible: {e}")
            print("[HippoRAG] Usando fallback a memoria simple")
            self._use_fallback = True
            self._initialized = True
            self._fallback_memory = []

            # Cargar memoria persistida desde archivo
            memory_file = self.save_dir / "fallback_memory.txt"
            if memory_file.exists():
                try:
                    with open(memory_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Separar por delimitador ---
                        docs = [doc.strip() for doc in content.split('---') if doc.strip()]
                        self._fallback_memory = docs
                        print(f"[HippoRAG] Cargados {len(docs)} documentos desde fallback_memory.txt")
                except Exception as load_error:
                    print(f"[HippoRAG] Error cargando memoria: {load_error}")

    def ingest_documents(self, documents: List[str]) -> Dict:
        """
        Indexa una lista de documentos en HippoRAG.

        Args:
            documents: Lista de strings con el contenido de los documentos

        Returns:
            Dict con status y count
        """
        self._lazy_init()

        if hasattr(self, '_use_fallback') and self._use_fallback:
            self._fallback_memory.extend(documents)
            return {"status": "fallback", "count": len(documents)}

        try:
            print(f"[HippoRAG] Indexando {len(documents)} documentos...")
            self.hipporag.index(docs=documents)
            self.is_indexed = True
            return {"status": "success", "count": len(documents)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def query(self, question: str, num_results: int = 5) -> Dict:
        """
        Busca informacion relevante para una pregunta.

        Args:
            question: La pregunta o consulta
            num_results: Numero de resultados a retornar

        Returns:
            Dict con answer y sources
        """
        self._lazy_init()

        if hasattr(self, '_use_fallback') and self._use_fallback:
            # Fallback: busqueda simple por keywords
            question_lower = question.lower()
            matches = [doc for doc in self._fallback_memory
                      if any(word in doc.lower() for word in question_lower.split())]
            return {
                "answer": matches[0][:500] if matches else "No encontre informacion relevante.",
                "sources": matches[:num_results]
            }

        if not self.is_indexed:
            return {"error": "No hay documentos indexados", "answer": None, "sources": []}

        try:
            retrieval = self.hipporag.retrieve(
                queries=[question],
                num_to_retrieve=num_results
            )
            qa = self.hipporag.rag_qa(retrieval)

            return {
                "answer": qa[0] if qa else None,
                "sources": retrieval[0] if retrieval else []
            }
        except Exception as e:
            return {"error": str(e), "answer": None, "sources": []}

    def add_knowledge(self, new_docs: List[str]) -> Dict:
        """
        Agrega nuevo conocimiento a la memoria.
        Usado cuando el usuario dice "recuerda que...", "anota que...", etc.

        Args:
            new_docs: Lista de strings con la nueva informacion

        Returns:
            Dict con status y count
        """
        self._lazy_init()

        if hasattr(self, '_use_fallback') and self._use_fallback:
            self._fallback_memory.extend(new_docs)
            # Persistir en archivo
            memory_file = self.save_dir / "fallback_memory.txt"
            with open(memory_file, 'a', encoding='utf-8') as f:
                for doc in new_docs:
                    f.write(f"{doc}\n---\n")
            return {"status": "fallback_saved", "count": len(new_docs)}

        try:
            self.hipporag.index(docs=new_docs)
            return {"status": "added", "count": len(new_docs)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_stats(self) -> Dict:
        """Retorna estadisticas de la memoria"""
        self._lazy_init()

        if hasattr(self, '_use_fallback') and self._use_fallback:
            return {
                "mode": "fallback",
                "documents": len(self._fallback_memory)
            }

        return {
            "mode": "hipporag",
            "indexed": self.is_indexed,
            "save_dir": str(self.save_dir)
        }


# Singleton para acceso global
_memory: Optional[MineDashMemory] = None

def get_memory() -> MineDashMemory:
    """
    Obtiene la instancia singleton de MineDashMemory.

    Returns:
        MineDashMemory: La instancia de memoria
    """
    global _memory
    if _memory is None:
        _memory = MineDashMemory()
    return _memory


def search_knowledge(query: str) -> str:
    """
    Funcion de compatibilidad con el sistema anterior.
    Busca en la memoria y retorna la respuesta.

    Args:
        query: La consulta a buscar

    Returns:
        str: La respuesta encontrada o mensaje de error
    """
    memory = get_memory()
    result = memory.query(query)

    if result.get("error"):
        return f"Error buscando: {result['error']}"

    answer = result.get("answer")
    if answer:
        return answer

    sources = result.get("sources", [])
    if sources:
        return f"Informacion encontrada:\n" + "\n".join(sources[:3])

    return "No encontre informacion relevante en mi memoria."


def learn_information(info: str) -> str:
    """
    Aprende nueva informacion.

    Args:
        info: La informacion a recordar

    Returns:
        str: Mensaje de confirmacion
    """
    memory = get_memory()
    result = memory.add_knowledge([info])

    if result.get("status") in ["added", "fallback_saved"]:
        return f"Aprendido: {info[:100]}..."
    else:
        return f"Error aprendiendo: {result.get('error', 'desconocido')}"
