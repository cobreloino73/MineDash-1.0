import React, { useState, useEffect } from 'react';
import { Calendar, RefreshCw, TrendingDown, AlertTriangle, Users, Truck, Activity, Target, Clock } from 'lucide-react';

const API_URL = 'http://localhost:8001';

const MESES = [
  { value: 1, label: 'Enero' },
  { value: 2, label: 'Febrero' },
  { value: 3, label: 'Marzo' },
  { value: 4, label: 'Abril' },
  { value: 5, label: 'Mayo' },
  { value: 6, label: 'Junio' },
  { value: 7, label: 'Julio' },
  { value: 8, label: 'Agosto' },
  { value: 9, label: 'Septiembre' },
  { value: 10, label: 'Octubre' },
  { value: 11, label: 'Noviembre' },
  { value: 12, label: 'Diciembre' }
];

export default function Dashboard({ selectedArea }) {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedYear, setSelectedYear] = useState(null);
  const [selectedMonth, setSelectedMonth] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [error, setError] = useState(null);
  const [availableYears, setAvailableYears] = useState([2024, 2025]);
  const [metadataLoaded, setMetadataLoaded] = useState(false);

  // Cargar metadata al montar para auto-detectar último mes cargado
  useEffect(() => {
    const loadMetadata = async () => {
      try {
        const res = await fetch(`${API_URL}/api/data/metadata`);
        if (res.ok) {
          const data = await res.json();
          if (data.success && data.last_loaded) {
            setSelectedYear(data.last_loaded.year);
            setSelectedMonth(data.last_loaded.month);
            if (data.available_years && data.available_years.length > 0) {
              setAvailableYears(data.available_years);
            }
          }
        }
      } catch (err) {
        console.warn('No se pudo cargar metadata, usando defaults:', err);
        // Fallback a valores por defecto
        setSelectedYear(2025);
        setSelectedMonth(1);
      } finally {
        setMetadataLoaded(true);
      }
    };
    loadMetadata();
  }, []);

  // Cargar datos solo cuando metadata está lista y hay año/mes seleccionado
  useEffect(() => {
    if (metadataLoaded && selectedYear && selectedMonth) {
      fetchDashboardData();
    }
  }, [selectedYear, selectedMonth, metadataLoaded]);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);

    try {
      // Llamar a endpoints que SÍ funcionan
      // NOTA: Pareto usa año fijo 2024 para datos históricos consistentes
      const [cumplimientoRes, paretoRes] = await Promise.all([
        fetch(`${API_URL}/api/cumplimiento/tonelaje?year=${selectedYear}&mes=${selectedMonth}`),
        fetch(`${API_URL}/api/analytics/pareto-delays?year=2024&mes_inicio=1&mes_fin=12`)
      ]);

      if (!cumplimientoRes.ok || !paretoRes.ok) {
        throw new Error('Error al cargar datos del backend');
      }

      const cumplimiento = await cumplimientoRes.json();
      const pareto = await paretoRes.json();

      // Transformar datos al formato del dashboard con defensive coding
      const cumplimientoData = cumplimiento?.cumplimiento || {};
      const analisisCausal = cumplimiento?.analisis_causal || {};
      const paretoData = pareto?.pareto || {};
      const uebdData = pareto?.uebd || {};

      const transformedData = {
        success: true,
        kpis: [
          {
            nombre: 'Tonelaje Real',
            valor: cumplimientoData.tonelaje_real || 0,
            unidad: 'ton',
            meta: cumplimientoData.tonelaje_plan_p0 || cumplimientoData.tonelaje_plan || 0,
            variacion: (cumplimientoData.cumplimiento_porcentaje || 0) - 100,
            icon: Activity
          },
          {
            nombre: 'Cumplimiento vs P0',
            valor: cumplimientoData.cumplimiento_porcentaje || 0,
            unidad: '%',
            meta: 100,
            variacion: (cumplimientoData.cumplimiento_porcentaje || 0) - 100,
            icon: Target
          },
          {
            nombre: 'UEBD (Utilización)',
            valor: uebdData.actual || 0,
            unidad: '%',
            meta: uebdData.target || 75,
            variacion: (uebdData.actual || 0) - (uebdData.target || 75),
            icon: Truck
          },
          {
            nombre: 'Dumps Totales',
            valor: cumplimientoData.total_dumps || 0,
            unidad: 'viajes',
            variacion: 0,
            icon: Truck
          },
          {
            nombre: 'Días Operativos',
            valor: cumplimientoData.dias_operativos || 0,
            unidad: 'días',
            variacion: 0,
            icon: Calendar
          },
          {
            nombre: 'Horas Perdidas',
            valor: paretoData.total_horas_perdidas || 0,
            unidad: 'hrs',
            variacion: 0,
            icon: TrendingDown
          }
        ],
        equipos: (analisisCausal.equipos_rendimiento || []).map(eq => ({
          nombre: eq.equipo,
          tonelaje_total: eq.tonelaje || 0,
          dumps_total: eq.dumps || 0,
          ton_promedio: eq.ton_por_dump || 0
        })),
        causas_criticas: paretoData.causas_criticas_80 || [],
        top_causas: (analisisCausal.top_causas_incumplimiento || []).slice(0, 5),
        periodo: cumplimiento?.periodo || {}
      };

      setDashboardData(transformedData);
      setLastUpdate(new Date());
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (num) => {
    if (!num) return '0';
    return new Intl.NumberFormat('es-CL').format(Math.round(num));
  };

  const renderPeriodoInfo = () => {
    const mesNombre = MESES.find(m => m.value === selectedMonth)?.label || 'Mes';
    return `${mesNombre} ${selectedYear}`;
  };

  // Mapeo de IDs de área a nombres para mostrar
  const AREA_NAMES = {
    carguio: 'Carguío',
    transporte: 'Transporte',
    perforacion: 'Perforación & Tronadura',
    servicios: 'Servicios',
    seguridad: 'Seguridad & RRHH',
    costos: 'Costos'
  };

  // Si el área seleccionada no es 'todas', mostrar "PRÓXIMAMENTE"
  if (selectedArea && selectedArea !== 'todas') {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center max-w-md mx-auto p-12">
          <div className="w-24 h-24 bg-copper-50 rounded-full flex items-center justify-center mx-auto mb-6 shadow-lg shadow-copper-500/10">
            <Clock className="text-copper-500" size={48} />
          </div>
          <h2 className="text-3xl font-display font-bold text-slate-800 mb-3">
            PRÓXIMAMENTE
          </h2>
          <p className="text-lg text-slate-500 font-medium mb-2">
            {AREA_NAMES[selectedArea] || selectedArea}
          </p>
          <p className="text-sm text-slate-400">
            Esta sección está en desarrollo y estará disponible pronto.
          </p>
          <div className="mt-8 px-6 py-3 bg-copper-50 border border-copper-100 rounded-xl inline-block">
            <p className="text-xs text-copper-600 font-semibold uppercase tracking-wider">
              División Salvador • Codelco Chile
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-4">
            <div className="absolute inset-0 border-4 border-copper-100 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-copper-500 rounded-full border-t-transparent animate-spin"></div>
          </div>
          <p className="text-slate-500 font-medium">Cargando datos operacionales...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-100 rounded-2xl p-8 text-center max-w-md mx-auto shadow-lg shadow-red-500/5">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <AlertTriangle className="text-red-500" size={32} />
          </div>
          <h3 className="text-red-900 font-bold text-lg mb-2">Error de Conexión</h3>
          <p className="text-red-600 text-sm mb-6">{error}</p>
          <button
            onClick={fetchDashboardData}
            className="px-6 py-2 bg-red-500 hover:bg-red-600 text-white rounded-xl shadow-lg shadow-red-500/20 transition-all hover:-translate-y-0.5"
          >
            Reintentar Conexión
          </button>
        </div>
      </div>
    );
  }

  if (!dashboardData) {
    return null;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8 overflow-y-auto custom-scrollbar h-full pb-20">
      {/* Header con título y filtros */}
      <div className="glass-card rounded-2xl p-6 flex flex-col md:flex-row items-center justify-between gap-6">
        <div>
          <h1 className="text-3xl font-display font-bold text-slate-900">Dashboard Operacional</h1>
          <p className="text-slate-500 font-medium">División Salvador • Codelco Chile</p>
        </div>

        <div className="flex items-center gap-4 bg-white/50 p-2 rounded-xl border border-white/60 shadow-inner">
          <div className="flex items-center gap-2 px-2">
            <Calendar className="text-copper-600" size={18} />
            <select
              value={selectedYear || ''}
              onChange={(e) => setSelectedYear(parseInt(e.target.value))}
              className="bg-transparent border-none text-slate-700 font-semibold focus:ring-0 cursor-pointer text-sm"
            >
              {availableYears.map(year => (
                <option key={year} value={year}>{year}</option>
              ))}
            </select>
          </div>

          <div className="h-6 w-px bg-slate-200"></div>

          <div className="flex items-center gap-2 px-2">
            <select
              value={selectedMonth || ''}
              onChange={(e) => setSelectedMonth(parseInt(e.target.value))}
              className="bg-transparent border-none text-slate-700 font-semibold focus:ring-0 cursor-pointer text-sm"
            >
              {MESES.map(mes => (
                <option key={mes.value} value={mes.value}>
                  {mes.label}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={fetchDashboardData}
            disabled={loading}
            className="ml-2 p-2 bg-copper-500 hover:bg-copper-600 text-white rounded-lg shadow-md shadow-copper-500/20 transition-all hover:scale-105"
            title="Actualizar datos"
          >
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* KPIs Principales */}
      {dashboardData.kpis && dashboardData.kpis.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {dashboardData.kpis.map((kpi, idx) => (
            <div key={idx} className="group glass-card rounded-2xl p-6 hover:bg-white/90 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:border-copper-200">
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 bg-copper-50 rounded-xl group-hover:bg-copper-100 transition-colors">
                  {kpi.icon ? <kpi.icon size={20} className="text-copper-600" /> : <Activity size={20} className="text-copper-600" />}
                </div>
                {kpi.meta && (
                  <span className="text-[10px] font-bold px-2 py-1 bg-slate-100 text-slate-500 rounded-full uppercase tracking-wide">
                    Meta: {formatNumber(kpi.meta)}
                  </span>
                )}
              </div>

              <div className="space-y-1">
                <span className="text-sm font-medium text-slate-500">{kpi.nombre}</span>
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-bold text-slate-800 tracking-tight">
                    {formatNumber(kpi.valor)}
                  </span>
                  <span className="text-sm font-medium text-slate-400">{kpi.unidad}</span>
                </div>
              </div>

              {kpi.variacion !== undefined && kpi.variacion !== 0 && (
                <div className={`mt-4 flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-lg w-fit ${kpi.variacion > 0
                    ? 'bg-green-50 text-green-700 border border-green-100'
                    : 'bg-red-50 text-red-700 border border-red-100'
                  }`}>
                  {kpi.variacion > 0 ? '↑' : '↓'}
                  <span>{Math.abs(kpi.variacion).toFixed(1)}%</span>
                  <span className="font-normal opacity-80">vs meta</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Equipos - Rendimiento */}
        {dashboardData.equipos && dashboardData.equipos.length > 0 && (
          <div className="glass-card rounded-2xl p-6">
            <h3 className="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
              <Truck className="text-copper-500" size={20} />
              Rendimiento de Equipos
            </h3>
            <div className="overflow-hidden rounded-xl border border-slate-100">
              <table className="w-full">
                <thead className="bg-slate-50/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">Equipo</th>
                    <th className="px-4 py-3 text-right text-xs font-bold text-slate-500 uppercase tracking-wider">Ton Total</th>
                    <th className="px-4 py-3 text-right text-xs font-bold text-slate-500 uppercase tracking-wider">Dumps</th>
                    <th className="px-4 py-3 text-right text-xs font-bold text-slate-500 uppercase tracking-wider">Ton/Dump</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {dashboardData.equipos.map((equipo, idx) => (
                    <tr key={idx} className="hover:bg-copper-50/30 transition-colors">
                      <td className="px-4 py-3 font-semibold text-slate-700">{equipo.nombre}</td>
                      <td className="px-4 py-3 text-right text-slate-600">
                        {formatNumber(equipo.tonelaje_total)}
                      </td>
                      <td className="px-4 py-3 text-right text-slate-600">
                        {formatNumber(equipo.dumps_total)}
                      </td>
                      <td className="px-4 py-3 text-right text-slate-600 font-medium text-copper-600">
                        {formatNumber(equipo.ton_promedio)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Top Causas de Pérdidas */}
        {dashboardData.top_causas && dashboardData.top_causas.length > 0 && (
          <div className="glass-card rounded-2xl p-6">
            <h3 className="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
              <TrendingDown className="text-red-500" size={20} />
              Top 5 Causas de Pérdidas
            </h3>
            <div className="space-y-3">
              {dashboardData.top_causas.map((causa, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-white border border-slate-100 hover:border-red-100 hover:shadow-sm transition-all">
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm ${idx === 0 ? 'bg-red-100 text-red-600' : 'bg-slate-100 text-slate-500'
                      }`}>
                      #{idx + 1}
                    </div>
                    <div>
                      <div className="font-semibold text-slate-800 text-sm">{causa.razon}</div>
                      <div className="text-xs text-slate-400">{causa.categoria}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-slate-700">{formatNumber(causa.horas_perdidas)} hrs</div>
                    <div className="text-xs text-slate-400">{formatNumber(causa.eventos)} eventos</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Causas Críticas Pareto 80/20 */}
      {dashboardData.causas_criticas && dashboardData.causas_criticas.length > 0 && (
        <div className="glass-card rounded-2xl p-1 bg-gradient-to-br from-red-50/50 to-copper-50/50 border-red-100">
          <div className="p-6">
            <div className="flex items-center gap-4 mb-6">
              <div className="p-3 bg-red-100 rounded-xl">
                <AlertTriangle className="text-red-600" size={24} />
              </div>
              <div>
                <h3 className="text-xl font-bold text-slate-900">
                  Análisis Pareto 80/20
                </h3>
                <p className="text-sm text-slate-500">
                  <span className="font-bold text-red-600">{dashboardData.causas_criticas.length} causas críticas</span> generan el 80% del impacto total
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {dashboardData.causas_criticas.map((causa, idx) => (
                <div key={idx} className="bg-white/80 backdrop-blur-sm border border-red-100 rounded-xl p-5 hover:shadow-md transition-all">
                  <div className="flex justify-between items-start mb-3">
                    <span className="text-xs font-bold px-2 py-1 bg-red-50 text-red-600 rounded-lg border border-red-100">
                      #{idx + 1} Crítica
                    </span>
                    <div className="text-right">
                      <span className="block text-2xl font-bold text-slate-800">{causa.porcentaje}%</span>
                      <span className="text-[10px] text-slate-400 uppercase tracking-wider">Impacto</span>
                    </div>
                  </div>

                  <h4 className="font-bold text-slate-800 mb-1 line-clamp-2 h-10" title={causa.razon}>
                    {causa.razon}
                  </h4>
                  <p className="text-xs text-slate-500 mb-4">{causa.categoria}</p>

                  <div className="grid grid-cols-2 gap-2 pt-3 border-t border-slate-100">
                    <div>
                      <p className="text-[10px] text-slate-400 uppercase">Horas</p>
                      <p className="font-semibold text-slate-700">{formatNumber(causa.horas_perdidas)}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-[10px] text-slate-400 uppercase">Eventos</p>
                      <p className="font-semibold text-slate-700">{formatNumber(causa.cantidad_eventos)}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}