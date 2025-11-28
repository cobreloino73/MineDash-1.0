```javascript
import React, { useState, useEffect } from 'react';
import { AlertTriangle, TrendingDown } from 'lucide-react';

const API_URL = 'http://localhost:8001';

export default function ParetoChart({ year = 2024 }) {
  const [paretoData, setParetoData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPareto();
  }, [year]);

  const loadPareto = async () => {
    try {
      const response = await fetch(`${ API_URL } /api/analytics / pareto - delays ? year = ${ year }& mes_inicio=1 & mes_fin=12`);
      const data = await response.json();
      
      if (data.success) {
        setParetoData(data);
      }
    } catch (error) {
      console.error('Error cargando pareto:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !paretoData) {
    return (
      <div className="glass-card bg-white/50 rounded-2xl shadow-sm border border-copper-100 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-slate-200 rounded w-1/3"></div>
          <div className="h-96 bg-slate-200 rounded-xl"></div>
        </div>
      </div>
    );
  }

  // Tomar top 10 causas para el gráfico
  const topCausas = paretoData.pareto.top_delays.slice(0, 10);
  const maxHoras = Math.max(...topCausas.map(c => c.horas_perdidas));

  return (
    <div className="glass-card bg-white/80 rounded-2xl shadow-glass border border-copper-100 p-8 transition-all duration-300 hover:shadow-glass-lg">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h3 className="text-xl font-display font-bold text-slate-900 flex items-center gap-3">
            <div className="p-2 bg-red-50 rounded-lg">
              <TrendingDown className="text-red-500" size={24} />
            </div>
            Análisis Pareto 80/20
          </h3>
          <p className="text-sm text-slate-500 mt-1 ml-12 font-medium">
            Año {year} • <span className="text-slate-700 font-bold">{paretoData.pareto.total_horas_perdidas.toLocaleString('es-CL')}</span> horas perdidas totales
          </p>
        </div>
      </div>

      {/* Alert de Causas Críticas */}
      <div className="mb-8 p-6 bg-gradient-to-br from-red-50/80 to-copper-50/50 border border-red-100 rounded-2xl shadow-sm">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-red-100 rounded-xl shadow-sm">
            <AlertTriangle className="text-red-600" size={24} />
          </div>
          <div className="flex-1">
            <h4 className="font-bold text-red-900 mb-3 text-lg">
              {paretoData.pareto.cantidad_causas_criticas} Causa(s) Crítica(s) = {paretoData.pareto.porcentaje_impacto_causas_criticas}% del Impacto Total
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {paretoData.pareto.causas_criticas_80.map((causa, idx) => (
                <div key={idx} className="bg-white/80 backdrop-blur-sm border border-red-100 rounded-xl p-4 transition-all hover:shadow-md hover:-translate-y-0.5">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-slate-800 text-sm">#{idx + 1} {causa.razon}</span>
                    <span className="text-lg font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded-lg border border-red-100">{causa.porcentaje}%</span>
                  </div>
                  <div className="text-xs text-slate-500 font-medium flex justify-between">
                    <span>{causa.horas_perdidas.toLocaleString('es-CL')} hrs</span>
                    <span>{causa.cantidad_eventos.toLocaleString('es-CL')} eventos</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Gráfico de Cascada (Waterfall) */}
      <div className="relative" style={{ height: '500px' }}>
        <svg width="100%" height="500" className="overflow-visible">
          {/* Eje Y - Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((factor) => {
            const y = 460 - (factor * 380);
            const value = (maxHoras * factor).toFixed(0);
            return (
              <g key={factor}>
                <line
                  x1="80"
                  y1={y}
                  x2="100%"
                  y2={y}
                  stroke="#e2e8f0"
                  strokeWidth="1"
                  strokeDasharray={factor === 0 || factor === 1 ? "0" : "4 4"}
                />
                <text
                  x="75"
                  y={y + 4}
                  textAnchor="end"
                  className="text-xs fill-slate-400 font-medium"
                >
                  {parseInt(value).toLocaleString('es-CL')}
                </text>
              </g>
            );
          })}

          {/* Título Eje Y */}
          <text
            x="20"
            y="240"
            transform="rotate(-90 20 240)"
            textAnchor="middle"
            className="text-xs fill-slate-500 font-bold uppercase tracking-wider"
          >
            Horas Perdidas
          </text>

          {/* Barras */}
          {topCausas.map((causa, idx) => {
            const barWidth = (100 - 100) / topCausas.length;
            const x = 90 + (idx * 8) + '%';
            const height = (causa.horas_perdidas / maxHoras) * 380;
            const y = 460 - height;
            const enPareto = causa.en_pareto_80;
            
            return (
              <g key={idx} className="group cursor-pointer">
                {/* Barra */}
                <rect
                  x={x}
                  y={y}
                  width="7%"
                  height={height}
                  fill={enPareto ? '#ef4444' : '#f97316'}
                  className="transition-all duration-300 hover:opacity-90 hover:shadow-lg"
                  rx="6"
                  filter="url(#shadow)"
                />
                
                {/* Porcentaje encima de la barra */}
                <text
                  x={`calc(${ x } + 3.5 %)`}
                  y={y - 8}
                  textAnchor="middle"
                  className="text-[10px] fill-slate-700 font-bold"
                >
                  {causa.porcentaje}%
                </text>

                {/* Tooltip completo */}
                <g className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-50">
                  <rect
                    x={`calc(${ x } - 10 %)`}
                    y={y - 100}
                    width="27%"
                    height="90"
                    fill="#1e293b"
                    rx="12"
                    opacity="0.95"
                    className="shadow-xl"
                  />
                  <text
                    x={`calc(${ x } + 3.5 %)`}
                    y={y - 75}
                    textAnchor="middle"
                    className="text-sm fill-white font-bold"
                  >
                    {causa.razon}
                  </text>
                  <text
                    x={`calc(${ x } + 3.5 %)`}
                    y={y - 60}
                    textAnchor="middle"
                    className="text-xs fill-slate-400"
                  >
                    {causa.categoria}
                  </text>
                  <line
                    x1={`calc(${ x } + 1 %)`}
                    x2={`calc(${ x } + 6 %)`}
                    y1={y - 52}
                    y2={y - 52}
                    stroke="#475569"
                    strokeWidth="1"
                  />
                  <text
                    x={`calc(${ x } + 3.5 %)`}
                    y={y - 38}
                    textAnchor="middle"
                    className="text-xs fill-white font-medium"
                  >
                    {causa.horas_perdidas.toLocaleString('es-CL')} hrs
                  </text>
                  <text
                    x={`calc(${ x } + 3.5 %)`}
                    y={y - 24}
                    textAnchor="middle"
                    className="text-xs fill-white font-medium"
                  >
                    {causa.cantidad_eventos.toLocaleString('es-CL')} eventos
                  </text>
                  <text
                    x={`calc(${ x } + 3.5 %)`}
                    y={y - 10}
                    textAnchor="middle"
                    className="text-xs fill-amber-400 font-bold"
                  >
                    {causa.porcentaje}% impacto
                  </text>
                </g>

                {/* Etiqueta causa (eje X) - rotada */}
                <text
                  x={`calc(${ x } + 3.5 %)`}
                  y="480"
                  textAnchor="start"
                  transform={`rotate(45 calc(${ x } + 3.5 %) 480)`}
                  className={`text - [10px] font - bold uppercase tracking - tight ${ enPareto ? 'fill-red-600' : 'fill-slate-500' } `}
                >
                  {causa.razon.length > 18 ? causa.razon.substring(0, 15) + '...' : causa.razon}
                </text>
              </g>
            );
          })}

          {/* Línea acumulativa */}
          {topCausas.map((causa, idx) => {
            if (idx === 0) return null;
            const prevCausa = topCausas[idx - 1];
            const x1 = `calc(${ 90 + ((idx - 1) * 8) } % + 3.5 %)`;
            const x2 = `calc(${ 90 + (idx * 8) } % + 3.5 %)`;
            const y1 = 460 - ((prevCausa.porcentaje_acumulado / 100) * 380);
            const y2 = 460 - ((causa.porcentaje_acumulado / 100) * 380);
            
            return (
              <line
                key={`line - ${ idx } `}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke="#3b82f6"
                strokeWidth="2"
                strokeDasharray="4 4"
                opacity="0.6"
              />
            );
          })}
          
          {/* Defs for shadows */}
          <defs>
            <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#000000" floodOpacity="0.1"/>
            </filter>
          </defs>
        </svg>

        {/* Leyenda */}
        <div className="flex items-center justify-center gap-8 mt-8 text-xs font-medium">
          <div className="flex items-center gap-2 bg-red-50 px-3 py-1.5 rounded-lg border border-red-100">
            <div className="w-3 h-3 bg-red-500 rounded-full shadow-sm"></div>
            <span className="text-red-700">Causas Críticas 80%</span>
          </div>
          <div className="flex items-center gap-2 bg-orange-50 px-3 py-1.5 rounded-lg border border-orange-100">
            <div className="w-3 h-3 bg-orange-500 rounded-full shadow-sm"></div>
            <span className="text-orange-700">Otras Causas</span>
          </div>
          <div className="flex items-center gap-2 bg-blue-50 px-3 py-1.5 rounded-lg border border-blue-100">
            <div className="w-6 h-0.5 bg-blue-500 border-t border-dashed border-blue-300"></div>
            <span className="text-blue-700">% Acumulado</span>
          </div>
        </div>
      </div>
    </div>
  );
}
```