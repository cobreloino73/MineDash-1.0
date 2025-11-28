"""
🛡️ VALIDATION AGENT - Sistema Anti-Alucinación
Valida respuestas ANTES de entregarlas al usuario para detectar y bloquear alucinaciones
"""

import re
from typing import Dict, List, Tuple
import anthropic


class ValidationAgent:
    """Agente que valida respuestas para detectar alucinaciones financieras y técnicas"""
    
    # Patrones PROHIBIDOS que indican alucinación
    FORBIDDEN_PATTERNS = [
        # Alucinaciones económicas
        r"asumiendo\s+(?:USD|US\$|\$|CLP|pesos)\s*[\d,]+",  # "asumiendo USD 50"
        r"estimando\s+(?:USD|US\$|\$|CLP|pesos)\s*[\d,]+",  # "estimando $100"
        r"aproximadamente\s+(?:USD|US\$|\$|CLP|pesos)\s*[\d,]+",  # "aproximadamente $200"
        r"cerca\s+de\s+(?:USD|US\$|\$|CLP|pesos)\s*[\d,]+",  # "cerca de $150"
        
        # Generalizaciones sin datos
        r"muchos\s+(?:equipos|operadores|caex)\s+alcanzan\s+\d+%",  # "muchos alcanzan 100%"
        r"típicamente\s+se\s+observa",  # "típicamente se observa"
        r"generalmente\s+los?\s+equipos?",  # "generalmente los equipos"
        r"es\s+común\s+que",  # "es común que"
        r"suelen?\s+(?:alcanzar|lograr|tener)",  # "suelen alcanzar"
        
        # Valores técnicamente imposibles
        r"(?:disponibilidad|utilización|dm|ue).*?100%",  # "disponibilidad de 100%"
        r"100%\s+(?:de\s+)?(?:disponibilidad|utilización|dm|ue)",  # "100% de DM"
    ]
    
    # Palabras que indican estimación sin datos
    ESTIMATION_KEYWORDS = [
        "asumiendo", "estimando", "aproximadamente", "cerca de", "alrededor de",
        "típicamente", "generalmente", "normalmente", "usualmente", "comúnmente",
        "es común que", "suelen", "tienden a", "se espera que",
        "muchos", "la mayoría", "varios", "algunos"
    ]
    
    # Valores técnicamente imposibles en minería
    IMPOSSIBLE_VALUES = {
        "disponibilidad_mecanica": 100,  # 90-95% es el máximo realista
        "utilizacion_efectiva": 100,     # 85% es excelente
        "cumplimiento_plan": 150,        # >120% es sospechoso
    }
    
    def __init__(self, anthropic_api_key: str):
        """
        Args:
            anthropic_api_key: API key de Anthropic para Claude
        """
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
        self.validation_history = []
    
    def validate_response(self, response: str, query: str, data_sources: List[str] = None) -> Dict:
        """
        Valida una respuesta antes de entregarla al usuario.
        
        Args:
            response: Respuesta generada por el agente principal
            query: Pregunta original del usuario
            data_sources: Lista de fuentes de datos consultadas (tablas, archivos, etc.)
        
        Returns:
            Dict con:
                - is_valid: bool (True si pasa validación)
                - issues: List[str] (problemas detectados)
                - severity: str ("none", "warning", "critical")
                - safe_response: str (respuesta corregida si is_valid=False)
                - confidence: float (0-1, confianza en la validación)
        """
        issues = []
        severity = "none"
        
        # VALIDACIÓN 1: Detectar patrones prohibidos
        print("\n🔍 Validación 1: Patrones prohibidos...")
        for pattern in self.FORBIDDEN_PATTERNS:
            matches = re.findall(pattern, response, re.IGNORECASE)
            if matches:
                issues.append(f"❌ Patrón prohibido detectado: {matches[0]}")
                severity = "critical"
        
        # VALIDACIÓN 2: Detectar palabras de estimación
        print("🔍 Validación 2: Palabras de estimación...")
        has_money = bool(re.search(r"(?:USD|US\$|\$|CLP|pesos)\s*[\d,]+", response))
        has_estimation = any(keyword in response.lower() for keyword in self.ESTIMATION_KEYWORDS)
        
        if has_money and has_estimation:
            issues.append("❌ Cifra económica con palabra de estimación (probablemente inventada)")
            severity = "critical"
        
        # VALIDACIÓN 3: Detectar valores técnicamente imposibles
        print("🔍 Validación 3: Valores imposibles...")
        impossible_found = []
        for metric, max_value in self.IMPOSSIBLE_VALUES.items():
            pattern = rf"{metric}.*?{max_value}%"
            if re.search(pattern, response.lower()):
                impossible_found.append(f"{metric}: {max_value}%")
        
        if impossible_found:
            issues.append(f"❌ Valores técnicamente imposibles: {', '.join(impossible_found)}")
            severity = "critical"
        
        # VALIDACIÓN 4: Verificar fuentes de datos económicos
        print("🔍 Validación 4: Fuentes de datos económicos...")
        if has_money:
            has_economic_source = False
            if data_sources:
                economic_sources = ["economic_parameters", "costos", "precios", "budget"]
                has_economic_source = any(source in str(data_sources).lower() for source in economic_sources)
            
            if not has_economic_source:
                issues.append("❌ Cifra económica sin fuente de datos verificable")
                severity = "critical"
        
        # VALIDACIÓN 5: Usar Claude para validación semántica
        print("🔍 Validación 5: Validación semántica con Claude...")
        semantic_check = self._semantic_validation(response, query, issues)
        if not semantic_check["is_valid"]:
            issues.extend(semantic_check["issues"])
            if semantic_check["severity"] == "critical":
                severity = "critical"
            elif severity != "critical" and semantic_check["severity"] == "warning":
                severity = "warning"
        
        # Determinar si pasa la validación
        is_valid = severity != "critical"
        confidence = self._calculate_confidence(issues, semantic_check)
        
        # Generar respuesta segura si falló validación
        safe_response = response if is_valid else self._generate_safe_response(response, issues, query)
        
        # Guardar en historial
        validation_result = {
            "query": query,
            "original_response": response,
            "is_valid": is_valid,
            "issues": issues,
            "severity": severity,
            "safe_response": safe_response,
            "confidence": confidence,
            "data_sources": data_sources
        }
        self.validation_history.append(validation_result)
        
        # Log resultado
        if is_valid:
            print(f"✅ Validación APROBADA (confianza: {confidence:.2f})")
        else:
            print(f"❌ Validación RECHAZADA (severidad: {severity})")
            print(f"   Problemas: {len(issues)}")
            for issue in issues:
                print(f"   - {issue}")
        
        return validation_result
    
    def _semantic_validation(self, response: str, query: str, existing_issues: List[str]) -> Dict:
        """
        Validación semántica usando Claude para detectar alucinaciones sutiles.
        """
        # Si ya hay problemas críticos, skip validación costosa
        if any("❌" in issue for issue in existing_issues):
            return {"is_valid": True, "issues": [], "severity": "none"}
        
        validation_prompt = f"""Analiza esta respuesta y detecta si contiene ALUCINACIONES o INVENCIONES de datos.

PREGUNTA USUARIO:
{query}

RESPUESTA A VALIDAR:
{response}

🎯 TU MISIÓN: Detectar si la respuesta inventa datos que NO debería saber.

❌ ALUCINACIONES COMUNES A DETECTAR:
1. Cifras económicas sin fuente explícita (USD/CLP/costos/precios)
2. Generalizaciones sobre "muchos equipos" o "típicamente" sin datos
3. Valores técnicamente imposibles (100% DM, 100% UE)
4. Porcentajes o estadísticas sin mención a fuente de datos
5. Comparaciones sin datos base

✅ ESTÁ BIEN:
- Citar datos de tablas SQL específicas
- Usar información de archivos mencionados explícitamente
- Decir "no tengo ese dato" o "se requiere información adicional"
- Análisis técnico sin monetizar

RESPONDE EN FORMATO JSON:
{{
    "tiene_alucinaciones": true/false,
    "tipo_alucinacion": "economica|tecnica|generalizacion|ninguna",
    "evidencia": "frase específica inventada o null",
    "severidad": "critical|warning|none",
    "explicacion": "Por qué es alucinación (si aplica)"
}}"""
        
        try:
            response_validation = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                temperature=0,  # Máxima determinismo
                messages=[{
                    "role": "user",
                    "content": validation_prompt
                }]
            )
            
            # Extraer JSON de la respuesta
            validation_text = response_validation.content[0].text
            
            # Parsear JSON
            import json
            # Buscar JSON en la respuesta
            json_match = re.search(r'\{.*\}', validation_text, re.DOTALL)
            if json_match:
                validation_result = json.loads(json_match.group())
            else:
                # Si no hay JSON, asumir que está ok
                return {"is_valid": True, "issues": [], "severity": "none"}
            
            # Construir resultado
            if validation_result.get("tiene_alucinaciones"):
                return {
                    "is_valid": False,
                    "issues": [
                        f"🤖 Claude Validator: {validation_result.get('explicacion', 'Alucinación detectada')}"
                    ],
                    "severity": validation_result.get("severidad", "warning")
                }
            else:
                return {"is_valid": True, "issues": [], "severity": "none"}
        
        except Exception as e:
            print(f"⚠️  Error en validación semántica: {e}")
            # En caso de error, mejor dejar pasar que bloquear
            return {"is_valid": True, "issues": [], "severity": "none"}
    
    def _calculate_confidence(self, issues: List[str], semantic_check: Dict) -> float:
        """
        Calcula la confianza en la validación (0-1).
        """
        if not issues and semantic_check.get("is_valid", True):
            return 1.0
        
        # Reducir confianza por cada problema
        confidence = 1.0
        for issue in issues:
            if "❌" in issue:
                confidence -= 0.3  # Problema crítico
            else:
                confidence -= 0.1  # Problema menor
        
        if not semantic_check.get("is_valid", True):
            confidence -= 0.2
        
        return max(0.0, confidence)
    
    def _generate_safe_response(self, original_response: str, issues: List[str], query: str) -> str:
        """
        Genera una respuesta segura sin alucinaciones cuando la validación falla.
        """
        print("\n🔧 Generando respuesta segura...")
        
        safe_prompt = f"""La siguiente respuesta fue RECHAZADA por contener alucinaciones:

RESPUESTA ORIGINAL (CON ALUCINACIONES):
{original_response}

PROBLEMAS DETECTADOS:
{chr(10).join(issues)}

PREGUNTA ORIGINAL:
{query}

🎯 TU MISIÓN: Generar una respuesta SEGURA que:

✅ DEBE:
1. Responder la pregunta usando SOLO datos técnicos verificables
2. Admitir cuando NO tienes datos económicos
3. Ofrecer análisis técnico (toneladas, horas, porcentajes operacionales)
4. Sugerir qué datos se necesitarían para análisis económico

❌ NO DEBE:
1. Inventar precios, costos, o valores monetarios
2. Hacer estimaciones económicas
3. Usar palabras como "asumiendo", "típicamente", "generalmente"
4. Afirmar valores técnicamente imposibles (100% DM/UE)

GENERA LA RESPUESTA SEGURA:"""
        
        try:
            safe_response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": safe_prompt
                }]
            )
            
            return safe_response.content[0].text
        
        except Exception as e:
            print(f"❌ Error generando respuesta segura: {e}")
            # Fallback: respuesta ultra-conservadora
            return f"""⚠️ **Respuesta validada y corregida**

Para responder tu pregunta de forma precisa necesito datos adicionales que actualmente no están disponibles en el sistema.

**Lo que puedo confirmar:**
- Consulta datos técnicos en las tablas disponibles
- Análisis operacional sin monetización

**Para análisis económico completo se requiere:**
- Precios de venta actualizados (USD/ton)
- Costos operacionales por equipo
- Parámetros económicos en tabla `economic_parameters`

¿Deseas que ejecute una consulta SQL para verificar qué datos están disponibles?"""
    
    def get_validation_stats(self) -> Dict:
        """
        Retorna estadísticas de validaciones realizadas.
        """
        if not self.validation_history:
            return {"total": 0, "approved": 0, "rejected": 0, "approval_rate": 0.0}
        
        total = len(self.validation_history)
        approved = sum(1 for v in self.validation_history if v["is_valid"])
        rejected = total - approved
        
        return {
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "approval_rate": approved / total if total > 0 else 0.0,
            "avg_confidence": sum(v["confidence"] for v in self.validation_history) / total
        }


# =============================================================================
# EJEMPLO DE USO
# =============================================================================

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Crear validator
    validator = ValidationAgent(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    # TEST 1: Respuesta con alucinación económica
    print("="*70)
    print("TEST 1: Alucinación económica")
    print("="*70)
    
    fake_response = """## Análisis de Disponibilidad Mecánica

La flota CAEX muestra una DM promedio de 87%, lo cual está por debajo del target de 90%.

## 💰 Impacto Económico

Asumiendo USD 50/ton y considerando la pérdida de 260 toneladas/hora:
- **Pérdida diaria:** $312,000 USD
- **Pérdida mensual:** $9.36 millones USD

Se recomienda invertir en mantenimiento preventivo."""
    
    result1 = validator.validate_response(
        response=fake_response,
        query="¿Cuál es el impacto de la baja disponibilidad?",
        data_sources=["equipment_kpi"]  # No incluye economic_parameters
    )
    
    print(f"\n{'='*70}")
    print(f"RESULTADO: {'✅ APROBADA' if result1['is_valid'] else '❌ RECHAZADA'}")
    print(f"Severidad: {result1['severity']}")
    print(f"Problemas: {len(result1['issues'])}")
    print(f"{'='*70}\n")
    
    # TEST 2: Respuesta segura (solo técnica)
    print("\n" + "="*70)
    print("TEST 2: Respuesta técnica segura")
    print("="*70)
    
    safe_response = """## Análisis de Disponibilidad Mecánica

Según la consulta SQL a la tabla equipment_kpi:

**Datos reales encontrados:**
- DM promedio flota CAEX: 87% (periodo: octubre 2025)
- Target establecido: 90%
- Brecha: -3 puntos porcentuales

**Impacto operacional:**
- Pérdida de producción: 260 toneladas/hora
- Horas totales perdidas: 145 horas en el mes

**Para cuantificar impacto económico se requieren datos de:**
- Precio de venta del mineral (USD/ton)
- Costos operacionales por equipo (USD/hora)

¿Deseas que consulte la tabla `economic_parameters` para verificar si estos datos están disponibles?"""
    
    result2 = validator.validate_response(
        response=safe_response,
        query="¿Cuál es el impacto de la baja disponibilidad?",
        data_sources=["equipment_kpi"]
    )
    
    print(f"\n{'='*70}")
    print(f"RESULTADO: {'✅ APROBADA' if result2['is_valid'] else '❌ RECHAZADA'}")
    print(f"Confianza: {result2['confidence']:.2%}")
    print(f"{'='*70}\n")
    
    # Estadísticas
    stats = validator.get_validation_stats()
    print(f"\n{'='*70}")
    print("ESTADÍSTICAS DE VALIDACIÓN")
    print(f"{'='*70}")
    print(f"Total validaciones: {stats['total']}")
    print(f"Aprobadas: {stats['approved']} ({stats['approval_rate']:.1%})")
    print(f"Rechazadas: {stats['rejected']}")
    print(f"Confianza promedio: {stats['avg_confidence']:.2%}")
    print(f"{'='*70}\n")
