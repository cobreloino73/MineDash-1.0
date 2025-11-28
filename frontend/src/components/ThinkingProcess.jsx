import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, Clock, Loader2, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';

const ThinkingProcess = ({ toolsUsed, isThinking }) => {
  const [isExpanded, setIsExpanded] = useState(true); // Siempre expandido durante proceso
  const [elapsedTime, setElapsedTime] = useState(0);

  useEffect(() => {
    if (isThinking) {
      setIsExpanded(true); // Auto-expandir cuando está pensando
      const interval = setInterval(() => {
        setElapsedTime(prev => prev + 1);
      }, 1000);
      return () => clearInterval(interval);
    } else {
      setElapsedTime(0);
    }
  }, [isThinking]);

  const formatTime = (seconds) => {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  // Mapeo de nombres de herramientas a descripciones amigables con emojis
  const getToolInfo = (tool) => {
    const toolNames = {
      'status': { icon: '🔍', name: 'Analizando' },
      'execute_sql': { icon: '🗄️', name: 'Consultando base de datos' },
      'obtener_analisis_gaviota': { icon: '🦅', name: 'Analizando patrón gaviota' },
      'obtener_comparacion_gaviotas': { icon: '📊', name: 'Comparando turnos' },
      'generate_chart': { icon: '📈', name: 'Generando gráfico' },
      'search_knowledge': { icon: '📚', name: 'Buscando en documentación' },
      'execute_python': { icon: '🐍', name: 'Ejecutando análisis Python' },
      'get_ranking_operadores': { icon: '🏆', name: 'Calculando rankings' },
      'obtener_movimiento_mina': { icon: '⛏️', name: 'Obteniendo movimiento mina' },
      'obtener_cumplimiento_tonelaje': { icon: '📦', name: 'Verificando cumplimiento' },
      'obtener_pareto_delays': { icon: '📉', name: 'Analizando delays (Pareto)' },
      'analizar_match_pala_camion': { icon: '🔄', name: 'Optimizando match pala-camión' },
      'analizar_tendencia_mes': { icon: '📈', name: 'Analizando tendencia mensual' },
      'obtener_costos_mina': { icon: '💰', name: 'Consultando costos operacionales' }
    };

    const info = toolNames[tool.name] || { icon: '⚙️', name: tool.name };
    return {
      ...info,
      description: tool.description || info.name,
      summary: tool.summary
    };
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
        return <CheckCircle2 size={14} className="text-green-500" />;
      case 'error':
        return <XCircle size={14} className="text-red-500" />;
      case 'running':
        return <Loader2 size={14} className="text-copper-500 animate-spin" />;
      default:
        return <AlertCircle size={14} className="text-slate-400" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'success':
        return 'border-l-green-500 bg-green-50/50';
      case 'error':
        return 'border-l-red-500 bg-red-50/50';
      case 'running':
        return 'border-l-copper-500 bg-copper-50/50';
      default:
        return 'border-l-slate-300 bg-slate-50/50';
    }
  };

  // Vista compacta cuando terminó (no está pensando)
  if (!isExpanded && !isThinking && toolsUsed.length > 0) {
    return (
      <div className="mb-3 text-xs text-slate-400 flex items-center gap-2 animate-fade-in">
        <CheckCircle2 size={14} className="text-green-500" />
        <span className="font-medium">{toolsUsed.filter(t => t.name !== 'status').length} {toolsUsed.length === 1 ? 'proceso ejecutado' : 'procesos ejecutados'}</span>
        <button
          onClick={() => setIsExpanded(true)}
          className="text-copper-600 hover:text-copper-700 hover:underline transition-colors ml-1"
        >
          ver detalles
        </button>
      </div>
    );
  }

  if (toolsUsed.length === 0 && !isThinking) return null;

  return (
    <div className="mb-4 rounded-xl border border-copper-100 bg-white/80 backdrop-blur-sm overflow-hidden shadow-sm transition-all duration-300">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-white/90 transition-colors border-b border-copper-100/50"
      >
        <div className="flex items-center gap-3">
          <div className={`flex items-center justify-center w-8 h-8 rounded-full ${isThinking ? 'bg-copper-100 text-copper-600' : 'bg-green-100 text-green-600'}`}>
            {isThinking ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
          </div>
          <div className="flex flex-col items-start">
            <span className="text-sm font-semibold text-slate-700">
              {isThinking ? 'Analizando...' : 'Analisis completado'}
            </span>
            <span className="text-[10px] text-slate-400 flex items-center gap-1 font-medium">
              <Clock size={10} />
              {formatTime(elapsedTime)}
              {toolsUsed.length > 0 && ` · ${toolsUsed.filter(t => t.name !== 'status').length} herramientas`}
            </span>
          </div>
        </div>
        {isExpanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
      </button>

      {/* Steps expandidos */}
      {isExpanded && (
        <div className="px-3 py-2 space-y-1 bg-white/50 max-h-64 overflow-y-auto">
          {toolsUsed.map((tool, idx) => {
            const toolInfo = getToolInfo(tool);
            return (
              <div
                key={idx}
                className={`flex items-start gap-3 text-xs p-2 rounded-lg border-l-2 transition-all duration-300 ${getStatusColor(tool.status)}`}
                style={{ animationDelay: `${idx * 50}ms` }}
              >
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <span className="text-base flex-shrink-0">{toolInfo.icon}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-700 truncate">
                        {toolInfo.description}
                      </span>
                      {getStatusIcon(tool.status)}
                    </div>
                    {tool.summary && (
                      <span className="text-slate-500 text-[10px] block truncate mt-0.5 italic">
                        {tool.summary}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {isThinking && (
            <div className="flex items-center gap-2 p-2 text-xs text-slate-500 animate-pulse">
              <span className="text-base">✨</span>
              <span className="italic">Generando respuesta final...</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ThinkingProcess;
