"""
MineDash AI v2.0 - Core Modules
3 Fases de IA Avanzada para Operaciones Mineras

Fase 1: Agentic AI - Agente con herramientas
Fase 2: World Model - Simulaciones operacionales
Fase 3: RLAIF - Aprendizaje por refuerzo
"""

from .agent import MineDashAgent
from .world_model import MiningWorldModel
from .learning import RLAIFLearning

__all__ = [
    'MineDashAgent',
    'MiningWorldModel',
    'RLAIFLearning'
]

__version__ = '2.0.0'
__author__ = 'AIMINE - David Kubota'