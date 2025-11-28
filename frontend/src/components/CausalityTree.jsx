import React from 'react';
import { AlertTriangle } from 'lucide-react';

/**
 * Árbol de Causalidad - Diagrama Sankey
 * Muestra flujo de causas raíz desde categorías hasta causas específicas
 */
export default function CausalityTree({ paretoData }) {
  if (!paretoData || !paretoData.pareto) {
    return null;
  }

  const totalHoras = paretoData.pareto.total_horas_perdidas;
  const categorias = paretoData.resumen_por_categoria || [];
  const topCausas = paretoData.pareto.top_delays.slice(0, 8); // Top 8 causas

  // Agrupar causas por categoría
  const causasPorCategoria = {};
  topCausas.forEach(causa => {
    if (!causasPorCategoria[causa.categoria]) {
      causasPorCategoria[causa.categoria] = [];
    }
    causasPorCategoria[causa.categoria].push(causa);
  });

  const colores = {
    'DET.NOPRG.': '#dc2626',      // Rojo
    'M. CORRECTIVA': '#ea580c',   // Naranja oscuro
    'DET.PROG.': '#f59e0b',       // Ámbar
    'M. PROGRAMADA': '#10b981',   // Verde
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border-2 border-orange-200 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <AlertTriangle className="text-orange-500" size={24} />
            Árbol de Causalidad - Análisis de Causas Raíz
          </h3>
          <p className="text-sm text-gray-600 mt-1">
            Flujo de pérdidas desde categorías hasta causas específicas
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-gray-900">
            {totalHoras.toLocaleString('es-CL')} hrs
          </div>
          <div className="text-xs text-gray-500">Total perdidas</div>
        </div>
      </div>

      {/* Diagrama de flujo */}
      <div className="relative" style={{ minHeight: '600px' }}>
        {/* Nodo raíz - Total */}
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-32">
          <div className="bg-gradient-to-r from-red-600 to-red-500 text-white rounded-lg p-4 shadow-lg">
            <div className="text-xs font-semibold mb-1">TOTAL</div>
            <div className="text-lg font-bold">
              {(totalHoras / 1000).toFixed(0)}K hrs
            </div>
            <div className="text-xs opacity-75">100%</div>
          </div>
        </div>

        {/* Nivel 1: Categorías */}
        <div className="absolute left-48 top-0 bottom-0 flex flex-col justify-around">
          {categorias.slice(0, 4).map((cat, idx) => {
            const heightPercent = (cat.horas_perdidas / totalHoras) * 100;
            const color = colores[cat.categoria] || '#6b7280';
            const yPosition = (idx * 25) + 10; // Distribuir verticalmente

            return (
              <div key={idx} className="relative" style={{ top: `${yPosition}%` }}>
                {/* Línea de conexión desde raíz */}
                <svg 
                  className="absolute right-full top-1/2 -translate-y-1/2"
                  width="80" 
                  height="4"
                  style={{ left: '-80px' }}
                >
                  <line
                    x1="0"
                    y1="2"
                    x2="80"
                    y2="2"
                    stroke={color}
                    strokeWidth={Math.max(heightPercent * 0.5, 2)}
                    opacity="0.6"
                  />
                </svg>

                {/* Nodo de categoría */}
                <div 
                  className="rounded-lg p-3 shadow-md text-white min-w-[160px]"
                  style={{ backgroundColor: color }}
                >
                  <div className="text-xs font-semibold mb-1 truncate">
                    {cat.categoria}
                  </div>
                  <div className="text-sm font-bold">
                    {(cat.horas_perdidas / 1000).toFixed(0)}K hrs
                  </div>
                  <div className="text-xs opacity-90">{cat.porcentaje}%</div>
                </div>

                {/* Nivel 2: Causas específicas de esta categoría */}
                {causasPorCategoria[cat.categoria] && (
                  <div className="absolute left-full ml-16 top-0 space-y-2">
                    {causasPorCategoria[cat.categoria].map((causa, cidx) => {
                      const causaPercent = (causa.horas_perdidas / cat.horas_perdidas) * 100;
                      
                      return (
                        <div key={cidx} className="relative">
                          {/* Línea de conexión desde categoría */}
                          <svg 
                            className="absolute right-full top-1/2 -translate-y-1/2"
                            width="64" 
                            height="4"
                            style={{ left: '-64px' }}
                          >
                            <line
                              x1="0"
                              y1="2"
                              x2="64"
                              y2="2"
                              stroke={color}
                              strokeWidth={Math.max(causaPercent * 0.3, 2)}
                              opacity="0.4"
                              strokeDasharray="4 2"
                            />
                          </svg>

                          {/* Nodo de causa */}
                          <div 
                            className="rounded-lg p-2 shadow-sm border-2 bg-white min-w-[200px] hover:shadow-md transition-shadow cursor-pointer"
                            style={{ borderColor: color }}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <div className="text-xs font-semibold text-gray-900 truncate">
                                {causa.razon}
                              </div>
                              {causa.en_pareto_80 && (
                                <span className="text-xs bg-red-100 text-red-700 px-1 rounded font-bold">
                                  80%
                                </span>
                              )}
                            </div>
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-gray-600">
                                {(causa.horas_perdidas / 1000).toFixed(1)}K hrs
                              </span>
                              <span className="font-semibold" style={{ color }}>
                                {causa.porcentaje}%
                              </span>
                            </div>
                            <div className="text-xs text-gray-500 mt-1">
                              {causa.cantidad_eventos.toLocaleString('es-CL')} eventos
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Leyenda */}
      <div className="mt-8 pt-4 border-t border-gray-200">
        <div className="flex items-center justify-center gap-6 flex-wrap text-xs">
          {Object.entries(colores).map(([cat, color]) => (
            <div key={cat} className="flex items-center gap-2">
              <div 
                className="w-4 h-4 rounded"
                style={{ backgroundColor: color }}
              />
              <span className="text-gray-600 font-medium">{cat}</span>
            </div>
          ))}
          <div className="flex items-center gap-2">
            <span className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded font-bold">
              80%
            </span>
            <span className="text-gray-600">Causas críticas Pareto</span>
          </div>
        </div>
      </div>

      {/* Métricas clave */}
      <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        {categorias.slice(0, 4).map((cat, idx) => (
          <div key={idx} className="bg-gray-50 rounded-lg p-3 border border-gray-200">
            <div className="text-xs text-gray-600 mb-1">{cat.categoria}</div>
            <div className="text-lg font-bold text-gray-900">
              {cat.porcentaje}%
            </div>
            <div className="text-xs text-gray-500">
              {cat.eventos.toLocaleString('es-CL')} eventos
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}