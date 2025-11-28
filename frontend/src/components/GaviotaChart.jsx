import React, { useState, useEffect } from 'react';
import { TrendingUp, Clock, AlertTriangle } from 'lucide-react';

const API_URL = 'http://localhost:8001';

export default function GaviotaChart({ fecha = '2024-07-15', turno = 'A' }) {
  const [gaviotaData, setGaviotaData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadGaviota();
  }, [fecha, turno]);

  const loadGaviota = async () => {
    try {
      const response = await fetch(`${API_URL}/api/dashboard/gaviota?fecha=${fecha}&turno=${turno}`);
      const data = await response.json();
      
      if (data.success) {
        setGaviotaData(data);
      }
    } catch (error) {
      console.error('Error cargando gaviota:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !gaviotaData) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-orange-100 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  const maxTonelaje = Math.max(...gaviotaData.datos_horarios.map(d => d.tonelaje));
  const promedio = gaviotaData.analisis.metricas.promedio_turno;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-orange-100 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <TrendingUp className="text-orange-500" size={24} />
            Análisis Gaviota - Producción Horaria
          </h3>
          <p className="text-sm text-gray-600 mt-1">
            Turno {turno} • {fecha} • {gaviotaData.analisis.horas_analizadas} horas
          </p>
        </div>
        <div className={`px-4 py-2 rounded-lg ${
          gaviotaData.analisis.estado === 'critico' ? 'bg-red-100 text-red-700' :
          gaviotaData.analisis.estado === 'regular' ? 'bg-yellow-100 text-yellow-700' :
          'bg-green-100 text-green-700'
        }`}>
          <span className="font-semibold">{gaviotaData.analisis.tipo_patron}</span>
        </div>
      </div>

      {/* Análisis */}
      <div className="mb-6 p-4 bg-orange-50 border border-orange-200 rounded-lg">
        <div className="flex items-start gap-2">
          <AlertTriangle className="text-orange-600 flex-shrink-0 mt-0.5" size={18} />
          <div>
            <p className="text-sm font-medium text-gray-900">{gaviotaData.analisis.descripcion}</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-xs">
              <div>
                <span className="text-gray-600">Promedio:</span>
                <span className="font-semibold text-gray-900 ml-1">
                  {promedio.toLocaleString('es-CL', { maximumFractionDigits: 0 })} ton/h
                </span>
              </div>
              <div>
                <span className="text-gray-600">Total turno:</span>
                <span className="font-semibold text-gray-900 ml-1">
                  {gaviotaData.analisis.metricas.total_turno.toLocaleString('es-CL', { maximumFractionDigits: 0 })} ton
                </span>
              </div>
              <div>
                <span className="text-gray-600">Pérdida estimada:</span>
                <span className="font-semibold text-red-600 ml-1">
                  {gaviotaData.analisis.perdida_estimada_ton.toLocaleString('es-CL')} ton
                </span>
              </div>
              {gaviotaData.analisis.outliers_corregidos > 0 && (
                <div>
                  <span className="text-gray-600">Outliers corregidos:</span>
                  <span className="font-semibold text-blue-600 ml-1">
                    {gaviotaData.analisis.outliers_corregidos}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Gráfico de Línea */}
      <div className="relative">
        <svg width="100%" height="300" className="overflow-visible">
          {/* Eje Y - Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((factor) => {
            const y = 280 - (factor * 240);
            const value = (maxTonelaje * factor).toFixed(0);
            return (
              <g key={factor}>
                <line
                  x1="50"
                  y1={y}
                  x2="100%"
                  y2={y}
                  stroke="#e5e7eb"
                  strokeWidth="1"
                  strokeDasharray={factor === 0 || factor === 1 ? "0" : "4 4"}
                />
                <text
                  x="45"
                  y={y + 4}
                  textAnchor="end"
                  className="text-xs fill-gray-500"
                >
                  {parseInt(value).toLocaleString('es-CL')}
                </text>
              </g>
            );
          })}

          {/* Línea de promedio */}
          <line
            x1="50"
            y1={280 - ((promedio / maxTonelaje) * 240)}
            x2="100%"
            y2={280 - ((promedio / maxTonelaje) * 240)}
            stroke="#f97316"
            strokeWidth="2"
            strokeDasharray="8 4"
            opacity="0.5"
          />
          <text
            x="55"
            y={280 - ((promedio / maxTonelaje) * 240) - 5}
            className="text-xs fill-orange-600 font-semibold"
          >
            Promedio: {promedio.toFixed(0)} ton/h
          </text>

          {/* Puntos y líneas */}
          {gaviotaData.datos_horarios.map((punto, idx) => {
            const x = 60 + (idx * ((100 - 60) / (gaviotaData.datos_horarios.length - 1))) + '%';
            const y = 280 - ((punto.tonelaje / maxTonelaje) * 240);
            const nextPunto = gaviotaData.datos_horarios[idx + 1];
            
            return (
              <g key={idx}>
                {/* Línea al siguiente punto */}
                {nextPunto && (
                  <line
                    x1={x}
                    y1={y}
                    x2={`${60 + ((idx + 1) * ((100 - 60) / (gaviotaData.datos_horarios.length - 1)))}%`}
                    y2={280 - ((nextPunto.tonelaje / maxTonelaje) * 240)}
                    stroke="#3b82f6"
                    strokeWidth="3"
                    className="transition-all hover:stroke-orange-500"
                  />
                )}
                
                {/* Punto */}
                <g className="cursor-pointer group">
                  <circle
                    cx={x}
                    cy={y}
                    r="5"
                    fill={punto.corregido ? "#f59e0b" : "#3b82f6"}
                    stroke="white"
                    strokeWidth="2"
                    className="transition-all group-hover:r-7"
                  />
                  
                  {/* Tooltip */}
                  <g className="opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    <rect
                      x={`calc(${x} - 60px)`}
                      y={y - 60}
                      width="120"
                      height="50"
                      fill="#1f2937"
                      rx="6"
                      opacity="0.95"
                    />
                    <text
                      x={x}
                      y={y - 40}
                      textAnchor="middle"
                      className="text-xs fill-white font-semibold"
                    >
                      Hora {punto.hora}
                    </text>
                    <text
                      x={x}
                      y={y - 25}
                      textAnchor="middle"
                      className="text-xs fill-white"
                    >
                      {punto.tonelaje.toLocaleString('es-CL', { maximumFractionDigits: 0 })} ton
                    </text>
                    {punto.corregido && (
                      <text
                        x={x}
                        y={y - 12}
                        textAnchor="middle"
                        className="text-xs fill-yellow-300"
                      >
                        ⚠️ Corregido
                      </text>
                    )}
                  </g>
                </g>

                {/* Etiqueta hora (eje X) */}
                <text
                  x={x}
                  y="295"
                  textAnchor="middle"
                  className="text-xs fill-gray-600 font-medium"
                >
                  {punto.hora}h
                </text>
              </g>
            );
          })}
        </svg>

        {/* Leyenda */}
        <div className="flex items-center justify-center gap-6 mt-4 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500"></div>
            <span className="text-gray-600">Producción Real</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-amber-500"></div>
            <span className="text-gray-600">Dato Corregido</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-orange-500 opacity-50"></div>
            <span className="text-gray-600">Promedio del Turno</span>
          </div>
        </div>
      </div>
    </div>
  );
}