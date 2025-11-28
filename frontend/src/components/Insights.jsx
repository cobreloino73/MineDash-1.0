import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  AlertCircle,
  Info,
  Lightbulb,
  TrendingUp,
  Loader,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  Zap,
  Activity
} from 'lucide-react';

const API_URL = 'http://localhost:8001';

const ALERT_TYPES = {
  critical: {
    icon: AlertTriangle,
    color: 'red',
    bgColor: 'bg-red-50/50',
    borderColor: 'border-red-200',
    textColor: 'text-red-900',
    badgeBg: 'bg-red-100',
    badgeText: 'text-red-700',
    shadow: 'shadow-red-500/5'
  },
  warning: {
    icon: AlertCircle,
    color: 'amber',
    bgColor: 'bg-amber-50/50',
    borderColor: 'border-amber-200',
    textColor: 'text-amber-900',
    badgeBg: 'bg-amber-100',
    badgeText: 'text-amber-700',
    shadow: 'shadow-amber-500/5'
  },
  info: {
    icon: Info,
    color: 'blue',
    bgColor: 'bg-blue-50/50',
    borderColor: 'border-blue-200',
    textColor: 'text-blue-900',
    badgeBg: 'bg-blue-100',
    badgeText: 'text-blue-700',
    shadow: 'shadow-blue-500/5'
  },
  success: {
    icon: CheckCircle,
    color: 'green',
    bgColor: 'bg-green-50/50',
    borderColor: 'border-green-200',
    textColor: 'text-green-900',
    badgeBg: 'bg-green-100',
    badgeText: 'text-green-700',
    shadow: 'shadow-green-500/5'
  }
};

export default function Insights() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [insightsData, setInsightsData] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [selectedFilter, setSelectedFilter] = useState('all');
  const [currentPeriod, setCurrentPeriod] = useState({ year: null, month: null });

  useEffect(() => {
    loadMetadataAndInsights();
  }, []);

  const loadMetadataAndInsights = async () => {
    setLoading(true);
    setError(null);

    try {
      // Primero obtener el último mes/año con datos
      let year = 2025;
      let month = 1;

      try {
        const metadataRes = await fetch(`${API_URL}/api/data/metadata`);
        if (metadataRes.ok) {
          const metadata = await metadataRes.json();
          if (metadata.success && metadata.last_loaded) {
            year = metadata.last_loaded.year;
            month = metadata.last_loaded.month;
          }
        }
      } catch (metaErr) {
        console.warn('No se pudo cargar metadata, usando defaults:', metaErr);
      }

      setCurrentPeriod({ year, month });
      await loadInsights(year, month);
    } catch (err) {
      console.error('Error inicial:', err);
      setError(err.message);
      setLoading(false);
    }
  };

  const loadInsights = async (year = currentPeriod.year || 2025, month = currentPeriod.month || 1) => {
    setLoading(true);
    setError(null);

    try {
      // Usar endpoints con año/mes dinámico
      const [cumplimientoRes, paretoRes] = await Promise.all([
        fetch(`${API_URL}/api/cumplimiento/tonelaje?year=${year}&mes=${month}`),
        fetch(`${API_URL}/api/analytics/pareto-delays?year=${year}&mes_inicio=1&mes_fin=12`)
      ]);

      if (!cumplimientoRes.ok || !paretoRes.ok) {
        throw new Error('Error al cargar datos del backend');
      }

      const cumplimiento = await cumplimientoRes.json();
      const pareto = await paretoRes.json();

      // Generar insights desde datos REALES con defensive coding
      const insights = [];
      let idCounter = 1;

      // Verificar que los datos existan antes de accederlos
      const cumplimientoData = cumplimiento?.cumplimiento || {};
      const periodoData = cumplimiento?.periodo || {};
      const analisisCausal = cumplimiento?.analisis_causal || {};
      const paretoData = pareto?.pareto || {};
      const uebdData = pareto?.uebd || {};

      // Insight 1: Cumplimiento vs P0
      const cumplimientoPct = cumplimientoData.cumplimiento_porcentaje;
      if (cumplimientoPct !== undefined && cumplimientoPct !== null) {
        if (cumplimientoPct < 100) {
          insights.push({
            id: idCounter++,
            type: 'critical',
            title: `Incumplimiento del Plan: ${cumplimientoPct.toFixed(1)}%`,
            description: `Se alcanzó solo el ${cumplimientoPct.toFixed(1)}% del plan P0 en ${periodoData.mes_nombre || 'el mes'} ${periodoData.year || ''}. Déficit de ${Math.abs(cumplimientoData.brecha_toneladas || 0).toLocaleString('es-CL')} toneladas.`,
            recommendation: 'Análisis urgente de causas raíz. Revisar disponibilidad de equipos y dotación de operadores.',
            area: 'Producción',
            impact: 'Crítico',
            timestamp: new Date().toISOString()
          });
        } else {
          insights.push({
            id: idCounter++,
            type: 'success',
            title: `Cumplimiento Exitoso: ${cumplimientoPct.toFixed(1)}%`,
            description: `Se superó el plan P0 en ${periodoData.mes_nombre || 'el mes'} ${periodoData.year || ''}. Excedente de ${(cumplimientoData.brecha_toneladas || 0).toLocaleString('es-CL')} toneladas.`,
            recommendation: 'Mantener prácticas actuales y analizar factores de éxito para replicar.',
            area: 'Producción',
            impact: 'Positivo',
            timestamp: new Date().toISOString()
          });
        }
      }

      // Insight 2: UEBD Crítico (con verificación null)
      if (uebdData.actual !== undefined && uebdData.target !== undefined && uebdData.actual < uebdData.target) {
        const brecha = uebdData.target - uebdData.actual;
        insights.push({
          id: idCounter++,
          type: 'critical',
          title: `UEBD Bajo: ${uebdData.actual}% (Target: ${uebdData.target}%)`,
          description: `La Utilización Efectiva está ${brecha.toFixed(1)}% por debajo del target. Esto impacta directamente en la producción y eficiencia operacional.`,
          recommendation: 'Enfocar esfuerzos en las 2 causas críticas del Pareto que representan el 80% del impacto.',
          area: 'Eficiencia',
          impact: 'Alto',
          timestamp: new Date().toISOString()
        });
      }

      // Insight 3: Causa Principal (con verificación array vacío)
      const topCausas = analisisCausal.top_causas_incumplimiento || [];
      const causaPrincipal = topCausas.length > 0 ? topCausas[0] : null;
      if (causaPrincipal && causaPrincipal.horas_perdidas > 10000) {
        insights.push({
          id: idCounter++,
          type: 'warning',
          title: `Causa Principal: ${causaPrincipal.razon}`,
          description: `Se perdieron ${(causaPrincipal.horas_perdidas || 0).toLocaleString('es-CL')} horas por "${causaPrincipal.razon}" en ${(causaPrincipal.eventos || 0).toLocaleString('es-CL')} eventos.`,
          recommendation: 'Mejorar coordinación despacho-carguío. Implementar sistema de alertas tempranas para disponibilidad de operadores.',
          area: 'Operaciones',
          impact: 'Alto',
          timestamp: new Date().toISOString()
        });
      }

      // Insight 4: Pareto 80/20 (con verificación null)
      const causasCriticas = paretoData.causas_criticas_80 || [];
      if (causasCriticas.length > 0) {
        insights.push({
          id: idCounter++,
          type: 'info',
          title: `Análisis Pareto: ${causasCriticas.length} Causas Críticas`,
          description: `Solo ${causasCriticas.length} causa(s) generan el ${paretoData.porcentaje_impacto_causas_criticas || 80}% del impacto total. Total de horas perdidas: ${(paretoData.total_horas_perdidas || 0).toLocaleString('es-CL')} hrs.`,
          recommendation: 'Crear task force enfocado específicamente en estas causas críticas para maximizar impacto de mejoras.',
          area: 'Mejora Continua',
          impact: 'Alto',
          timestamp: new Date().toISOString()
        });
      }

      // Insight 5: Equipos de Alto Rendimiento (con verificación array vacío)
      const equiposRendimiento = analisisCausal.equipos_rendimiento || [];
      const mejorEquipo = equiposRendimiento.length > 0 ? equiposRendimiento[0] : null;
      if (mejorEquipo) {
        insights.push({
          id: idCounter++,
          type: 'success',
          title: `Equipo Destacado: ${mejorEquipo.equipo}`,
          description: `El equipo ${mejorEquipo.equipo} logró ${(mejorEquipo.tonelaje || 0).toLocaleString('es-CL')} toneladas en ${mejorEquipo.dumps || 0} dumps, con promedio de ${(mejorEquipo.ton_por_dump || 0).toFixed(0)} ton/dump.`,
          recommendation: 'Analizar prácticas de este equipo para replicar en otros.',
          area: 'Equipos',
          impact: 'Positivo',
          timestamp: new Date().toISOString()
        });
      }

      // Construir resumen
      const summary = {
        total: insights.length,
        critical: insights.filter(i => i.type === 'critical').length,
        warning: insights.filter(i => i.type === 'warning').length,
        info: insights.filter(i => i.type === 'info').length,
        success: insights.filter(i => i.type === 'success').length
      };

      // Recomendaciones del backend (con verificación null)
      const recomendacionesBackend = cumplimiento?.recomendaciones || [];
      const recommendations = recomendacionesBackend.map((rec, idx) => ({
        id: idx + 1,
        title: rec.titulo,
        description: rec.descripcion,
        priority: rec.prioridad === 'CRÍTICA' ? 'high' : rec.prioridad === 'ALTA' ? 'medium' : 'low',
        impact: rec.enfoque
      }));

      setInsightsData({
        insights,
        summary,
        recommendations,
        predictions: [] // No inventar predicciones
      });

      setLastUpdate(new Date());
    } catch (err) {
      console.error('Error cargando insights:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getFilteredInsights = () => {
    if (!insightsData || !insightsData.insights) return [];
    if (selectedFilter === 'all') return insightsData.insights;
    return insightsData.insights.filter(i => i.type === selectedFilter);
  };

  const InsightCard = ({ insight }) => {
    const config = ALERT_TYPES[insight.type];
    const Icon = config.icon;

    return (
      <div className={`glass-card ${config.bgColor} border ${config.borderColor} rounded-2xl p-6 hover:shadow-lg ${config.shadow} transition-all duration-300 hover:-translate-y-0.5`}>
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-4">
            <div className={`p-3 ${config.badgeBg} rounded-xl shadow-sm`}>
              <Icon className={config.badgeText} size={24} />
            </div>
            <div>
              <h3 className={`font-bold text-lg ${config.textColor} tracking-tight`}>
                {insight.title}
              </h3>
              <div className="flex items-center gap-2 mt-1.5">
                <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 ${config.badgeBg} ${config.badgeText} rounded-md border border-white/20`}>
                  {insight.area}
                </span>
                <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 ${config.badgeBg} ${config.badgeText} rounded-md border border-white/20`}>
                  Impacto {insight.impact}
                </span>
              </div>
            </div>
          </div>
        </div>

        <p className={`${config.textColor} text-sm leading-relaxed mb-5 opacity-90 font-medium`}>
          {insight.description}
        </p>

        {insight.recommendation && (
          <div className={`mt-4 p-4 bg-white/60 backdrop-blur-sm border ${config.borderColor} rounded-xl`}>
            <div className="flex items-start gap-3">
              <Lightbulb className="text-copper-500 flex-shrink-0 mt-0.5" size={18} />
              <div>
                <p className="font-bold text-slate-800 text-xs uppercase tracking-wider mb-1">
                  Recomendación Estratégica
                </p>
                <p className="text-slate-600 text-sm font-medium">
                  {insight.recommendation}
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="flex items-center gap-2 mt-4 text-xs text-slate-400 font-medium">
          <Clock size={14} />
          <span>
            {new Date(insight.timestamp).toLocaleString('es-CL')}
          </span>
        </div>
      </div>
    );
  };

  const RecommendationCard = ({ recommendation }) => {
    const priorityConfig = {
      high: { color: 'red', label: 'Alta Prioridad', bgColor: 'bg-red-100', textColor: 'text-red-700' },
      medium: { color: 'amber', label: 'Prioridad Media', bgColor: 'bg-amber-100', textColor: 'text-amber-700' },
      low: { color: 'blue', label: 'Baja Prioridad', bgColor: 'bg-blue-100', textColor: 'text-blue-700' }
    };
    const config = priorityConfig[recommendation.priority];

    return (
      <div className="glass-card bg-white/80 border border-copper-100 rounded-2xl p-6 hover:shadow-lg hover:shadow-copper-500/5 transition-all duration-300 hover:-translate-y-0.5">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-copper-50 rounded-xl shadow-sm">
              <Lightbulb className="text-copper-600" size={24} />
            </div>
            <div>
              <h3 className="font-bold text-lg text-slate-900 tracking-tight">
                {recommendation.title}
              </h3>
              <span className={`inline-block text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 ${config.bgColor} ${config.textColor} rounded-md mt-1.5`}>
                {config.label}
              </span>
            </div>
          </div>
        </div>

        <p className="text-slate-600 text-sm leading-relaxed mb-5 font-medium">
          {recommendation.description}
        </p>

        <div className="bg-slate-50 border border-slate-100 rounded-xl p-3">
          <div className="flex items-start gap-2">
            <TrendingUp className="text-copper-600 flex-shrink-0 mt-0.5" size={18} />
            <div>
              <p className="font-bold text-slate-700 text-xs uppercase tracking-wider mb-1">
                Enfoque de Impacto
              </p>
              <p className="text-slate-600 text-sm font-medium">
                {recommendation.impact}
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-4">
            <div className="absolute inset-0 border-4 border-copper-100 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-copper-500 rounded-full border-t-transparent animate-spin"></div>
          </div>
          <p className="text-slate-600 font-bold text-lg">Generando insights...</p>
          <p className="text-sm text-slate-400 mt-1 font-medium">
            Analizando datos operacionales con IA
          </p>
        </div>
      </div>
    );
  }

  const filteredInsights = getFilteredInsights();

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="glass-card rounded-2xl mx-6 mt-6 p-6 mb-6 flex flex-col md:flex-row items-center justify-between gap-6 sticky top-0 z-10">
        <div>
          <h1 className="text-2xl font-display font-bold text-slate-900 flex items-center gap-3">
            <Zap className="text-copper-500 fill-copper-500" size={28} />
            Insights & Alertas
          </h1>
          <p className="text-sm text-slate-500 font-medium mt-1 ml-10">
            Análisis inteligente de operaciones - División Salvador
          </p>
        </div>

        <div className="flex items-center gap-4">
          {/* Filtros */}
          {insightsData && (
            <div className="flex bg-slate-100/50 p-1 rounded-xl">
              <button
                onClick={() => setSelectedFilter('all')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wide transition-all ${selectedFilter === 'all'
                    ? 'bg-white text-copper-600 shadow-sm'
                    : 'text-slate-400 hover:text-slate-600'
                  }`}
              >
                Todas
              </button>
              <button
                onClick={() => setSelectedFilter('critical')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wide transition-all ${selectedFilter === 'critical'
                    ? 'bg-white text-red-600 shadow-sm'
                    : 'text-slate-400 hover:text-slate-600'
                  }`}
              >
                Críticas
              </button>
              <button
                onClick={() => setSelectedFilter('warning')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wide transition-all ${selectedFilter === 'warning'
                    ? 'bg-white text-amber-600 shadow-sm'
                    : 'text-slate-400 hover:text-slate-600'
                  }`}
              >
                Alertas
              </button>
            </div>
          )}

          <button
            onClick={() => loadInsights(currentPeriod.year, currentPeriod.month)}
            disabled={loading}
            className="p-2 bg-copper-500 hover:bg-copper-600 text-white rounded-lg shadow-md shadow-copper-500/20 transition-all hover:scale-105 disabled:opacity-50"
          >
            <RefreshCw size={20} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Contenido principal */}
      <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-8 custom-scrollbar">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-8 text-center max-w-2xl mx-auto">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="text-red-600" size={32} />
            </div>
            <h3 className="text-red-900 font-bold text-lg mb-2">Error de Conexión</h3>
            <p className="text-red-600 text-sm mb-6">{error}</p>
            <button
              onClick={loadMetadataAndInsights}
              className="px-6 py-2 bg-red-500 hover:bg-red-600 text-white rounded-xl shadow-lg shadow-red-500/20 transition-all hover:-translate-y-0.5"
            >
              Reintentar
            </button>
          </div>
        )}

        {!error && !insightsData && (
          <div className="glass-card border-dashed border-2 border-slate-200 rounded-2xl p-12 text-center max-w-2xl mx-auto">
            <Activity className="text-slate-300 mx-auto mb-4" size={64} />
            <p className="text-slate-600 font-bold text-lg">
              No hay insights disponibles
            </p>
            <p className="text-sm text-slate-400 mt-2">
              Presiona el botón de actualizar para generar un nuevo análisis
            </p>
          </div>
        )}

        {insightsData && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 max-w-7xl mx-auto">
            {/* Alertas */}
            <div className="space-y-6">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-1 h-6 bg-copper-500 rounded-full" />
                <h2 className="text-xl font-bold text-slate-800">
                  Alertas Operacionales
                </h2>
              </div>

              {filteredInsights.length > 0 ? (
                <div className="space-y-4">
                  {filteredInsights.map(insight => (
                    <InsightCard key={insight.id} insight={insight} />
                  ))}
                </div>
              ) : (
                <div className="glass-card border-dashed border-2 border-slate-200 rounded-2xl p-12 text-center">
                  <CheckCircle className="text-slate-300 mx-auto mb-4" size={48} />
                  <p className="text-slate-500 font-medium">
                    No hay alertas de tipo "{selectedFilter}"
                  </p>
                </div>
              )}
            </div>

            {/* Recomendaciones */}
            {insightsData.recommendations && insightsData.recommendations.length > 0 && (
              <div className="space-y-6">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-1 h-6 bg-copper-500 rounded-full" />
                  <h2 className="text-xl font-bold text-slate-800">
                    Recomendaciones Estratégicas
                  </h2>
                </div>
                <div className="space-y-4">
                  {insightsData.recommendations.map(rec => (
                    <RecommendationCard key={rec.id} recommendation={rec} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}