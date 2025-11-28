"""
Servicio de Contexto MineOPS
VERSIÓN AUTO-DETECT - Detecta ruta automáticamente

Autor: David @ AIMINE
Versión: 2.6 - Auto path detection
"""

from pathlib import Path
from typing import Optional, Dict, List
import json
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# AUTO-DETECCIÓN DE RUTA
# ============================================================================

def encontrar_backend_dir():
    """
    Encuentra el directorio backend automáticamente
    Busca hacia arriba hasta encontrar la carpeta que contenga data/context/
    """
    current = Path(__file__).parent
    
    # Intentar hasta 3 niveles arriba
    for _ in range(3):
        # Verificar si aquí está data/context/mineops_context.json
        context_file = current / "data" / "context" / "mineops_context.json"
        if context_file.exists():
            return current, context_file
        
        # Subir un nivel
        current = current.parent
    
    # Si no se encontró, usar rutas default
    script_dir = Path(__file__).parent
    
    # Si estamos en services/, backend es el padre
    if script_dir.name == "services":
        backend = script_dir.parent
    else:
        # Si estamos en backend/, usar este directorio
        backend = script_dir
    
    context_file = backend / "data" / "context" / "mineops_context.json"
    return backend, context_file


# Detectar rutas
BACKEND_DIR, CONTEXT_FILE = encontrar_backend_dir()

print("="*70)
print("AUTO-DETECCION DE RUTAS")
print("="*70)
print(f"Script ubicado en: {Path(__file__)}")
print(f"Backend detectado: {BACKEND_DIR}")
print(f"Contexto esperado en: {CONTEXT_FILE}")
print(f"Archivo existe? {CONTEXT_FILE.exists()}")
print("="*70)
print()

# ============================================================================
# SERVICIO DE CONTEXTO
# ============================================================================

class ContextService:
    """
    Servicio de contexto MineOPS sin LightRAG
    Usa búsqueda de texto simple en el JSON
    """
    
    def __init__(self):
        """Inicializa el servicio"""
        self.contexto = None
        self.contexts: List[Dict] = []  # Historial de contextos recientes
        self._cargar_contexto()
    
    def _cargar_contexto(self):
        """Carga el contexto desde JSON"""
        if not CONTEXT_FILE.exists():
            logger.warning(f"Contexto no encontrado: {CONTEXT_FILE}")
            print(f"ERROR: Archivo no encontrado")
            print(f"   Esperado en: {CONTEXT_FILE}")
            print()
            print("Archivos en data/:")
            data_dir = BACKEND_DIR / "data"
            if data_dir.exists():
                for item in data_dir.iterdir():
                    print(f"   - {item.name}")
                    if item.is_dir():
                        for subitem in item.iterdir():
                            print(f"     - {subitem.name}")
            else:
                print("   (directorio data/ no existe)")
            return

        try:
            with open(CONTEXT_FILE, 'r', encoding='utf-8') as f:
                self.contexto = json.load(f)
            logger.info("Contexto MineOPS cargado")
            print(f"Contexto MineOPS cargado exitosamente")
            print(f"   Version: {self.contexto.get('metadata', {}).get('version', 'N/A')}")
            print(f"   Terminos: {len(self.contexto.get('vocabulario_global', {}).get('terminos', {}))}")
            print(f"   Tablas: {len(self.contexto.get('tablas_principales', {}))}")
            print()
        except Exception as e:
            logger.error(f"Error cargando contexto: {e}")
            print(f"Error leyendo archivo: {e}")
            self.contexto = None
    
    def definir_termino(self, termino: str) -> str:
        """Define un término técnico MineOPS"""
        if not self.contexto:
            return "Contexto no disponible"
        
        termino_lower = termino.lower().strip()
        
        # Buscar en vocabulario
        vocabulario = self.contexto.get('vocabulario_global', {}).get('terminos', {})
        
        for key, info in vocabulario.items():
            # Comparar clave o alias
            if key.lower() == termino_lower:
                return self._formatear_definicion(info)
            
            # Buscar en alias
            alias = info.get('alias', [])
            if any(a.lower() == termino_lower for a in alias):
                return self._formatear_definicion(info)
        
        return f"No se encontró definición para '{termino}'"
    
    def _formatear_definicion(self, info: dict) -> str:
        """Formatea una definición"""
        respuesta = f"{info['significa']}. "
        
        if 'tipo' in info:
            respuesta += f"Tipo: {info['tipo']}. "
        
        if 'formula' in info:
            respuesta += f"Fórmula: {info['formula']}. "
        
        if 'objetivo' in info:
            respuesta += f"Objetivo: {info['objetivo']}. "
        
        if 'contexto' in info:
            respuesta += f"Contexto: {info['contexto']}. "
        
        return respuesta.strip()
    
    def obtener_tablas_para(self, objetivo: str) -> str:
        """Sugiere tablas para un objetivo"""
        if not self.contexto:
            return "Contexto no disponible"
        
        objetivo_lower = objetivo.lower()
        
        # Buscar en patrones de análisis
        patrones = self.contexto.get('patrones_analisis', {}).get('patrones', {})
        
        for patron_id, patron in patrones.items():
            pregunta = patron.get('pregunta', '').lower()
            # Buscar coincidencias de palabras
            palabras_objetivo = objetivo_lower.split()
            if any(palabra in pregunta for palabra in palabras_objetivo if len(palabra) > 3):
                tablas = ', '.join(patron.get('tablas', []))
                metodo = patron.get('metodo', '')
                return f"Para {objetivo}, consulta: {tablas}. Método: {metodo}"
        
        # Si no hay patrón específico, buscar en tablas principales
        tablas_principales = self.contexto.get('tablas_principales', {})
        sugerencias = []
        
        for tabla_id, tabla in tablas_principales.items():
            uso = tabla.get('uso_principal', '').lower()
            desc = tabla.get('descripcion', '').lower()
            
            # Buscar en uso o descripción
            if any(palabra in uso or palabra in desc for palabra in objetivo_lower.split() if len(palabra) > 3):
                sugerencias.append(f"{tabla_id} ({tabla.get('nombre_es', '')})")
        
        if sugerencias:
            return f"Tablas recomendadas: {', '.join(sugerencias[:5])}"
        
        return "No se encontraron tablas específicas. Consulta: by_equipment_times, shift_states, by_kpi_hora (tablas generales)."
    
    def enriquecer_prompt(self, pregunta: str) -> str:
        """Enriquece un prompt con contexto relevante de forma concisa"""
        if not self.contexto:
            return pregunta
        
        # Términos técnicos MineOPS
        terminos_mineops = [
            'efh', 'tkph', 'time', 'created_at', 'updated_at',
            'payload', 'tonnage', 'material_tonnage',
            'availability', 'utilization', 
            'efectivo', 'disponible',
            'det_noprg', 'det_prg', 
            'm_correctiva', 'm_programada',
            'shift_loads', 'shift_dumps', 'shift_states',
            'by_detail_dumps', 'by_equipment_times', 'by_kpi_hora'
        ]
        
        pregunta_lower = pregunta.lower()
        terminos_encontrados = [t for t in terminos_mineops if t in pregunta_lower]
        
        if not terminos_encontrados:
            return pregunta
        
        # Detectar si es pregunta simple de definición
        es_pregunta_simple = any(palabra in pregunta_lower for palabra in [
            'qué es', 'qué significa', 'define', 'definición', 'significado'
        ])
        
        # Agregar contexto CONCISO para términos encontrados
        contexto_adicional = "\n\n[Contexto técnico para tu respuesta - NO copies este texto, úsalo para entender mejor y responder en tus propias palabras de forma conversacional]:\n"
        
        for termino in terminos_encontrados[:2]:  # Máximo 2 términos
            definicion = self.definir_termino(termino)
            if definicion and "No se encontró" not in definicion:
                # Versión ultra-concisa
                partes = definicion.split('.')[:3]  # Solo primeras 3 oraciones
                definicion_corta = '. '.join(partes) + '.'
                contexto_adicional += f"- {termino}: {definicion_corta}\n"
        
        if es_pregunta_simple:
            contexto_adicional += "\n[IMPORTANTE: Esta es una pregunta simple. Responde de forma DIRECTA y CONVERSACIONAL en 2-3 oraciones máximo. NO uses markdown excesivo, tablas o estructura formal. Habla naturalmente como si explicaras a un colega.]"
        
        if len(contexto_adicional) > 100:
            return pregunta + contexto_adicional
        else:
            return pregunta
    
    def esta_disponible(self) -> bool:
        """Verifica si el servicio está disponible"""
        return self.contexto is not None
    
    def get_estadisticas(self) -> Dict:
        """Obtiene estadísticas del servicio"""
        return {
            'disponible': self.esta_disponible(),
            'ruta_contexto': str(CONTEXT_FILE),
            'existe_contexto': CONTEXT_FILE.exists(),
            'backend_dir': str(BACKEND_DIR)
        }

    def get_recent_context(self, limit: int = 5) -> str:
        """
        Retorna los últimos n contextos de la conversación como string.
        Si no hay historial, retorna resumen del contexto MineOPS disponible.
        """
        if self.contexts:
            recent = self.contexts[-limit:]
            return "\n".join([
                f"- {ctx.get('query', 'N/A')}: {ctx.get('summary', 'N/A')}"
                for ctx in recent
            ])

        # Si no hay historial, dar contexto general del sistema
        if self.contexto:
            tablas = list(self.contexto.get('tablas_principales', {}).keys())[:5]
            return f"Tablas disponibles: {', '.join(tablas)}"

        return ""

    def add_context(self, query: str, summary: str):
        """Agrega un contexto al historial"""
        self.contexts.append({
            'query': query,
            'summary': summary
        })
        # Mantener máximo 20 contextos
        if len(self.contexts) > 20:
            self.contexts = self.contexts[-20:]


# ============================================================================
# INSTANCIA SINGLETON
# ============================================================================

_context_service_instance = None

def get_context_service() -> ContextService:
    """Obtiene la instancia singleton del servicio"""
    global _context_service_instance
    if _context_service_instance is None:
        _context_service_instance = ContextService()
    return _context_service_instance


# ============================================================================
# TESTING
# ============================================================================

def test_context_service():
    """Test del servicio"""
    print("="*70)
    print("TEST DEL SERVICIO DE CONTEXTO")
    print("="*70)
    print()

    service = ContextService()

    if not service.esta_disponible():
        print("Servicio no disponible")
        print()
        print("DIAGNOSTICO:")
        print(f"   Backend: {BACKEND_DIR}")
        print(f"   Archivo esperado: {CONTEXT_FILE}")
        print(f"   Existe: {CONTEXT_FILE.exists()}")
        print()
        print("SOLUCION:")
        print("   1. Verifica que el archivo existe en:")
        print(f"      {CONTEXT_FILE}")
        print("   2. O copialo:")
        print(f"      copy Downloads\\mineops_context.json {BACKEND_DIR / 'data' / 'context' / ''}")
        return

    print("Servicio disponible")
    print()

    # Test 1
    print("Test 1: Definir 'efh'")
    print(service.definir_termino("efh"))
    print()

    # Test 2
    print("Test 2: Definir 'det_noprg'")
    print(service.definir_termino("det_noprg"))
    print()

    # Test 3
    print("Test 3: Tablas para 'disponibilidad'")
    print(service.obtener_tablas_para("analizar disponibilidad"))
    print()

    # Test 4
    print("Test 4: Enriquecer prompt")
    pregunta = "¿Por qué el det_noprg es alto?"
    enriquecida = service.enriquecer_prompt(pregunta)
    print(f"Original ({len(pregunta)} chars): {pregunta}")
    print(f"Enriquecida ({len(enriquecida)} chars)")
    if len(enriquecida) > len(pregunta):
        print("Contexto agregado correctamente")
    print()
    
    # Test 5
    print("Test 5: Estadisticas")
    stats = service.get_estadisticas()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()
    
    print("="*70)
    print("TODOS LOS TESTS COMPLETADOS")
    print("="*70)


if __name__ == "__main__":
    test_context_service()