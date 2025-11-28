"""
MineDash AI v2.0 - World Model Module
FASE 2: Simulaciones Operacionales

Capacidades:
- Simular fallas de equipos y su impacto
- Optimizar calendarios de mantenimiento
- Predecir cuellos de botella
- Escenarios "qué pasaría si"
- Optimización de flotas (similar a Modular/Hexagon)
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import sqlite3
from pathlib import Path


@dataclass
class Equipment:
    """Modelo de equipo minero"""
    id: str
    type: str  # 'loader', 'truck', 'drill'
    capacity: float  # toneladas o metros
    availability: float  # 0-1
    utilization: float  # 0-1
    mtbf: float  # Mean Time Between Failures (horas)
    mttr: float  # Mean Time To Repair (horas)
    operating_hours: float
    last_maintenance: datetime


@dataclass
class SimulationResult:
    """Resultado de simulación"""
    scenario: str
    metrics: Dict[str, float]
    recommendations: List[str]
    risk_level: str  # 'low', 'medium', 'high'
    confidence: float  # 0-1


class MiningWorldModel:
    """
    Modelo de Mundo para Operaciones Mineras
    
    Simula el sistema productivo completo y permite predecir
    el impacto de eventos, optimizar recursos y tomar decisiones.
    """
    
    def __init__(self, db_path: str = "minedash.db"):
        """
        Inicializar World Model
        
        Args:
            db_path: Ruta a base de datos operacional
        """
        self.db_path = db_path
        self.equipment_cache = {}
        self.simulation_history = []
        
        # Parámetros del modelo (calibrables)
        self.params = {
            # Factores de productividad
            'loader_productivity_base': 1000,  # ton/hora
            'truck_productivity_base': 120,  # ton/ciclo
            'drill_productivity_base': 50,  # metros/turno
            
            # Factores de degradación
            'equipment_age_factor': 0.02,  # % por año
            'maintenance_boost': 1.15,  # multiplicador post-mantención
            
            # Disponibilidad mecánica típica
            'loader_availability': 0.85,
            'truck_availability': 0.80,
            'drill_availability': 0.75,
            
            # Costos operacionales (USD/hora)
            'loader_cost': 250,
            'truck_cost': 180,
            'drill_cost': 200,
            
            # Costos de downtime
            'production_loss_per_hour': 50000,  # USD/hora de producción perdida
            
            # Umbrales de alerta
            'utilization_low': 0.60,
            'utilization_high': 0.95,
            'availability_critical': 0.70
        }
    
    async def simulate_equipment_failure(
        self,
        equipment_id: str,
        failure_duration_hours: float,
        shift: str = 'A'
    ) -> SimulationResult:
        """
        Simular falla de un equipo y calcular impacto
        
        Args:
            equipment_id: ID del equipo
            failure_duration_hours: Duración de la falla en horas
            shift: Turno afectado
            
        Returns:
            Resultado de simulación con métricas e impacto
        """
        try:
            # 1. Obtener información del equipo
            equipment = await self._get_equipment(equipment_id)
            if not equipment:
                return SimulationResult(
                    scenario=f"Falla de {equipment_id}",
                    metrics={},
                    recommendations=[],
                    risk_level="high",
                    confidence=0.0
                )
            
            # 2. Calcular impacto en producción
            hourly_production = self._calculate_equipment_productivity(equipment)
            production_loss = hourly_production * failure_duration_hours
            
            # 3. Calcular impacto económico
            operational_cost = self.params[f"{equipment.type}_cost"] * failure_duration_hours
            production_cost = production_loss * self.params['production_loss_per_hour'] / 1000
            total_cost = operational_cost + production_cost
            
            # 4. Analizar disponibilidad de equipos backup
            backup_available = await self._check_backup_equipment(equipment.type, shift)
            
            # 5. Calcular nivel de riesgo
            risk_level = self._assess_risk(
                production_loss=production_loss,
                backup_available=backup_available,
                duration=failure_duration_hours
            )
            
            # 6. Generar recomendaciones
            recommendations = self._generate_failure_recommendations(
                equipment=equipment,
                backup_available=backup_available,
                production_loss=production_loss,
                duration=failure_duration_hours
            )
            
            # 7. Compilar métricas
            metrics = {
                'production_loss_tons': round(production_loss, 2),
                'operational_cost_usd': round(operational_cost, 2),
                'production_cost_usd': round(production_cost, 2),
                'total_cost_usd': round(total_cost, 2),
                'duration_hours': failure_duration_hours,
                'backup_units_available': len(backup_available),
                'impact_severity': self._calculate_severity(production_loss)
            }
            
            return SimulationResult(
                scenario=f"Falla de {equipment.type} {equipment_id} por {failure_duration_hours}h",
                metrics=metrics,
                recommendations=recommendations,
                risk_level=risk_level,
                confidence=0.85
            )
            
        except Exception as e:
            return SimulationResult(
                scenario=f"Error en simulación: {str(e)}",
                metrics={},
                recommendations=[],
                risk_level="unknown",
                confidence=0.0
            )
    
    async def optimize_maintenance_schedule(
        self,
        equipment_type: Optional[str] = None,
        horizon_days: int = 30
    ) -> Dict[str, Any]:
        """
        Optimizar calendario de mantenimiento preventivo
        
        Args:
            equipment_type: Tipo de equipo (None = todos)
            horizon_days: Horizonte de planificación en días
            
        Returns:
            Calendario optimizado con fechas y prioridades
        """
        try:
            # 1. Obtener todos los equipos
            equipment_list = await self._get_all_equipment(equipment_type)
            
            # 2. Calcular prioridad de mantenimiento
            maintenance_plan = []
            
            for eq in equipment_list:
                # Calcular probabilidad de falla
                failure_prob = self._calculate_failure_probability(eq)
                
                # Calcular impacto de downtime
                impact_score = self._calculate_equipment_productivity(eq) * 24  # impacto diario
                
                # Prioridad = Probabilidad × Impacto
                priority = failure_prob * impact_score
                
                # Fecha sugerida de mantenimiento
                days_until_maintenance = self._calculate_optimal_maintenance_day(
                    eq, failure_prob, horizon_days
                )
                
                maintenance_plan.append({
                    'equipment_id': eq.id,
                    'equipment_type': eq.type,
                    'priority': round(priority, 2),
                    'failure_probability': round(failure_prob, 3),
                    'impact_score': round(impact_score, 2),
                    'suggested_date': (datetime.now() + timedelta(days=days_until_maintenance)).strftime('%Y-%m-%d'),
                    'days_until': days_until_maintenance,
                    'reason': self._get_maintenance_reason(eq, failure_prob)
                })
            
            # 3. Ordenar por prioridad
            maintenance_plan.sort(key=lambda x: x['priority'], reverse=True)
            
            # 4. Generar recomendaciones generales
            recommendations = self._generate_maintenance_recommendations(maintenance_plan)
            
            # 5. Calcular estadísticas
            stats = {
                'total_equipment': len(maintenance_plan),
                'high_priority': len([m for m in maintenance_plan if m['priority'] > 5000]),
                'medium_priority': len([m for m in maintenance_plan if 1000 < m['priority'] <= 5000]),
                'low_priority': len([m for m in maintenance_plan if m['priority'] <= 1000]),
                'avg_failure_prob': round(np.mean([m['failure_probability'] for m in maintenance_plan]), 3)
            }
            
            return {
                'maintenance_plan': maintenance_plan,
                'recommendations': recommendations,
                'statistics': stats,
                'horizon_days': horizon_days,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'maintenance_plan': [],
                'recommendations': []
            }
    
    async def predict_bottlenecks(
        self,
        target_production: float,
        shift: str = 'A'
    ) -> Dict[str, Any]:
        """
        Predecir cuellos de botella operacionales
        
        Args:
            target_production: Meta de producción (toneladas/turno)
            shift: Turno a analizar
            
        Returns:
            Análisis de cuellos de botella y recomendaciones
        """
        try:
            # 1. Obtener capacidad actual de cada etapa
            loaders = await self._get_all_equipment('loader')
            trucks = await self._get_all_equipment('truck')
            drills = await self._get_all_equipment('drill')
            
            # 2. Calcular capacidad teórica de cada etapa
            loader_capacity = sum([
                self._calculate_equipment_productivity(eq) * 8  # 8 horas/turno
                for eq in loaders if eq.availability > 0.5
            ])
            
            truck_capacity = sum([
                self._calculate_equipment_productivity(eq) * 8
                for eq in trucks if eq.availability > 0.5
            ])
            
            # 3. Identificar cuellos de botella
            bottlenecks = []
            
            if loader_capacity < target_production:
                bottlenecks.append({
                    'stage': 'Carguío',
                    'current_capacity': round(loader_capacity, 2),
                    'target': target_production,
                    'deficit': round(target_production - loader_capacity, 2),
                    'severity': 'high' if target_production - loader_capacity > target_production * 0.2 else 'medium',
                    'equipment_count': len(loaders),
                    'avg_availability': round(np.mean([eq.availability for eq in loaders]), 3)
                })
            
            if truck_capacity < target_production:
                bottlenecks.append({
                    'stage': 'Transporte',
                    'current_capacity': round(truck_capacity, 2),
                    'target': target_production,
                    'deficit': round(target_production - truck_capacity, 2),
                    'severity': 'high' if target_production - truck_capacity > target_production * 0.2 else 'medium',
                    'equipment_count': len(trucks),
                    'avg_availability': round(np.mean([eq.availability for eq in trucks]), 3)
                })
            
            # 4. Generar recomendaciones específicas
            recommendations = []
            for bottleneck in bottlenecks:
                recommendations.extend(self._generate_bottleneck_recommendations(bottleneck))
            
            # 5. Calcular ratio de capacidad vs demanda
            capacity_ratio = min(loader_capacity, truck_capacity) / target_production
            
            return {
                'target_production': target_production,
                'shift': shift,
                'bottlenecks': bottlenecks,
                'recommendations': recommendations,
                'capacity_ratio': round(capacity_ratio, 3),
                'status': 'ok' if capacity_ratio >= 1.0 else 'bottleneck_detected',
                'equipment_summary': {
                    'loaders': {
                        'count': len(loaders),
                        'capacity': round(loader_capacity, 2),
                        'avg_availability': round(np.mean([eq.availability for eq in loaders]), 3)
                    },
                    'trucks': {
                        'count': len(trucks),
                        'capacity': round(truck_capacity, 2),
                        'avg_availability': round(np.mean([eq.availability for eq in trucks]), 3)
                    }
                }
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'bottlenecks': [],
                'recommendations': []
            }
    
    async def simulate_whatif_scenario(
        self,
        scenario_type: str,
        parameters: Dict[str, Any]
    ) -> SimulationResult:
        """
        Simular escenario "qué pasaría si"
        
        Args:
            scenario_type: Tipo de escenario ('add_equipment', 'change_shift', 'maintenance_window', etc.)
            parameters: Parámetros específicos del escenario
            
        Returns:
            Resultado de simulación
        """
        try:
            if scenario_type == 'add_equipment':
                return await self._simulate_add_equipment(parameters)
            
            elif scenario_type == 'change_shift':
                return await self._simulate_shift_change(parameters)
            
            elif scenario_type == 'maintenance_window':
                return await self._simulate_maintenance_window(parameters)
            
            elif scenario_type == 'production_increase':
                return await self._simulate_production_increase(parameters)
            
            else:
                return SimulationResult(
                    scenario=f"Escenario desconocido: {scenario_type}",
                    metrics={},
                    recommendations=[],
                    risk_level="unknown",
                    confidence=0.0
                )
        
        except Exception as e:
            return SimulationResult(
                scenario=f"Error: {str(e)}",
                metrics={},
                recommendations=[],
                risk_level="unknown",
                confidence=0.0
            )
    
    # ========================================================================
    # MÉTODOS PRIVADOS - CÁLCULOS Y UTILIDADES
    # ========================================================================
    
    async def _get_equipment(self, equipment_id: str) -> Optional[Equipment]:
        """Obtener información de un equipo específico"""
        # Implementación simplificada - en producción leer de BD
        return Equipment(
            id=equipment_id,
            type='loader',
            capacity=1000,
            availability=0.85,
            utilization=0.75,
            mtbf=120,
            mttr=4,
            operating_hours=5000,
            last_maintenance=datetime.now() - timedelta(days=30)
        )
    
    async def _get_all_equipment(self, equipment_type: Optional[str] = None) -> List[Equipment]:
        """Obtener todos los equipos (opcionalmente filtrados por tipo)"""
        # Implementación simplificada
        equipment = []
        for i in range(5):
            eq_type = equipment_type or ('loader' if i < 2 else 'truck')
            equipment.append(Equipment(
                id=f"{eq_type}_{i+1:03d}",
                type=eq_type,
                capacity=1000 if eq_type == 'loader' else 120,
                availability=np.random.uniform(0.70, 0.95),
                utilization=np.random.uniform(0.60, 0.90),
                mtbf=np.random.uniform(100, 150),
                mttr=np.random.uniform(2, 6),
                operating_hours=np.random.uniform(4000, 6000),
                last_maintenance=datetime.now() - timedelta(days=np.random.randint(1, 60))
            ))
        return equipment
    
    def _calculate_equipment_productivity(self, equipment: Equipment) -> float:
        """Calcular productividad actual de un equipo (ton/hora o m/hora)"""
        base_productivity = self.params[f"{equipment.type}_productivity_base"]
        
        # Aplicar factores de degradación
        age_years = equipment.operating_hours / 8760  # horas por año
        age_factor = 1 - (self.params['equipment_age_factor'] * age_years)
        
        # Aplicar disponibilidad y utilización
        effective_productivity = (
            base_productivity *
            age_factor *
            equipment.availability *
            equipment.utilization
        )
        
        return max(effective_productivity, 0)
    
    def _calculate_failure_probability(self, equipment: Equipment) -> float:
        """Calcular probabilidad de falla basada en MTBF y tiempo desde última mantención"""
        days_since_maintenance = (datetime.now() - equipment.last_maintenance).days
        
        # Modelo de probabilidad exponencial
        failure_rate = 1 / equipment.mtbf
        probability = 1 - np.exp(-failure_rate * days_since_maintenance * 24)
        
        return min(probability, 0.95)
    
    def _calculate_optimal_maintenance_day(
        self,
        equipment: Equipment,
        failure_prob: float,
        horizon_days: int
    ) -> int:
        """Calcular día óptimo para mantenimiento preventivo"""
        # Si probabilidad > 30%, mantenimiento urgente
        if failure_prob > 0.30:
            return min(7, horizon_days)
        
        # Si probabilidad > 20%, dentro de 2 semanas
        elif failure_prob > 0.20:
            return min(14, horizon_days)
        
        # Si probabilidad > 10%, dentro de 1 mes
        elif failure_prob > 0.10:
            return min(30, horizon_days)
        
        # Sino, al final del horizonte
        else:
            return horizon_days
    
    def _get_maintenance_reason(self, equipment: Equipment, failure_prob: float) -> str:
        """Generar razón para mantenimiento"""
        if failure_prob > 0.30:
            return "Alta probabilidad de falla - Urgente"
        elif failure_prob > 0.20:
            return "Probabilidad moderada de falla"
        elif equipment.utilization > self.params['utilization_high']:
            return "Alta utilización - Desgaste acelerado"
        elif equipment.availability < self.params['availability_critical']:
            return "Disponibilidad crítica"
        else:
            return "Mantenimiento preventivo programado"
    
    async def _check_backup_equipment(self, equipment_type: str, shift: str) -> List[Equipment]:
        """Verificar equipos backup disponibles"""
        all_equipment = await self._get_all_equipment(equipment_type)
        
        # Filtrar equipos con baja utilización que pueden servir de backup
        backup = [
            eq for eq in all_equipment
            if eq.utilization < self.params['utilization_low'] and eq.availability > 0.7
        ]
        
        return backup
    
    def _assess_risk(
        self,
        production_loss: float,
        backup_available: List,
        duration: float
    ) -> str:
        """Evaluar nivel de riesgo"""
        # Sin backup y pérdida alta
        if not backup_available and production_loss > 1000:
            return "high"
        
        # Sin backup o pérdida moderada
        elif not backup_available or production_loss > 500:
            return "medium"
        
        # Con backup y pérdida baja
        else:
            return "low"
    
    def _calculate_severity(self, production_loss: float) -> str:
        """Calcular severidad del impacto"""
        if production_loss > 2000:
            return "critical"
        elif production_loss > 1000:
            return "high"
        elif production_loss > 500:
            return "medium"
        else:
            return "low"
    
    def _generate_failure_recommendations(
        self,
        equipment: Equipment,
        backup_available: List,
        production_loss: float,
        duration: float
    ) -> List[str]:
        """Generar recomendaciones para manejo de falla"""
        recs = []
        
        if backup_available:
            recs.append(f" {len(backup_available)} equipo(s) backup disponible(s): {', '.join([eq.id for eq in backup_available])}")
            recs.append("Activar equipo backup inmediatamente para minimizar impacto")
        else:
            recs.append(" No hay equipos backup disponibles")
            recs.append("Considerar redistribuir carga entre equipos activos")
        
        if production_loss > 1000:
            recs.append(" Pérdida de producción significativa - Priorizar reparación urgente")
        
        if duration > 4:
            recs.append("Evaluar arrendar equipo externo si reparación excede 4 horas")
        
        recs.append(f"Notificar a planificación sobre ajuste de {int(production_loss)} toneladas")
        
        return recs
    
    def _generate_maintenance_recommendations(self, maintenance_plan: List[Dict]) -> List[str]:
        """Generar recomendaciones generales de mantenimiento"""
        recs = []
        
        high_priority = [m for m in maintenance_plan if m['priority'] > 5000]
        if high_priority:
            recs.append(f" {len(high_priority)} equipo(s) requieren mantenimiento urgente")
            recs.append(f"Priorizar: {', '.join([m['equipment_id'] for m in high_priority[:3]])}")
        
        avg_prob = np.mean([m['failure_probability'] for m in maintenance_plan])
        if avg_prob > 0.20:
            recs.append(" Probabilidad promedio de falla elevada - Intensificar programa preventivo")
        
        recs.append("Coordinar mantenimientos para minimizar impacto en producción")
        recs.append("Mantener stock de repuestos críticos")
        
        return recs
    
    def _generate_bottleneck_recommendations(self, bottleneck: Dict) -> List[str]:
        """Generar recomendaciones para resolver cuello de botella"""
        recs = []
        
        deficit = bottleneck['deficit']
        stage = bottleneck['stage']
        
        recs.append(f" Cuello de botella identificado en {stage}: déficit de {deficit:.0f} ton/turno")
        
        if bottleneck['avg_availability'] < 0.80:
            recs.append("Mejorar disponibilidad mecánica mediante mantenimiento preventivo intensivo")
        
        if deficit > bottleneck['target'] * 0.20:
            recs.append("Déficit significativo - Considerar agregar equipo adicional")
        else:
            recs.append("Optimizar utilización de flota existente")
        
        recs.append(f"Revisar asignación de operadores en {stage}")
        
        return recs
    
    async def _simulate_add_equipment(self, parameters: Dict) -> SimulationResult:
        """Simular agregar equipos"""
        equipment_type = parameters.get('equipment_type', 'loader')
        quantity = parameters.get('quantity', 1)
        
        current_production = 8000  # Simplificado
        additional_production = quantity * self.params[f"{equipment_type}_productivity_base"] * 8
        
        return SimulationResult(
            scenario=f"Agregar {quantity} {equipment_type}(s)",
            metrics={
                'current_production': current_production,
                'additional_production': additional_production,
                'new_total_production': current_production + additional_production,
                'production_increase_pct': round((additional_production / current_production) * 100, 2)
            },
            recommendations=[
                f"Aumento estimado: {additional_production:.0f} ton/turno",
                "Considerar costos de operación y personal adicional",
                "Evaluar disponibilidad de operadores calificados"
            ],
            risk_level="low",
            confidence=0.80
        )
    
    async def _simulate_shift_change(self, parameters: Dict) -> SimulationResult:
        """Simular cambio de turno"""
        return SimulationResult(
            scenario="Cambio de configuración de turnos",
            metrics={'impact': 'medium'},
            recommendations=["Evaluar impacto en productividad por turno"],
            risk_level="medium",
            confidence=0.70
        )
    
    async def _simulate_maintenance_window(self, parameters: Dict) -> SimulationResult:
        """Simular ventana de mantenimiento"""
        return SimulationResult(
            scenario="Ventana de mantenimiento programada",
            metrics={'downtime_hours': parameters.get('duration', 8)},
            recommendations=["Coordinar con producción", "Preparar repuestos"],
            risk_level="medium",
            confidence=0.85
        )
    
    async def _simulate_production_increase(self, parameters: Dict) -> SimulationResult:
        """Simular aumento de producción"""
        target_increase = parameters.get('increase_pct', 10)
        
        return SimulationResult(
            scenario=f"Aumento de producción en {target_increase}%",
            metrics={
                'target_increase_pct': target_increase,
                'equipment_required': 'Análisis en progreso'
            },
            recommendations=[
                "Evaluar capacidad actual de flota",
                "Verificar disponibilidad de personal",
                "Revisar suministros y repuestos"
            ],
            risk_level="medium",
            confidence=0.75
        )


# ============================================================================
# EJEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test_world_model():
        model = MiningWorldModel()
        
        # Test 1: Simular falla
        print("\n=== TEST 1: SIMULACIÓN DE FALLA ===")
        result = await model.simulate_equipment_failure("loader_001", 4.0, "A")
        print(f"Escenario: {result.scenario}")
        print(f"Riesgo: {result.risk_level}")
        print(f"Métricas: {result.metrics}")
        print(f"Recomendaciones: {len(result.recommendations)}")
        
        # Test 2: Optimizar mantenimiento
        print("\n=== TEST 2: OPTIMIZACIÓN DE MANTENIMIENTO ===")
        plan = await model.optimize_maintenance_schedule(horizon_days=30)
        print(f"Equipos a mantener: {len(plan['maintenance_plan'])}")
        print(f"Alta prioridad: {plan['statistics']['high_priority']}")
        
        # Test 3: Predecir cuellos de botella
        print("\n=== TEST 3: PREDICCIÓN DE CUELLOS DE BOTELLA ===")
        bottlenecks = await model.predict_bottlenecks(target_production=10000)
        print(f"Cuellos de botella: {len(bottlenecks['bottlenecks'])}")
        print(f"Ratio capacidad: {bottlenecks['capacity_ratio']}")
    
    asyncio.run(test_world_model())