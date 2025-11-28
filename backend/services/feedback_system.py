"""
Feedback System - Aprendizaje por Refuerzo
Sistema que aprende de las validaciones del usuario
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import asyncio

class FeedbackSystem:
    """
    Sistema de feedback para aprendizaje continuo
    El usuario valida insights y el sistema aprende
    """
    
    def __init__(self):
        self.feedback_dir = Path("backend/data/feedback")
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        
        self.stats_file = self.feedback_dir / "learning_stats.json"
        self.history_file = self.feedback_dir / "feedback_history.json"
    
    async def record_feedback(
        self,
        insight_type: str,
        insight_data: Dict,
        user_validation: bool,
        corrections: Dict = None,
        user_comment: str = None
    ) -> Dict[str, Any]:
        """
        Registra feedback del usuario sobre un insight
        
        Args:
            insight_type: "alerta", "recomendacion", "prediccion", "plan_extraction"
            insight_data: Datos del insight generado
            user_validation: True si usuario validó como correcto
            corrections: Dict con correcciones si las hubo
            user_comment: Comentario opcional del usuario
            
        Returns:
            Resultado del aprendizaje
        """
        
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "insight_type": insight_type,
            "insight_data": insight_data,
            "user_validation": user_validation,
            "corrections": corrections or {},
            "user_comment": user_comment,
            "learned": False
        }
        
        # Guardar en historial
        await self._save_to_history(feedback_entry)
        
        # Si hay correcciones, aprender
        if corrections and not user_validation:
            learning_result = await self._learn_from_correction(
                insight_type,
                insight_data,
                corrections
            )
            feedback_entry["learned"] = True
            feedback_entry["learning_result"] = learning_result
        
        # Actualizar estadísticas
        await self._update_stats(insight_type, user_validation)
        
        return {
            "success": True,
            "feedback_id": feedback_entry["timestamp"],
            "learned": feedback_entry["learned"],
            "message": "Gracias! El sistema aprendió de tu corrección" if feedback_entry["learned"] else "Validación registrada"
        }
    
    async def _save_to_history(self, feedback_entry: Dict):
        """Guarda feedback en historial"""
        try:
            # Leer historial existente
            history = []
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            
            # Agregar nuevo feedback
            history.append(feedback_entry)
            
            # Guardar (mantener últimos 1000)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history[-1000:], f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"⚠️ Error guardando historial: {e}")
    
    async def _learn_from_correction(
        self,
        insight_type: str,
        original_data: Dict,
        corrections: Dict
    ) -> Dict:
        """
        Aprende de las correcciones del usuario
        Ajusta parámetros y estrategias
        """
        
        learning_result = {
            "timestamp": datetime.now().isoformat(),
            "insight_type": insight_type,
            "adjustments": []
        }
        
        # Analizar correcciones según tipo
        if insight_type == "plan_extraction":
            # Usuario corrigió valores de un plan
            adjustments = await self._adjust_extraction_strategy(
                original_data,
                corrections
            )
            learning_result["adjustments"] = adjustments
        
        elif insight_type == "alerta":
            # Usuario corrigió umbrales de alerta
            adjustments = await self._adjust_alert_thresholds(
                original_data,
                corrections
            )
            learning_result["adjustments"] = adjustments
        
        elif insight_type == "prediccion":
            # Usuario corrigió predicción
            adjustments = await self._adjust_prediction_model(
                original_data,
                corrections
            )
            learning_result["adjustments"] = adjustments
        
        return learning_result
    
    async def _adjust_extraction_strategy(
        self,
        original: Dict,
        corrections: Dict
    ) -> List[Dict]:
        """
        Ajusta estrategia de extracción basándose en correcciones
        """
        adjustments = []
        
        # Si usuario corrigió tonelaje
        if "tonelaje_mensual" in corrections:
            original_val = original.get("tonelaje_mensual", 0)
            corrected_val = corrections["tonelaje_mensual"]
            
            ratio = corrected_val / original_val if original_val > 0 else 1
            
            adjustment = {
                "parameter": "tonelaje_mensual",
                "original": original_val,
                "corrected": corrected_val,
                "adjustment_factor": ratio,
                "note": f"Usuario ajustó tonelaje en {ratio:.2f}x"
            }
            adjustments.append(adjustment)
        
        # Si usuario corrigió disponibilidad
        if "disponibilidad_meta" in corrections:
            adjustment = {
                "parameter": "disponibilidad_meta",
                "original": original.get("disponibilidad_meta"),
                "corrected": corrections["disponibilidad_meta"],
                "note": "Usuario ajustó disponibilidad meta"
            }
            adjustments.append(adjustment)
        
        # Guardar ajustes para uso futuro
        await self._save_learned_adjustments(adjustments)
        
        return adjustments
    
    async def _adjust_alert_thresholds(
        self,
        original: Dict,
        corrections: Dict
    ) -> List[Dict]:
        """
        Ajusta umbrales de alertas
        """
        adjustments = []
        
        # Si usuario dijo "no es crítico" cuando sistema dijo "crítico"
        if "severidad" in corrections:
            adjustment = {
                "parameter": "alert_threshold",
                "original_severity": original.get("tipo"),
                "corrected_severity": corrections["severidad"],
                "note": "Usuario ajustó severidad de alerta"
            }
            adjustments.append(adjustment)
        
        return adjustments
    
    async def _adjust_prediction_model(
        self,
        original: Dict,
        corrections: Dict
    ) -> List[Dict]:
        """
        Ajusta modelo de predicción
        """
        adjustments = []
        
        if "valor_proyectado" in corrections:
            adjustment = {
                "parameter": "prediction_accuracy",
                "original": original.get("valor_proyectado"),
                "corrected": corrections["valor_proyectado"],
                "note": "Usuario ajustó predicción"
            }
            adjustments.append(adjustment)
        
        return adjustments
    
    async def _save_learned_adjustments(self, adjustments: List[Dict]):
        """Guarda ajustes aprendidos para uso futuro"""
        adjustments_file = self.feedback_dir / "learned_adjustments.json"
        
        try:
            learned = []
            if adjustments_file.exists():
                with open(adjustments_file, 'r', encoding='utf-8') as f:
                    learned = json.load(f)
            
            learned.extend(adjustments)
            
            with open(adjustments_file, 'w', encoding='utf-8') as f:
                json.dump(learned[-100:], f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"⚠️ Error guardando ajustes: {e}")
    
    async def _update_stats(self, insight_type: str, validated: bool):
        """Actualiza estadísticas de aprendizaje"""
        try:
            stats = {}
            if self.stats_file.exists():
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    stats = json.load(f)
            
            # Inicializar si no existe
            if insight_type not in stats:
                stats[insight_type] = {
                    "total": 0,
                    "validated": 0,
                    "corrected": 0,
                    "accuracy": 0.0
                }
            
            # Actualizar contadores
            stats[insight_type]["total"] += 1
            if validated:
                stats[insight_type]["validated"] += 1
            else:
                stats[insight_type]["corrected"] += 1
            
            # Calcular accuracy
            total = stats[insight_type]["total"]
            validated_count = stats[insight_type]["validated"]
            stats[insight_type]["accuracy"] = (validated_count / total * 100) if total > 0 else 0
            
            # Guardar
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"⚠️ Error actualizando stats: {e}")
    
    async def get_learning_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de aprendizaje del sistema"""
        try:
            if self.stats_file.exists():
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"⚠️ Error leyendo stats: {e}")
            return {}
    
    async def get_feedback_history(self, limit: int = 50) -> List[Dict]:
        """Obtiene historial de feedback"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                return history[-limit:]
            return []
        except Exception as e:
            print(f"⚠️ Error leyendo historial: {e}")
            return []


def get_feedback_system():
    """Obtiene instancia del sistema de feedback"""
    return FeedbackSystem()