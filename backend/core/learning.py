"""
MineDash AI v2.0 - RLAIF Learning Module
FASE 3: Reinforcement Learning from AI Feedback

Capacidades:
- Aprender de cada interacción sin reentrenamiento
- Mejorar respuestas basándose en feedback
- Generar insights automáticos de patrones
- Recomendar acciones basadas en aprendizaje
- Tracking de calidad de respuestas
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
import numpy as np
from collections import defaultdict, Counter


@dataclass
class Interaction:
    """Registro de una interacción"""
    id: Optional[int]
    timestamp: str
    user_query: str
    agent_response: str
    tools_used: str  # JSON list
    feedback_score: Optional[float]  # 0-1
    feedback_text: Optional[str]
    context: str  # JSON dict
    response_time_ms: float
    tokens_used: int


@dataclass
class Insight:
    """Insight generado automáticamente"""
    id: Optional[int]
    timestamp: str
    category: str  # 'pattern', 'recommendation', 'anomaly'
    title: str
    description: str
    confidence: float  # 0-1
    priority: str  # 'low', 'medium', 'high'
    metadata: str  # JSON dict


@dataclass
class Recommendation:
    """Recomendación generada por el sistema"""
    id: Optional[int]
    timestamp: str
    topic: str
    recommendation: str
    reasoning: str
    confidence: float
    impact: str  # 'low', 'medium', 'high'
    implemented: bool


class RLAIFLearning:
    """
    Sistema de Aprendizaje por Refuerzo desde Feedback de IA
    
    Aprende continuamente de las interacciones y genera insights
    sin necesidad de reentrenamiento del modelo base.
    """
    
    def __init__(self, db_path: str = "learning.db"):
        """
        Inicializar sistema de aprendizaje
        
        Args:
            db_path: Ruta a base de datos de aprendizaje
        """
        self.db_path = db_path
        self._init_database()
        
        # Configuración de aprendizaje
        self.config = {
            'min_interactions_for_pattern': 10,
            'confidence_threshold': 0.70,
            'feedback_weight': 0.8,
            'recency_weight': 0.2,
            'insight_generation_frequency': 100  # cada N interacciones
        }
        
        # Cache de patrones aprendidos
        self.pattern_cache = {}
        self.last_insight_generation = datetime.now()
    
    def _init_database(self):
        """Inicializar estructura de base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla de interacciones
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_query TEXT NOT NULL,
                agent_response TEXT NOT NULL,
                tools_used TEXT,
                feedback_score REAL,
                feedback_text TEXT,
                context TEXT,
                response_time_ms REAL,
                tokens_used INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de insights
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                confidence REAL NOT NULL,
                priority TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de recomendaciones
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                topic TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                reasoning TEXT NOT NULL,
                confidence REAL NOT NULL,
                impact TEXT NOT NULL,
                implemented BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de patrones aprendidos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learned_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT NOT NULL,
                pattern_data TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                last_seen TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Índices para mejor rendimiento
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_feedback ON interactions(feedback_score)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_insights_category ON insights(category)')
        
        conn.commit()
        conn.close()
    
    def log_interaction(
        self,
        user_query: str,
        agent_response: str,
        tools_used: List[str],
        context: Dict[str, Any],
        response_time_ms: float,
        tokens_used: int
    ) -> int:
        """
        Registrar una interacción
        
        Returns:
            ID de la interacción registrada
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO interactions 
            (timestamp, user_query, agent_response, tools_used, context, response_time_ms, tokens_used)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            user_query,
            agent_response,
            json.dumps(tools_used),
            json.dumps(context),
            response_time_ms,
            tokens_used
        ))
        
        interaction_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Verificar si es momento de generar insights
        self._check_insight_generation()
        
        return interaction_id
    
    def add_feedback(
        self,
        interaction_id: int,
        score: float,
        feedback_text: Optional[str] = None
    ):
        """
        Agregar feedback a una interacción
        
        Args:
            interaction_id: ID de la interacción
            score: Puntuación 0-1 (0=malo, 1=excelente)
            feedback_text: Texto opcional de feedback
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE interactions 
            SET feedback_score = ?, feedback_text = ?
            WHERE id = ?
        ''', (score, feedback_text, interaction_id))
        
        conn.commit()
        conn.close()
        
        # Actualizar patrones aprendidos
        self._update_learned_patterns(interaction_id, score)
    
    def get_insights(
        self,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 50
    ) -> List[Insight]:
        """
        Obtener insights generados
        
        Args:
            category: Filtrar por categoría
            priority: Filtrar por prioridad
            limit: Número máximo de resultados
            
        Returns:
            Lista de insights
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = 'SELECT * FROM insights WHERE 1=1'
        params = []
        
        if category:
            query += ' AND category = ?'
            params.append(category)
        
        if priority:
            query += ' AND priority = ?'
            params.append(priority)
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        insights = []
        for row in rows:
            insights.append(Insight(
                id=row['id'],
                timestamp=row['timestamp'],
                category=row['category'],
                title=row['title'],
                description=row['description'],
                confidence=row['confidence'],
                priority=row['priority'],
                metadata=row['metadata']
            ))
        
        return insights
    
    def get_recommendations(
        self,
        topic: Optional[str] = None,
        impact: Optional[str] = None,
        only_not_implemented: bool = False,
        limit: int = 20
    ) -> List[Recommendation]:
        """
        Obtener recomendaciones generadas
        
        Args:
            topic: Filtrar por tema
            impact: Filtrar por impacto
            only_not_implemented: Solo recomendaciones no implementadas
            limit: Número máximo de resultados
            
        Returns:
            Lista de recomendaciones
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = 'SELECT * FROM recommendations WHERE 1=1'
        params = []
        
        if topic:
            query += ' AND topic = ?'
            params.append(topic)
        
        if impact:
            query += ' AND impact = ?'
            params.append(impact)
        
        if only_not_implemented:
            query += ' AND implemented = 0'
        
        query += ' ORDER BY confidence DESC, timestamp DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        recommendations = []
        for row in rows:
            recommendations.append(Recommendation(
                id=row['id'],
                timestamp=row['timestamp'],
                topic=row['topic'],
                recommendation=row['recommendation'],
                reasoning=row['reasoning'],
                confidence=row['confidence'],
                impact=row['impact'],
                implemented=bool(row['implemented'])
            ))
        
        return recommendations
    
    def get_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Obtener estadísticas de aprendizaje
        
        Args:
            days: Número de días hacia atrás
            
        Returns:
            Dict con estadísticas
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Total de interacciones
        cursor.execute('SELECT COUNT(*) FROM interactions WHERE timestamp >= ?', (cutoff_date,))
        total_interactions = cursor.fetchone()[0]
        
        # Interacciones con feedback
        cursor.execute('SELECT COUNT(*) FROM interactions WHERE feedback_score IS NOT NULL AND timestamp >= ?', (cutoff_date,))
        interactions_with_feedback = cursor.fetchone()[0]
        
        # Puntuación promedio
        cursor.execute('SELECT AVG(feedback_score) FROM interactions WHERE feedback_score IS NOT NULL AND timestamp >= ?', (cutoff_date,))
        avg_score = cursor.fetchone()[0] or 0.0
        
        # Herramientas más usadas
        cursor.execute('SELECT tools_used FROM interactions WHERE timestamp >= ?', (cutoff_date,))
        tools_data = cursor.fetchall()
        tools_counter = Counter()
        for (tools_json,) in tools_data:
            if tools_json:
                tools = json.loads(tools_json)
                for tool in tools:
                    if isinstance(tool, dict):
                        tools_counter[tool.get('name', 'unknown')] += 1
        
        # Insights generados
        cursor.execute('SELECT COUNT(*) FROM insights WHERE timestamp >= ?', (cutoff_date,))
        total_insights = cursor.fetchone()[0]
        
        # Insights por categoría
        cursor.execute('SELECT category, COUNT(*) FROM insights WHERE timestamp >= ? GROUP BY category', (cutoff_date,))
        insights_by_category = dict(cursor.fetchall())
        
        # Recomendaciones
        cursor.execute('SELECT COUNT(*) FROM recommendations WHERE timestamp >= ?', (cutoff_date,))
        total_recommendations = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM recommendations WHERE implemented = 1 AND timestamp >= ?', (cutoff_date,))
        implemented_recommendations = cursor.fetchone()[0]
        
        # Tiempo de respuesta promedio
        cursor.execute('SELECT AVG(response_time_ms) FROM interactions WHERE timestamp >= ?', (cutoff_date,))
        avg_response_time = cursor.fetchone()[0] or 0.0
        
        conn.close()
        
        return {
            'period_days': days,
            'total_interactions': total_interactions,
            'interactions_with_feedback': interactions_with_feedback,
            'feedback_rate': round(interactions_with_feedback / total_interactions * 100, 2) if total_interactions > 0 else 0,
            'avg_feedback_score': round(avg_score, 3),
            'avg_response_time_ms': round(avg_response_time, 2),
            'total_insights': total_insights,
            'insights_by_category': insights_by_category,
            'total_recommendations': total_recommendations,
            'implemented_recommendations': implemented_recommendations,
            'implementation_rate': round(implemented_recommendations / total_recommendations * 100, 2) if total_recommendations > 0 else 0,
            'most_used_tools': dict(tools_counter.most_common(10))
        }
    
    def generate_insights_now(self) -> List[Insight]:
        """
        Generar insights inmediatamente basándose en datos históricos
        
        Returns:
            Lista de nuevos insights generados
        """
        insights = []
        
        # 1. Analizar patrones de consultas frecuentes
        pattern_insights = self._analyze_query_patterns()
        insights.extend(pattern_insights)
        
        # 2. Analizar herramientas más efectivas
        tool_insights = self._analyze_tool_effectiveness()
        insights.extend(tool_insights)
        
        # 3. Detectar anomalías en rendimiento
        anomaly_insights = self._detect_anomalies()
        insights.extend(anomaly_insights)
        
        # 4. Generar recomendaciones operacionales
        operational_recs = self._generate_operational_recommendations()
        insights.extend(operational_recs)
        
        # Guardar insights en BD
        for insight in insights:
            self._save_insight(insight)
        
        self.last_insight_generation = datetime.now()
        
        return insights
    
    # ========================================================================
    # MÉTODOS PRIVADOS - ANÁLISIS Y GENERACIÓN
    # ========================================================================
    
    def _check_insight_generation(self):
        """Verificar si es momento de generar insights automáticamente"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Contar interacciones desde último insight
        cursor.execute('''
            SELECT COUNT(*) FROM interactions 
            WHERE timestamp > ?
        ''', (self.last_insight_generation.isoformat(),))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        if count >= self.config['insight_generation_frequency']:
            self.generate_insights_now()
    
    def _update_learned_patterns(self, interaction_id: int, score: float):
        """Actualizar patrones aprendidos basándose en feedback"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Obtener la interacción
        cursor.execute('SELECT user_query, tools_used FROM interactions WHERE id = ?', (interaction_id,))
        row = cursor.fetchone()
        
        if row:
            query, tools_json = row
            
            # Extraer patrón de la consulta (simplificado)
            pattern_type = self._classify_query_pattern(query)
            
            # Buscar patrón existente
            cursor.execute('''
                SELECT id, frequency, confidence FROM learned_patterns 
                WHERE pattern_type = ?
            ''', (pattern_type,))
            
            existing = cursor.fetchone()
            
            if existing:
                pattern_id, freq, conf = existing
                
                # Actualizar patrón existente
                new_confidence = (conf * freq + score) / (freq + 1)
                cursor.execute('''
                    UPDATE learned_patterns 
                    SET frequency = frequency + 1,
                        confidence = ?,
                        last_seen = ?
                    WHERE id = ?
                ''', (new_confidence, datetime.now().isoformat(), pattern_id))
            else:
                # Crear nuevo patrón
                cursor.execute('''
                    INSERT INTO learned_patterns 
                    (pattern_type, pattern_data, frequency, last_seen, confidence)
                    VALUES (?, ?, 1, ?, ?)
                ''', (
                    pattern_type,
                    json.dumps({'query_template': query[:100], 'tools': tools_json}),
                    datetime.now().isoformat(),
                    score
                ))
        
        conn.commit()
        conn.close()
    
    def _classify_query_pattern(self, query: str) -> str:
        """Clasificar tipo de patrón de consulta"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['cuánto', 'cuántos', 'cantidad', 'total']):
            return 'quantitative'
        elif any(word in query_lower for word in ['por qué', 'causa', 'razón', 'motivo']):
            return 'causal'
        elif any(word in query_lower for word in ['gráfico', 'visualiza', 'muestra', 'grafica']):
            return 'visualization'
        elif any(word in query_lower for word in ['mejor', 'óptimo', 'recomienda', 'debería']):
            return 'recommendation'
        elif any(word in query_lower for word in ['comparar', 'diferencia', 'versus', 'vs']):
            return 'comparison'
        else:
            return 'general'
    
    def _analyze_query_patterns(self) -> List[Insight]:
        """Analizar patrones en consultas frecuentes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        insights = []
        
        # Consultas más frecuentes (últimos 30 días)
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        cursor.execute('''
            SELECT user_query, COUNT(*) as freq 
            FROM interactions 
            WHERE timestamp >= ?
            GROUP BY LOWER(SUBSTR(user_query, 1, 50))
            HAVING freq >= ?
            ORDER BY freq DESC
            LIMIT 5
        ''', (cutoff, self.config['min_interactions_for_pattern']))
        
        frequent_queries = cursor.fetchall()
        
        if frequent_queries:
            for query, freq in frequent_queries:
                insights.append(Insight(
                    id=None,
                    timestamp=datetime.now().isoformat(),
                    category='pattern',
                    title=f"Consulta frecuente detectada ({freq} veces)",
                    description=f"Los usuarios preguntan con frecuencia: '{query[:100]}...'",
                    confidence=min(0.9, 0.5 + (freq / 50)),
                    priority='medium' if freq > 20 else 'low',
                    metadata=json.dumps({'frequency': freq, 'query_sample': query[:200]})
                ))
        
        conn.close()
        return insights
    
    def _analyze_tool_effectiveness(self) -> List[Insight]:
        """Analizar efectividad de herramientas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        insights = []
        
        # Herramientas con mejor feedback
        cursor.execute('''
            SELECT tools_used, AVG(feedback_score) as avg_score, COUNT(*) as usage_count
            FROM interactions
            WHERE feedback_score IS NOT NULL AND tools_used != '[]'
            GROUP BY tools_used
            HAVING usage_count >= 5
            ORDER BY avg_score DESC
            LIMIT 3
        ''')
        
        effective_tools = cursor.fetchall()
        
        for tools_json, avg_score, count in effective_tools:
            if avg_score > 0.75:
                insights.append(Insight(
                    id=None,
                    timestamp=datetime.now().isoformat(),
                    category='recommendation',
                    title=f"Herramienta efectiva identificada (score: {avg_score:.2f})",
                    description=f"Las herramientas {tools_json} tienen alta efectividad basada en {count} usos",
                    confidence=min(0.95, 0.6 + (count / 50)),
                    priority='high' if avg_score > 0.85 else 'medium',
                    metadata=json.dumps({'tools': tools_json, 'avg_score': avg_score, 'usage_count': count})
                ))
        
        conn.close()
        return insights
    
    def _detect_anomalies(self) -> List[Insight]:
        """Detectar anomalías en rendimiento"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        insights = []
        
        # Tiempo de respuesta anormalmente alto
        cursor.execute('''
            SELECT AVG(response_time_ms), MAX(response_time_ms)
            FROM interactions
            WHERE timestamp >= ?
        ''', ((datetime.now() - timedelta(days=7)).isoformat(),))
        
        avg_time, max_time = cursor.fetchone()
        
        if max_time and avg_time and max_time > avg_time * 3:
            insights.append(Insight(
                id=None,
                timestamp=datetime.now().isoformat(),
                category='anomaly',
                title="Tiempo de respuesta elevado detectado",
                description=f"Tiempo máximo ({max_time:.0f}ms) es 3x el promedio ({avg_time:.0f}ms)",
                confidence=0.80,
                priority='medium',
                metadata=json.dumps({'avg_ms': avg_time, 'max_ms': max_time})
            ))
        
        conn.close()
        return insights
    
    def _generate_operational_recommendations(self) -> List[Insight]:
        """Generar recomendaciones operacionales"""
        insights = []
        
        # Obtener estadísticas recientes
        stats = self.get_statistics(days=7)
        
        # Recomendación sobre feedback
        if stats['feedback_rate'] < 30:
            insights.append(Insight(
                id=None,
                timestamp=datetime.now().isoformat(),
                category='recommendation',
                title="Aumentar tasa de feedback",
                description=f"Solo {stats['feedback_rate']:.1f}% de interacciones tienen feedback. Objetivo: >50%",
                confidence=0.90,
                priority='high',
                metadata=json.dumps({'current_rate': stats['feedback_rate'], 'target': 50})
            ))
        
        # Recomendación sobre insights
        if stats['total_insights'] < 5:
            insights.append(Insight(
                id=None,
                timestamp=datetime.now().isoformat(),
                category='recommendation',
                title="Generar más insights automáticos",
                description="Pocos insights generados en la última semana. Revisar frecuencia de generación.",
                confidence=0.75,
                priority='medium',
                metadata=json.dumps({'current_count': stats['total_insights']})
            ))
        
        return insights
    
    def _save_insight(self, insight: Insight):
        """Guardar insight en base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO insights 
            (timestamp, category, title, description, confidence, priority, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            insight.timestamp,
            insight.category,
            insight.title,
            insight.description,
            insight.confidence,
            insight.priority,
            insight.metadata
        ))
        
        conn.commit()
        conn.close()


# ============================================================================
# EJEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    # Crear sistema de aprendizaje
    learning = RLAIFLearning("learning.db")
    
    # Simular algunas interacciones
    print("\n=== REGISTRANDO INTERACCIONES ===")
    for i in range(5):
        interaction_id = learning.log_interaction(
            user_query=f"¿Cuál es la productividad del operador {1000+i}?",
            agent_response=f"El operador {1000+i} tiene una productividad de {80+i}%",
            tools_used=["execute_sql"],
            context={"operator_id": 1000+i},
            response_time_ms=250 + i*10,
            tokens_used=150
        )
        
        # Agregar feedback aleatorio
        learning.add_feedback(interaction_id, np.random.uniform(0.7, 1.0))
    
    print("✅ 5 interacciones registradas")
    
    # Generar insights
    print("\n=== GENERANDO INSIGHTS ===")
    insights = learning.generate_insights_now()
    print(f"✅ {len(insights)} insights generados")
    
    for insight in insights:
        print(f"\n📊 {insight.title}")
        print(f"   {insight.description}")
        print(f"   Confianza: {insight.confidence:.2f} | Prioridad: {insight.priority}")
    
    # Obtener estadísticas
    print("\n=== ESTADÍSTICAS ===")
    stats = learning.get_statistics(days=7)
    print(f"Total interacciones: {stats['total_interactions']}")
    print(f"Tasa de feedback: {stats['feedback_rate']}%")
    print(f"Score promedio: {stats['avg_feedback_score']}")
    print(f"Total insights: {stats['total_insights']}")